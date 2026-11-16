"""Install additive AV Field master fields without changing ERPNext's core schemas."""
import frappe


CUSTOM_FIELDS = {
    "Customer": [
        ("field_sales_user", "Field Salesperson (User)", "Link", "User", "territory"),
        ("field_visit_frequency_days", "Field Visit Frequency (Days)", "Int", None, "field_sales_user"),
    ],
    "Address": [
        ("field_geojson", "Field Sales Location", "Geolocation", None, "address_line2"),
        ("field_visit_enabled", "Include in Field Sales Routes", "Check", None, "field_geojson"),
        ("field_visit_minutes", "Planned Visit Minutes", "Int", None, "field_visit_enabled"),
        ("field_visit_priority", "Field Visit Priority", "Select", "Normal\nHigh\nCritical", "field_visit_minutes"),
        ("field_visit_start", "Preferred Visit From", "Time", None, "field_visit_priority"),
        ("field_visit_end", "Preferred Visit Until", "Time", None, "field_visit_start"),
        ("field_visit_instructions", "Field Visit Instructions", "Small Text", None, "field_visit_end"),
    ],
}


def ensure_route_fields():
    """Idempotent on fresh installs and migrate; never overwrite site-owned customizations."""
    for dt, fields in CUSTOM_FIELDS.items():
        for fieldname, label, fieldtype, options, insert_after in fields:
            if frappe.get_meta(dt).has_field(fieldname):
                continue
            values = {
                "doctype": "Custom Field", "dt": dt, "fieldname": fieldname,
                "label": label, "fieldtype": fieldtype, "insert_after": insert_after,
                "module": "AV Field",
            }
            if options:
                values["options"] = options
            if fieldname == "field_visit_enabled":
                values["default"] = "0"
            elif fieldname == "field_visit_minutes":
                values["default"] = "20"
            elif fieldname == "field_visit_frequency_days":
                values["default"] = "7"
            elif fieldname == "field_visit_priority":
                values["default"] = "Normal"
            frappe.get_doc(values).insert(ignore_permissions=True)
        frappe.clear_cache(doctype=dt)
