"""Authenticated same-origin API. Each push is one atomic Frappe transaction."""
from datetime import date
from html import escape

import frappe
from frappe.utils import getdate, nowdate

from av_field.records import check_master, conversion_guard, require_agent
from av_field.validation import InvalidOperation, fingerprint, normalize, operation_name


@frappe.whitelist(methods=["GET"])
def context():
    require_agent()
    from frappe.sessions import get_csrf_token
    frappe.local.response_headers["Cache-Control"] = "no-store"
    return {"user": frappe.session.user, "csrf_token": get_csrf_token(), "version": 1}


@frappe.whitelist(methods=["GET"])
def references(kind, after=""):
    require_agent()
    specs = {"customers": ("Customer", ["name", "customer_name"], {"disabled": 0}),
             "items": ("Item", ["name", "item_name", "stock_uom"],
                       {"disabled": 0, "is_sales_item": 1, "has_variants": 0})}
    if kind not in specs or not isinstance(after, str) or len(after) > 140:
        frappe.throw("Invalid reference request")
    doctype, fields, filters = specs[kind]
    filters = dict(filters)
    if after:
        filters["name"] = [">", after]
    # get_list applies role permissions and User Permissions. Never get_all here.
    rows = frappe.get_list(doctype, fields=fields, filters=filters,
                           order_by="name asc", limit_page_length=201)
    more = len(rows) > 200
    rows = rows[:200]
    return {"rows": rows, "after": rows[-1].name if more else None}


@frappe.whitelist(methods=["POST"])
def push(operation):
    require_agent()
    operation = frappe.parse_json(operation)
    try:
        operation = normalize(operation)
    except InvalidOperation as exc:
        frappe.throw(str(exc))
    doctype = "Field Visit" if operation["kind"] == "visit" else "Field Order Request"
    frappe.has_permission(doctype, "create", throw=True)
    name = operation_name(frappe.session.user, operation["id"])
    digest = fingerprint(operation)

    def existing_ack():
        existing = frappe.get_doc(doctype, name)
        existing.check_permission("read")
        if existing.submitted_by != frappe.session.user or existing.payload_hash != digest:
            frappe.throw("Operation ID already used with different data")
        return {"id": operation["id"], "name": name, "doctype": doctype, "duplicate": True}

    if frappe.db.exists(doctype, name):
        return existing_ack()
    payload = operation["payload"]
    values = {"doctype": doctype, "operation_id": operation["id"],
              "recorded_at": operation["recorded_at"], **payload}
    if operation["kind"] == "visit":
        values["has_location"] = int(payload["latitude"] is not None)
    frappe.db.savepoint("field_push")
    try:
        frappe.get_doc(values).insert()
    except frappe.DuplicateEntryError:
        # A second tab/device retried the same UUID at the same time.
        frappe.db.rollback(save_point="field_push")
        return existing_ack()
    return {"id": operation["id"], "name": name, "doctype": doctype, "duplicate": False}


@frappe.whitelist(methods=["POST"])
def make_sales_order(request_name, company, delivery_date):
    require_agent()
    if not {"Field Manager", "System Manager"}.intersection(frappe.get_roles()):
        frappe.throw("Only a Field Manager may convert a request", frappe.PermissionError)
    frappe.has_permission("Sales Order", "create", throw=True)
    # Row lock serializes concurrent conversion requests without raw SQL.
    table = frappe.qb.DocType("Field Order Request")
    frappe.qb.from_(table).select(table.name).where(table.name == request_name).for_update().run()
    request = frappe.get_doc("Field Order Request", request_name)
    request.check_permission("read")
    request.check_permission("write")
    if request.sales_order:
        frappe.get_doc("Sales Order", request.sales_order).check_permission("read")
        return request.sales_order
    try:
        delivery_date = date.fromisoformat(delivery_date).isoformat()
    except (ValueError, TypeError):
        frappe.throw("A delivery date in YYYY-MM-DD format is required")
    if getdate(delivery_date) < getdate(nowdate()):
        frappe.throw("Delivery date cannot be in the past")
    check_master("Company", company)
    check_master("Customer", request.customer)
    items = []
    for row in request.items:
        item = check_master("Item", row.item_code)
        items.append({"item_code": item.name, "qty": row.qty, "uom": item.stock_uom,
                      "delivery_date": delivery_date})
    order = frappe.get_doc({"doctype": "Sales Order", "company": company,
                           "customer": request.customer, "transaction_date": nowdate(), "order_type": "Sales",
                           "delivery_date": delivery_date, "items": items})
    # Standard ERPNext validation/pricing/tax rules apply; mobile never supplies rates.
    order.set_missing_values()
    order.calculate_taxes_and_totals()
    if any(not row.rate and not row.is_free_item for row in order.items):
        frappe.throw("A selling rate is missing. Configure prices before conversion.")
    order.insert()
    order.add_comment("Comment", f"Created from AV Field request {request.name}.<br>{escape(request.notes or chr(32))}")
    with conversion_guard(request.name):
        request.sales_order = order.name
        request.save()
    return order.name
