"""Neutral input format: one dict per PO line, grouped into POs by po_number."""
import re
from collections import OrderedDict

PO_NUMBER_RE = re.compile(r"^[a-zA-Z0-9]{1,22}$")
FORMATS = ("Electronic Resource", "Physical Resource", "P/E Mix")
RECEIPT_STATUSES = ("Pending", "Awaiting Receipt", "Partially Received",
                    "Fully Received", "Receipt Not Required", "Ongoing", "Cancelled")
ORDER_TYPES = ("Ongoing", "One-Time")

REQUIRED = ("po_number", "vendor_code", "title", "order_format", "cost",
            "currency", "fund_code", "expense_class_code", "order_type",
            "acquisition_method")

# Fields that must agree on every line of one PO.
PO_LEVEL = ("vendor_code", "order_type", "interval_days", "is_subscription",
            "manual_renewal", "renewal_date")


def validate_line(line):
    """Return a list of problems with one line record (empty when valid)."""
    problems = []
    for key in REQUIRED:
        if line.get(key) in (None, ""):
            problems.append(f"missing {key}")
    po = str(line.get("po_number") or "")
    if po and not PO_NUMBER_RE.match(po):
        problems.append(f"po_number {po!r} must be 1-22 letters/digits")
    if line.get("order_format") and line["order_format"] not in FORMATS:
        problems.append(f"order_format {line['order_format']!r} not in {FORMATS}")
    if line.get("order_type") and line["order_type"] not in ORDER_TYPES:
        problems.append(f"order_type {line['order_type']!r} not in {ORDER_TYPES}")
    if line.get("receipt_status") and line["receipt_status"] not in RECEIPT_STATUSES:
        problems.append(f"receipt_status {line['receipt_status']!r} not in {RECEIPT_STATUSES}")
    fmt = line.get("order_format")
    if fmt in ("Physical Resource", "P/E Mix") and not line.get("material_type"):
        problems.append("material_type required for physical lines")
    if line.get("order_type") == "Ongoing" and not line.get("interval_days"):
        problems.append("interval_days required for Ongoing")
    return problems


def group_by_po(lines):
    """Group line records by po_number, keeping input order.

    Returns (pos, problems): pos is an OrderedDict po_number -> [lines];
    problems maps po_number -> list of messages. A PO with any problem
    should not be loaded.
    """
    pos = OrderedDict()
    for line in lines:
        pos.setdefault(str(line.get("po_number")), []).append(line)
    problems = {}
    for po, group in pos.items():
        msgs = []
        for i, line in enumerate(group, 1):
            msgs += [f"line {i}: {p}" for p in validate_line(line)]
        for key in PO_LEVEL:
            values = {str(ln.get(key)) for ln in group}
            if len(values) > 1:
                msgs.append(f"lines disagree on {key}: {sorted(values)}")
        if msgs:
            problems[po] = msgs
    return pos, problems
