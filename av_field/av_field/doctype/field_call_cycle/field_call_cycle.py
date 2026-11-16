import frappe
from frappe.model.document import Document

from av_field.route_optimizer import _sales_address
from av_field.route_geo import RoutingError


class FieldCallCycle(Document):
    def validate(self):
        if not self.stops:
            frappe.throw("Add at least one recurring stop")
        seen = set()
        for row in self.stops:
            if not row.sequence or row.sequence <= 0:
                frappe.throw("Stop sequence must be positive")
            key = (row.day_of_week, row.address or row.outlet)
            if not key[1] or key in seen:
                frappe.throw("Each weekly stop must have one unique Address or legacy outlet")
            seen.add(key)
            if row.address:
                if not row.customer:
                    frappe.throw("Select the Customer associated with this Address")
                try:
                    _sales_address(row.customer, row.address, self.salesperson)
                except RoutingError as exc:
                    frappe.throw(str(exc))
            else:
                outlet = frappe.get_doc("Field Customer Outlet", row.outlet)
                if not outlet.active or outlet.salesperson != self.salesperson:
                    frappe.throw("Legacy outlet is inactive or assigned to another salesperson")
