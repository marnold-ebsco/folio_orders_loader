"""Neutral input format: one dict per PO line, grouped into POs by po_number."""
import re
from collections import OrderedDict

PO_NUMBER_RE = re.compile(r"^[a-zA-Z0-9]{1,22}$")
FORMATS = ("Electronic Resource", "Physical Resource", "P/E Mix")
RECEIPT_STATUSES = ("Pending", "Awaiting Receipt", "Partially Received",
                    "Fully Received", "Receipt Not Required", "Ongoing", "Cancelled")
PAYMENT_STATUSES = ("Awaiting Payment", "Cancelled", "Fully Paid", "Partially Paid",
                    "Payment Not Required", "Pending", "Ongoing")
REFERENCE_TYPES = ("Vendor continuation reference number", "Vendor order reference number",
                   "Vendor subscription reference number", "Vendor internal number",
                   "Vendor title number")
ORDER_TYPES = ("Ongoing", "One-Time")

REQUIRED = ("po_number", "vendor_code", "title", "order_format", "cost",
            "currency", "order_type", "acquisition_method")
# Single-fund shorthand; replaced by fund_distribution[n] for several funds.
FUND_FIELDS = ("fund_code", "expense_class_code")
DISTRIBUTION_TYPES = ("percentage", "amount")
DISCOUNT_TYPES = ("amount", "percentage")
# Repeating groups: name -> sub-keys (neutral records hold a list of dicts).
REPEATING = {
    "product_ids": ("type", "value", "qualifier"),
    "fund_distribution": ("code", "expense_class_code", "value", "type"),
    "locations": ("code", "quantity_physical", "quantity_electronic"),
    "contributors": ("name", "type"),
}

# Fields that must agree on every line of one PO.
PO_LEVEL = ("vendor_code", "order_type", "interval_days", "is_subscription",
            "manual_renewal", "renewal_date", "notes", "tags", "bill_to", "ship_to")
LINE_FLAGS = (("automatic_export", "automaticExport"), ("collection", "collection"),
              ("suppress_from_discovery", "suppressInstanceFromDiscovery"),
              ("multi_year_payment", "multiYearPayment"),
              ("claiming_active", "claimingActive"), ("is_package", "isPackage"))
LINE_UUIDS = (("instance_id", "instanceId"), ("agreement_id", "agreementId"),
              ("package_po_line_id", "packagePoLineId"))
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fund_list(line):
    """Fund distribution as dicts with code, expense_class_code, value, type."""
    dist = line.get("fund_distribution")
    if not dist:
        return [{"code": line.get("fund_code"),
                 "expense_class_code": line.get("expense_class_code"),
                 "value": 100, "type": "percentage"}]
    return [{"code": d.get("code"),
             "expense_class_code": d.get("expense_class_code")
             or line.get("expense_class_code"),
             "value": d.get("value", 100 if len(dist) == 1 else None),
             "type": d.get("type") or "percentage"} for d in dist]


def quantities(line):
    """(physical, electronic) copies for the line; 1 for each format it has."""
    fmt = line.get("order_format")
    phys = fmt in ("Physical Resource", "P/E Mix")
    elec = fmt in ("Electronic Resource", "P/E Mix")
    return (int(_number(line.get("quantity_physical")) or 1) if phys else 0,
            int(_number(line.get("quantity_electronic")) or 1) if elec else 0)


def location_list(line):
    """Locations as dicts with code, quantity_physical, quantity_electronic."""
    phys, elec = quantities(line)
    locs = line.get("locations")
    if not locs:
        if not line.get("location_code"):
            return []
        return [{"code": line["location_code"], "quantity_physical": phys,
                 "quantity_electronic": elec}]
    only = len(locs) == 1
    return [{"code": loc.get("code"),
             "quantity_physical": int(_number(loc.get("quantity_physical"))
                                      or (phys if only else 0)),
             "quantity_electronic": int(_number(loc.get("quantity_electronic"))
                                        or (elec if only else 0))}
            for loc in locs]


def _check_funds(line, problems):
    if not line.get("fund_distribution") and not all(
            line.get(k) for k in FUND_FIELDS):
        problems.append("missing fund_code/expense_class_code "
                        "(or fund_distribution)")
        return
    funds = fund_list(line)
    for i, f in enumerate(funds):
        if not f["code"]:
            problems.append(f"fund_distribution[{i}]: missing code")
        if not f["expense_class_code"]:
            problems.append(f"fund_distribution[{i}]: missing expense_class_code")
        if f["type"] not in DISTRIBUTION_TYPES:
            problems.append(f"fund_distribution[{i}]: type {f['type']!r} "
                            f"not in {DISTRIBUTION_TYPES}")
        if _number(f["value"]) is None:
            problems.append(f"fund_distribution[{i}]: value {f['value']!r} "
                            "is not a number")
    values = [_number(f["value"]) for f in funds]
    if ({f["type"] for f in funds} == {"percentage"} and None not in values
            and abs(sum(values) - 100) > 0.001):
        problems.append(f"fund percentages add to {sum(values):g}, not 100")


def _check_quantities(line, problems):
    for key in ("quantity_physical", "quantity_electronic"):
        n = _number(line.get(key)) if line.get(key) not in (None, "") else 1
        if n is None or n < 1 or n != int(n):
            problems.append(f"{key} {line[key]!r} must be a whole number of 1 or more")
            return
    for key in ("discount", "additional_cost", "exchange_rate"):
        if line.get(key) not in (None, "") and _number(line[key]) is None:
            problems.append(f"{key} {line[key]!r} is not a number")
    if line.get("discount_type"):
        if line["discount_type"] not in DISCOUNT_TYPES:
            problems.append(f"discount_type {line['discount_type']!r} "
                            f"not in {DISCOUNT_TYPES}")
        if line.get("discount") in (None, ""):
            problems.append("discount_type given without discount")
    if line.get("locations"):
        if line.get("location_code"):
            problems.append("use locations[n] or location_code, not both")
        locs = location_list(line)
        phys, elec = quantities(line)
        for label, want, have in (
                ("physical", phys, sum(x["quantity_physical"] for x in locs)),
                ("electronic", elec, sum(x["quantity_electronic"] for x in locs))):
            if want != have:
                problems.append(f"location {label} quantities add to {have}, "
                                f"line quantity is {want}")


def validate_line(line):
    """Return a list of problems with one line record (empty when valid)."""
    problems = []
    _check_funds(line, problems)
    _check_quantities(line, problems)
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
    if line.get("payment_status") and line["payment_status"] not in PAYMENT_STATUSES:
        problems.append(f"payment_status {line['payment_status']!r} not in {PAYMENT_STATUSES}")
    if line.get("vendor_reference_number"):
        ref_type = line.get("vendor_reference_type")
        if ref_type not in REFERENCE_TYPES:
            problems.append(f"vendor_reference_type {ref_type!r} not in {REFERENCE_TYPES}")
    elif line.get("vendor_reference_type"):
        problems.append("vendor_reference_type given without vendor_reference_number")
    if line.get("subscription_interval") not in (None, ""):
        n = _number(line["subscription_interval"])
        if n is None or n < 0 or n != int(n):
            problems.append("subscription_interval must be a whole number of days")
    for i, c in enumerate(line.get("contributors") or []):
        if not c.get("name"):
            problems.append(f"contributors[{i}]: missing name")
        if not c.get("type"):
            problems.append(f"contributors[{i}]: missing type")
    if line.get("claiming_interval") not in (None, ""):
        n = _number(line["claiming_interval"])
        if n is None or n < 0 or n != int(n):
            problems.append("claiming_interval must be a whole number of days")
    for key in ("bill_to", "ship_to") + tuple(k for k, _ in LINE_UUIDS):
        if line.get(key) and not UUID_RE.match(str(line[key])):
            problems.append(f"{key} {line[key]!r} must be an address UUID")
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
