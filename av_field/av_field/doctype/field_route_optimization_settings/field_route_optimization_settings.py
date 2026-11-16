import frappe
from frappe.model.document import Document


class FieldRouteOptimizationSettings(Document):
    def validate(self):
        if (self.max_stops or 0) < 1 or self.max_stops > 100:
            frappe.throw("Maximum stops must be between 1 and 100")
        if (self.daily_credit_budget or 0) < 0 or self.daily_credit_budget > 3000:
            frappe.throw("Set the baseline credit budget between 0 and 3000")
        if (self.request_timeout_seconds or 0) < 3 or self.request_timeout_seconds > 60:
            frappe.throw("Request timeout must be between 3 and 60 seconds")
        if str(self.working_end or "") <= str(self.working_start or ""):
            frappe.throw("Working end time must be after working start time")
