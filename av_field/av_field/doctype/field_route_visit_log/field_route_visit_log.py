import frappe
from frappe.model.document import Document


class FieldRouteVisitLog(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw("Route visit logs are immutable. Add a correction event instead.")

    def on_trash(self):
        frappe.throw("Route visit logs cannot be deleted.")
