import frappe
from frappe.model.document import Document

from av_field.route_optimizer import _sales_address
from av_field.route_geo import RoutingError


class FieldRoutePlan(Document):
    def validate(self):
        if not self.stops:
            frappe.throw("Add at least one route stop")
        seen = set()
        for row in self.stops:
            if not row.sequence or row.sequence <= 0:
                frappe.throw("Route sequence must be positive")
            key = row.address or row.outlet
            if not key or key in seen:
                frappe.throw("Route must contain unique Addresses or legacy outlets")
            seen.add(key)
            if row.address:
                if not row.customer:
                    frappe.throw("Customer is required for each Address stop")
                if self.is_new():
                    try:
                        _sales_address(row.customer, row.address, self.salesperson)
                    except RoutingError as exc:
                        frappe.throw(str(exc))
            else:
                outlet = frappe.get_doc("Field Customer Outlet", row.outlet)
                if self.is_new() and (not outlet.active or outlet.salesperson != self.salesperson):
                    frappe.throw("Legacy outlet is inactive or assigned elsewhere")
                row.customer = outlet.customer
