import frappe
from frappe.model.document import Document


class FieldCallCycle(Document):
    def validate(self):
        if not self.stops:
            frappe.throw("Add at least one recurring stop")
        seen = set()
        for row in self.stops:
            if row.sequence <= 0:
                frappe.throw("Stop sequence must be positive")
            key = (row.day_of_week, row.outlet)
            if key in seen:
                frappe.throw("An outlet cannot appear twice on the same day")
            seen.add(key)
            outlet = frappe.get_doc("Field Customer Outlet", row.outlet)
            if not outlet.active or outlet.salesperson != self.salesperson:
                frappe.throw("Every outlet must be active and assigned to the call cycle salesperson")
