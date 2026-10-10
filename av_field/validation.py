"""Pure sync contract validation, independent of Frappe and database drivers."""
import hashlib
import json
import math
from datetime import datetime, timezone
from uuid import UUID


class InvalidOperation(ValueError):
    pass


def text(value, label, required=False, maximum=5000):
    if not isinstance(value, str) or len(value) > maximum:
        raise InvalidOperation(f"{label} must be text of at most {maximum} characters")
    value = value.strip()
    if required and not value:
        raise InvalidOperation(f"{label} is required")
    return value


def number(value, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidOperation(f"{label} must be a number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise InvalidOperation(f"{label} is outside the allowed range")
    return float(value)


def normalize(operation):
    if not isinstance(operation, dict) or type(operation.get("version")) is not int or operation.get("version") != 1:
        raise InvalidOperation("Unsupported sync contract version")
    kind = operation.get("kind")
    if kind not in ("visit", "order"):
        raise InvalidOperation("Unsupported operation kind")
    try:
        operation_id = str(UUID(operation["id"]))
        recorded = datetime.fromisoformat(operation["recorded_at"].replace("Z", "+00:00"))
        if recorded.tzinfo is None:
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        raise InvalidOperation("A UUID and timezone-aware recorded_at are required") from None
    payload = operation.get("payload")
    if not isinstance(payload, dict):
        raise InvalidOperation("Payload must be an object")
    allowed = {"customer", "notes", "latitude", "longitude", "accuracy"} if kind == "visit" else {"customer", "notes", "items"}
    if set(payload) - allowed:
        raise InvalidOperation("Payload contains unsupported fields")
    clean = {"customer": text(payload.get("customer"), "Customer", True, 140),
             "notes": text(payload.get("notes", ""), "Notes")}
    if kind == "visit":
        lat, lon = payload.get("latitude"), payload.get("longitude")
        if (lat is None) != (lon is None):
            raise InvalidOperation("Latitude and longitude must be provided together")
        clean.update(latitude=None, longitude=None, accuracy=None)
        if lat is not None:
            clean["latitude"] = round(number(lat, "Latitude", -90, 90), 8)
            clean["longitude"] = round(number(lon, "Longitude", -180, 180), 8)
            clean["accuracy"] = round(number(payload.get("accuracy") if payload.get("accuracy") is not None else 0, "Accuracy", 0, 100000), 2)
        elif payload.get("accuracy") is not None:
            raise InvalidOperation("Accuracy requires coordinates")
    else:
        items = payload.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 100:
            raise InvalidOperation("An order needs 1 to 100 items")
        clean["items"] = []
        seen = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {"item_code", "qty"}:
                raise InvalidOperation("Each item needs only item_code and qty")
            code = text(item["item_code"], "Item", True, 140)
            qty = round(number(item["qty"], "Quantity", 0.000001, 1000000), 6)
            if code in seen:
                raise InvalidOperation("Combine duplicate item quantities into one row")
            seen.add(code)
            clean["items"].append({"item_code": code, "qty": qty})
    return {"version": 1, "id": operation_id, "kind": kind,
            "recorded_at": recorded.astimezone(timezone.utc).isoformat(), "payload": clean}


def operation_name(user, operation_id):
    return "FIELD-" + hashlib.sha256(f"{user}:{operation_id}".encode()).hexdigest()


def fingerprint(operation):
    return hashlib.sha256(json.dumps(operation, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
