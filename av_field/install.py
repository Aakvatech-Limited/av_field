import frappe

from av_field.route_setup import ensure_route_fields


def after_install():
    ensure_route_fields()
    # App-specific roles only: customer/item visibility stays under ERPNext permissions.
    for role in ("Field Agent", "Field Manager"):
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert()
