import frappe
from frappe.model.document import Document


class FieldRoutePlan(Document):
    def validate(self):
        if not self.stops:
            frappe.throw("Add at least one route stop")
        seen = set()
        for row in self.stops:
            if not row.sequence or row.sequence <= 0:
                frappe.throw("Route sequence must be positive")
            if row.outlet in seen:
                frappe.throw("An outlet cannot appear twice in the same daily plan")
            seen.add(row.outlet)
            outlet = frappe.get_doc("Field Customer Outlet", row.outlet)
            if self.is_new() and (not outlet.active or outlet.salesperson != self.salesperson):
                frappe.throw("Every outlet must be active and assigned to the route salesperson")
            row.customer = outlet.customer
