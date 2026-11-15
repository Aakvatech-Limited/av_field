"""Route planning and visit outcomes, separate from immutable field capture."""
from datetime import datetime
from uuid import UUID

import frappe
from frappe.utils import getdate, now_datetime

from av_field.records import require_agent

OUTCOMES = {"Done", "Skipped", "Not Done", "Postponed"}
MANAGERS = {"Field Manager", "System Manager"}


def _manager():
    require_agent()
    if not MANAGERS.intersection(frappe.get_roles()):
        frappe.throw("A Field Manager is required", frappe.PermissionError)


def _visible(doc):
    require_agent()
    if not MANAGERS.intersection(frappe.get_roles()) and doc.salesperson != frappe.session.user:
        frappe.throw("This route is assigned to another salesperson", frappe.PermissionError)


def _safe_text(value, name, limit=5000):
    if not isinstance(value, str) or len(value) > limit:
        frappe.throw(name + " must be text of at most " + str(limit) + " characters")
    return value.strip()


def _day(date):
    return getdate(date).strftime("%A")


@frappe.whitelist(methods=["POST"])
def generate_route(call_cycle, route_date, publish=0):
    """Generate an ordered day plan from a recurring weekly call cycle."""
    _manager()
    day = getdate(route_date)
    template = frappe.get_doc("Field Call Cycle", call_cycle)
    template.check_permission("read")
    if not template.active:
        frappe.throw("The call cycle is inactive")
    existing = frappe.get_list(
        "Field Route Plan",
        filters={"call_cycle": call_cycle, "route_date": day},
        fields=["name"],
        limit_page_length=1,
    )
    if existing:
        frappe.throw("A route already exists for this cycle and date: " + existing[0].name)
    stops = sorted(
        [r for r in template.stops if r.day_of_week == _day(day)],
        key=lambda r: (r.sequence, r.idx),
    )
    if not stops:
        frappe.throw("The call cycle has no stops on " + _day(day))
    values = []
    seen = set()
    for item in stops:
        if item.outlet in seen:
            frappe.throw("The call cycle includes the same outlet twice on this day")
        seen.add(item.outlet)
        outlet = frappe.get_doc("Field Customer Outlet", item.outlet)
        if not outlet.active:
            frappe.throw("Inactive outlet: " + outlet.name)
        values.append({
            "outlet": outlet.name,
            "customer": outlet.customer,
            "sequence": item.sequence,
            "planned_time": item.planned_time,
            "purpose": item.purpose,
            "status": "Pending",
        })
    doc = frappe.get_doc({
        "doctype": "Field Route Plan",
        "route_date": day,
        "salesperson": template.salesperson,
        "zone": template.zone,
        "call_cycle": template.name,
        "status": "Published" if frappe.utils.cint(publish) else "Draft",
        "stops": values,
    })
    doc.insert()
    return {"name": doc.name, "count": len(values)}


@frappe.whitelist(methods=["GET"])
def my_routes(expected_user, after=""):
    """Cursor-paginated published plan snapshot for authenticated account's offline PWA."""
    require_agent()
    if expected_user != frappe.session.user:
        frappe.throw("Signed-in account changed", frappe.PermissionError)
    if not isinstance(after, str) or len(after) > 140:
        frappe.throw("Invalid cursor")
    filters = {"salesperson": frappe.session.user, "status": "Published"}
    if after:
        filters["name"] = [">", after]
    plans = frappe.get_list(
        "Field Route Plan", filters=filters,
        fields=["name", "route_date", "salesperson", "status", "zone"],
        order_by="name asc", limit_page_length=101,
    )
    more = len(plans) > 100
    rows = []
    for basic in plans[:100]:
        plan = frappe.get_doc("Field Route Plan", basic.name)
        _visible(plan)
        rows.append({
            "name": plan.name,
            "route_date": str(plan.route_date),
            "zone": plan.zone,
            "status": plan.status,
            "stops": [{
                "name": s.name, "outlet": s.outlet, "customer": s.customer,
                "sequence": s.sequence, "planned_time": str(s.planned_time or ""),
                "purpose": s.purpose, "status": s.status,
                "status_reason": s.status_reason,
                "action_taken": s.action_taken,
                "next_action": s.next_action,
                "next_action_date": str(s.next_action_date or ""),
                "postponed_to": str(s.postponed_to or ""),
            } for s in sorted(plan.stops, key=lambda s: s.sequence)],
        })
    return {"rows": rows, "after": rows[-1]["name"] if more else None}


@frappe.whitelist(methods=["GET"])
def my_outlets(expected_user, after=""):
    """Only outlets assigned to the agent, excluding unrelated customers."""
    require_agent()
    if expected_user != frappe.session.user:
        frappe.throw("Signed-in account changed", frappe.PermissionError)
    filters = {"salesperson": frappe.session.user, "active": 1}
    if after:
        filters["name"] = [">", after]
    rows = frappe.get_list(
        "Field Customer Outlet", filters=filters,
        fields=["name", "customer", "outlet_name", "latitude", "longitude",
                "visit_instructions", "address"],
        order_by="name asc", limit_page_length=201,
    )
    more = len(rows) > 200
    return {"rows": rows[:200], "after": rows[199].name if more else None}


@frappe.whitelist(methods=["POST"])
def record_outcome(operation, expected_user):
    """Idempotent offline outcome event; last accepted event updates the route row."""
    require_agent()
    if expected_user != frappe.session.user:
        frappe.throw("Signed-in account changed", frappe.PermissionError)
    op = frappe.parse_json(operation)
    if not isinstance(op, dict) or op.get("kind") != "route_outcome" or op.get("version") != 1:
        frappe.throw("Invalid route outcome contract")
    try:
        uid = str(UUID(op["id"]))
        when = datetime.fromisoformat(op["recorded_at"].replace("Z", "+00:00"))
        if not when.tzinfo:
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        frappe.throw("A valid UUID and timezone-aware recorded timestamp are required")
    payload = op.get("payload")
    if not isinstance(payload, dict):
        frappe.throw("Missing outcome details")
    allowed = {"plan", "stop", "outcome", "reason", "action_taken",
               "next_action", "next_action_date", "postponed_to",
               "latitude", "longitude", "accuracy"}
    if set(payload) - allowed:
        frappe.throw("Unexpected outcome details")
    outcome = payload.get("outcome")
    if outcome not in OUTCOMES:
        frappe.throw("Invalid visit status")
    reason = _safe_text(payload.get("reason", ""), "Reason")
    action = _safe_text(payload.get("action_taken", ""), "Action")
    next_action = _safe_text(payload.get("next_action", ""), "Next action")
    if outcome in {"Skipped", "Not Done", "Postponed"} and not reason:
        frappe.throw("A reason is required when the visit was not completed")
    postponed = payload.get("postponed_to") or None
    if outcome == "Postponed" and not postponed:
        frappe.throw("Select the postponed date")
    if postponed:
        postponed = getdate(postponed)
    next_date = getdate(payload["next_action_date"]) if payload.get("next_action_date") else None
    lat, lon = payload.get("latitude"), payload.get("longitude")
    if (lat is None) != (lon is None):
        frappe.throw("GPS coordinates must be paired")
    accuracy = payload.get("accuracy")
    if lat is not None:
        try:
            lat, lon = float(lat), float(lon)
            accuracy = float(accuracy) if accuracy is not None else None
        except (TypeError, ValueError):
            frappe.throw("GPS values must be numeric")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (accuracy is not None and not 0 <= accuracy <= 100000):
            frappe.throw("GPS values are outside valid ranges")
    elif accuracy is not None:
        frappe.throw("Accuracy requires coordinates")
    existing = frappe.db.get_value("Field Route Visit Log", {"operation_id": uid}, ["name", "salesperson"], as_dict=True)
    if existing:
        if existing.salesperson != frappe.session.user:
            frappe.throw("Outcome ID belongs to another user", frappe.PermissionError)
        return {"id": uid, "name": existing.name, "doctype": "Field Route Visit Log", "duplicate": True}
    plan = frappe.get_doc("Field Route Plan", payload.get("plan"))
    _visible(plan)
    if plan.status != "Published":
        frappe.throw("Route is no longer published")
    stop = next((s for s in plan.stops if s.name == payload.get("stop")), None)
    if not stop:
        frappe.throw("The stop is not on the assigned route")
    if stop.status != "Pending":
        frappe.throw("This stop is already resolved. Ask your manager to reopen it.")
    log = frappe.get_doc({
        "doctype": "Field Route Visit Log", "route_plan": plan.name,
        "stop_id": stop.name, "outlet": stop.outlet,
        "salesperson": frappe.session.user, "outcome": outcome,
        "reason": reason, "action_taken": action, "next_action": next_action,
        "next_action_date": next_date, "postponed_to": postponed,
        "recorded_at": when, "latitude": lat, "longitude": lon,
        "accuracy": accuracy, "operation_id": uid,
    })
    # Agent cannot mutate manager-owned route documents directly; route API enforces ownership.
    log.insert(ignore_permissions=True)
    stop.status = outcome
    stop.status_reason = reason
    stop.action_taken = action
    stop.next_action = next_action
    stop.next_action_date = next_date
    stop.postponed_to = postponed
    stop.visited_at = when if outcome == "Done" else None
    stop.latitude, stop.longitude, stop.accuracy = lat, lon, accuracy
    plan.save(ignore_permissions=True)
    return {"id": uid, "name": log.name, "doctype": "Field Route Visit Log", "duplicate": False}
