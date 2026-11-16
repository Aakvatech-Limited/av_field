"""Geoapify-based route generation from ERPNext Customers and linked Addresses."""
import hashlib
import json
from datetime import datetime

import frappe
import requests
from frappe.utils import getdate, nowdate

from av_field.route_geo import RoutingError, optimized_jobs, point_from_geojson

ENDPOINT = "https://api.geoapify.com/v1/routeplanner"


def _seconds(value):
    parts = str(value or "").split(":")
    if len(parts) < 2:
        raise RoutingError("Invalid time window")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + (int(float(parts[2])) if len(parts) > 2 else 0)


def _clock(seconds):
    seconds = int(seconds)
    if not 0 <= seconds < 86400:
        raise RoutingError("Geoapify returned an arrival outside the route day")
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:00"


def _linked_to_customer(address, customer):
    return bool(frappe.db.exists("Dynamic Link", {
        "parenttype": "Address", "parent": address,
        "link_doctype": "Customer", "link_name": customer,
    }))


def _sales_address(customer_name, address_name, salesperson):
    customer = frappe.get_doc("Customer", customer_name)
    if customer.disabled or customer.get("field_sales_user") != salesperson:
        raise RoutingError("Customer is disabled or not assigned to this salesperson: " + customer_name)
    if not _linked_to_customer(address_name, customer_name):
        raise RoutingError("Address is not linked to Customer: " + address_name)
    address = frappe.get_doc("Address", address_name)
    if not address.get("field_visit_enabled"):
        raise RoutingError("Address is not enabled for sales visits: " + address_name)
    location = point_from_geojson(address.get("field_geojson"))
    return customer, address, location


def _due(customer_name, address_name, day, frequency):
    if frequency <= 0:
        return True
    last = frappe.get_all(
        "Field Route Visit Log",
        filters={"customer": customer_name, "address": address_name, "outcome": "Done"},
        fields=["recorded_at"], order_by="recorded_at desc", limit_page_length=1,
    )
    return not last or (day - getdate(last[0].recorded_at)).days >= frequency


def _eligible_jobs(salesperson, day, selected=None):
    customers = frappe.get_all("Customer",
        filters={"field_sales_user": salesperson, "disabled": 0},
        fields=["name", "field_visit_frequency_days"], order_by="name")
    selected = set(selected) if selected is not None else None
    jobs = []
    for c in customers:
        addresses = frappe.get_all("Dynamic Link",
            filters={"parenttype": "Address", "link_doctype": "Customer", "link_name": c.name},
            pluck="parent")
        for address_name in sorted(set(addresses)):
            if selected is not None and address_name not in selected:
                continue
            address = frappe.get_doc("Address", address_name)
            if not address.get("field_visit_enabled"):
                continue
            customer, address, location = _sales_address(c.name, address_name, salesperson)
            if not _due(c.name, address_name, day, max(0, int(c.field_visit_frequency_days or 0))):
                continue
            job = {"id": f"job-{len(jobs)}", "location": location,
                   "duration": max(1, int(address.get("field_visit_minutes") or 20)) * 60,
                   "priority": {"Normal": 30, "High": 70, "Critical": 100}.get(
                       address.get("field_visit_priority"), 30)}
            start, end = address.get("field_visit_start"), address.get("field_visit_end")
            if start and end:
                start_seconds, end_seconds = _seconds(start), _seconds(end)
                if start_seconds >= end_seconds:
                    raise RoutingError("Invalid preferred time window for " + address_name)
                job["time_windows"] = [[start_seconds, end_seconds]]
            jobs.append({"customer": c.name, "address": address_name, "job": job,
                         "instructions": address.get("field_visit_instructions")})
    if selected is not None:
        found = {item["address"] for item in jobs}
        if selected - found:
            raise RoutingError("Some selected addresses are not eligible, due or assigned")
    return jobs


def _consume_api(settings, body):
    key = settings.get_password("api_key")
    if not key:
        raise RoutingError("Configure the Geoapify API key")
    try:
        response = requests.post(
            ENDPOINT, params={"apiKey": key},
            json=body, timeout=(5, int(settings.request_timeout_seconds or 25)),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        # Do not log a response or exception containing an API URL with its secret.
        raise RoutingError("Geoapify optimization is unavailable; use a manual route and try again") from None


def create_optimized_route(salesperson, route_date, publish=False, selected_addresses=None):
    """Manager-side synchronous MVP: one driving agent; never silently drop jobs."""
    day = getdate(route_date)
    settings = frappe.get_single("Field Route Optimization Settings")
    if not settings.enabled:
        raise RoutingError("Enable Geoapify in Field Route Optimization Settings")
    if not frappe.db.exists("User", {"name": salesperson, "enabled": 1}):
        raise RoutingError("Choose an enabled salesperson User")
    if frappe.db.exists("Field Route Plan", {"salesperson": salesperson, "route_date": day,
                                              "optimization_provider": "Geoapify"}):
        raise RoutingError("An optimized route already exists for this salesperson and date")
    if selected_addresses is not None:
        if not isinstance(selected_addresses, list) or any(not isinstance(x, str) for x in selected_addresses):
            raise RoutingError("Selected addresses must be a list")
        if len(selected_addresses) != len(set(selected_addresses)):
            raise RoutingError("Duplicate selected addresses")
    jobs = _eligible_jobs(salesperson, day, selected_addresses)
    if not jobs:
        raise RoutingError("No assigned customer addresses are due for visits")
    if len(jobs) > min(int(settings.max_stops or 20), 100):
        raise RoutingError("Too many due customer addresses. Reduce the route stop count")
    if not settings.start_address:
        raise RoutingError("Configure the route starting Address")
    start = frappe.get_doc("Address", settings.start_address)
    starting_point = point_from_geojson(start.get("field_geojson"))
    unique_locations = {tuple(starting_point)} | {tuple(j["job"]["location"]) for j in jobs}
    estimated_credits = len(unique_locations) * min(len(unique_locations), 10)
    if estimated_credits > int(settings.daily_credit_budget or 0):
        raise RoutingError("This route exceeds the configured free-tier baseline credit budget")
    # This preflight is an estimate, not the Geoapify provider's actual billing.
    used = sum(int(p.estimated_credits or 0) for p in frappe.get_all(
        "Field Route Plan", filters={"creation": [">=", nowdate()]},
        fields=["estimated_credits"]))
    if used + estimated_credits > int(settings.daily_credit_budget or 0):
        raise RoutingError("Estimated daily route credits would exceed the configured budget")
    window = [_seconds(settings.working_start), _seconds(settings.working_end)]
    if not window[0] < window[1]:
        raise RoutingError("Workday end must be after start")
    body = {
        "mode": "drive",
        "traffic": settings.traffic_model or "approximated",
        "agents": [{"id": salesperson, "start_location": starting_point, "time_windows": [window]}],
        "jobs": [j["job"] for j in jobs],
    }
    response = _consume_api(settings, body)
    order, distance, seconds = optimized_jobs(response, [j["job"]["id"] for j in jobs])
    lookup = {j["job"]["id"]: j for j in jobs}
    stops = []
    for position, item in enumerate(order, 1):
        job = lookup[item["id"]]
        stops.append({
            "customer": job["customer"], "address": job["address"],
            "sequence": position,
            "planned_time": _clock(item["arrival_seconds"]) if item["arrival_seconds"] is not None else None,
            "estimated_arrival": _clock(item["arrival_seconds"]) if item["arrival_seconds"] is not None else None,
            "purpose": "Sales", "status": "Pending",
        })
    doc = frappe.get_doc({
        "doctype": "Field Route Plan", "route_date": day,
        "salesperson": salesperson,
        "start_address": settings.start_address,
        "optimization_provider": "Geoapify",
        "estimated_credits": estimated_credits,
        "estimated_distance_m": distance,
        "estimated_travel_seconds": seconds,
        "status": "Published" if publish else "Draft", "stops": stops,
    })
    doc.insert()
    return {"name": doc.name, "count": len(stops), "distance_m": distance,
            "travel_seconds": seconds, "estimated_credits": estimated_credits}


@frappe.whitelist(methods=["POST"])
def generate_optimized_route(salesperson, route_date, publish=0, selected_addresses=None):
    from av_field.routes import _manager
    _manager()
    try:
        selected = frappe.parse_json(selected_addresses) if isinstance(selected_addresses, str) else selected_addresses
        return create_optimized_route(salesperson, route_date, bool(frappe.utils.cint(publish)), selected)
    except RoutingError as exc:
        frappe.throw(str(exc))
