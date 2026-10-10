from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

import frappe
from frappe.model.document import Document

from av_field.validation import InvalidOperation, fingerprint, normalize, operation_name


_conversion = ContextVar("field_conversion", default=None)


@contextmanager
def conversion_guard(name):
    token = _conversion.set(name)
    try:
        yield
    finally:
        _conversion.reset(token)


def require_agent():
    if frappe.session.user == "Guest" or not {"Field Agent", "Field Manager", "System Manager"}.intersection(frappe.get_roles()):
        frappe.throw("Field Agent or Field Manager access is required", frappe.PermissionError)


def check_master(doctype, name):
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    if doc.get("disabled"):
        frappe.throw(f"{doctype} {name} is disabled")
    if doctype == "Item" and (not doc.is_sales_item or doc.has_variants):
        frappe.throw(f"Item {name} is not a saleable item variant")
    return doc


class FieldRecord(Document):
    def autoname(self):
        try:
            self.operation_id = str(UUID(self.operation_id))
        except (ValueError, TypeError, AttributeError):
            frappe.throw("A valid operation UUID is required")
        self.name = operation_name(frappe.session.user, self.operation_id)

    def validate(self):
        require_agent()
        if not self.is_new():
            # Captured events are append-only. Only the manager conversion action can
            # add a Sales Order link; it cannot alter the captured customer or items.
            if _conversion.get() != self.name or self.doctype != "Field Order Request":
                frappe.throw("Field records are immutable. Capture a new request instead.")
            before = self.get_doc_before_save()
            protected = ("operation_id", "recorded_at", "customer", "notes", "submitted_by", "payload_hash", "owner")
            if not before or any(self.get(key) != before.get(key) for key in protected):
                frappe.throw("Conversion cannot alter captured data")
            if [(r.item_code, r.qty) for r in self.items] != [(r.item_code, r.qty) for r in before.items]:
                frappe.throw("Conversion cannot alter captured items")
            return
        kind = "visit" if self.doctype == "Field Visit" else "order"
        payload = {"customer": self.customer, "notes": self.notes or ""}
        if kind == "visit":
            payload.update(latitude=self.latitude if self.has_location else None,
                           longitude=self.longitude if self.has_location else None,
                           accuracy=self.accuracy if self.has_location else None)
        else:
            payload["items"] = [{"item_code": row.item_code, "qty": row.qty} for row in self.items]
        try:
            operation = normalize({"version": 1, "id": self.operation_id, "kind": kind,
                                   "recorded_at": self.recorded_at, "payload": payload})
        except InvalidOperation as exc:
            frappe.throw(str(exc))
        check_master("Customer", operation["payload"]["customer"])
        self.operation_id = operation["id"]
        self.recorded_at = operation["recorded_at"]
        self.customer = operation["payload"]["customer"]
        self.notes = operation["payload"]["notes"]
        if kind == "order":
            for row, clean in zip(self.items, operation["payload"]["items"]):
                check_master("Item", clean["item_code"])
                row.item_code, row.qty = clean["item_code"], clean["qty"]
            self.sales_order = None
        self.owner = frappe.session.user
        self.submitted_by = frappe.session.user
        self.payload_hash = fingerprint(operation)
