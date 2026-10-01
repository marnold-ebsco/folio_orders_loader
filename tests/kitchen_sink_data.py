"""Kitchen-sink fixture for folio_orders_loader: one synthetic PO per behavior.

Standalone, deterministic generator, in the spirit of marc_repair's
build_kitchen_sink.py. All data is invented (PO numbers KS..., vendor codes,
funds, titles); nothing is derived from real orders.

Outputs (in tests/fixtures/):
    kitchen_sink.tsv        one row per PO line, tab delimited, UTF-8 BOM
    kitchen_sink_map.json   mapping file for it (exercises translate, rules,
                            date_format, repeating groups, booleans, money)

EXPECTED maps each PO number to the status ``load(live=True)`` must return
against the fake client in test_kitchen_sink.py. Numbering: KS0xx valid,
KS1xx rejected by validation ('invalid'), KS2xx mapping errors, KS3xx tenant
lookup failure, KS4xx already exists, KS5xx FOLIO rejects the POST.

Run: python tests/kitchen_sink_data.py
"""
import csv
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

COLUMNS = [
    "PO", "Vendor", "Title", "Format", "Cost", "Currency", "Fund", "ExpClass",
    "Fund1", "Exp1", "Pct1", "Fund2", "Exp2", "Pct2", "OrderType", "Interval",
    "Method", "MatType", "Loc", "L1", "L1p", "L1e", "L2", "L2p", "L2e", "QtyP",
    "QtyE", "ISSN", "SubTo", "RcptDate", "RcptStatus", "PayStatus", "Notes",
    "Tags", "BillTo", "Prefix", "Contrib1", "Contrib1Type", "Contrib2",
    "Contrib2Type", "Url", "Volumes", "Rush"]

BASE = {
    "Vendor": "ACME", "Title": "A Synthetic Title", "Format": "Online",
    "Cost": "100.00", "Currency": "USD", "Fund": "TEST-ELEC", "ExpClass": "GEN",
    "OrderType": "Sub", "Interval": "365", "Method": "Purchase",
    "ISSN": "1234-5678", "SubTo": "2026-12-31"}

# (PO number, expected status, what it proves, [row overrides, ...])
CASES = [
    ("KS001", "created", "minimal electronic ongoing PO", [{}]),
    ("KS002", "created", "physical one-time with location and material type",
     [{"Format": "Print", "OrderType": "Mono", "Interval": "", "SubTo": "",
       "Fund": "TEST-PRINT", "MatType": "journal", "Loc": "MAIN"}]),
    ("KS003", "created", "multi-line P/E Mix PO; money with $ and commas",
     [{"Format": "Mix", "Cost": "$1,234.50", "MatType": "journal", "Loc": "MAIN",
       "Title": "Line one"},
      {"Format": "Mix", "Cost": "$2,000.00", "MatType": "journal", "Loc": "MAIN",
       "Title": "Line two"}]),
    ("KS004", "created", "two funds 60/40, two locations, two contributors",
     [{"Format": "Mix", "Fund": "", "ExpClass": "", "Fund1": "TEST-ELEC",
       "Exp1": "GEN", "Pct1": "60", "Fund2": "TEST-PRINT", "Exp2": "GEN",
       "Pct2": "40", "MatType": "journal", "QtyP": "2", "QtyE": "1",
       "L1": "MAIN", "L1p": "1", "L1e": "1", "L2": "BRANCH", "L2p": "1",
       "L2e": "0", "Contrib1": "Doe, Jane", "Contrib1Type": "Personal name",
       "Contrib2": "Example Press", "Contrib2Type": "Corporate name"}]),
    ("KS005", "created", "translate is case-insensitive; date_format; "
     "strip_prefix + upper rules on fund",
     [{"Format": "ONLINE", "Fund": "x-test-elec", "RcptDate": "03/04/2026",
       "RcptStatus": "Pending", "PayStatus": "Pending"}]),
    ("KS006", "created", "PO-level notes, tags, address by name, prefix",
     [{"Notes": "first note|second note", "Tags": "alpha|beta",
       "BillTo": "Main Library", "Prefix": "KS"}]),
    ("KS007", "created", "boolean coercion and electronic-only keys",
     [{"Rush": "yes", "Url": "https://example.org/ks007"}]),
    ("KS008", "created", "physical-only keys on a physical line",
     [{"Format": "Print", "OrderType": "Mono", "Interval": "", "SubTo": "",
       "Fund": "TEST-PRINT", "MatType": "journal", "Volumes": "v.1|v.2"}]),

    ("KS101", "invalid", "missing title", [{"Title": ""}]),
    ("KS-102", "invalid", "PO number with a character outside letters/digits",
     [{}]),
    ("KS103", "invalid", "fund percentages add to 90",
     [{"Fund": "", "ExpClass": "", "Fund1": "TEST-ELEC", "Exp1": "GEN",
       "Pct1": "50", "Fund2": "TEST-PRINT", "Exp2": "GEN", "Pct2": "40"}]),
    ("KS104", "invalid", "location quantities do not match line quantity",
     [{"Format": "Print", "OrderType": "Mono", "Interval": "", "SubTo": "",
       "MatType": "journal", "QtyP": "3", "L1": "MAIN", "L1p": "1"}]),
    ("KS105", "invalid", "electronic-only key (Url) on a Physical line",
     [{"Format": "Print", "OrderType": "Mono", "Interval": "", "SubTo": "",
       "MatType": "journal", "Loc": "MAIN", "Url": "https://example.org"}]),
    ("KS106", "invalid", "Ongoing order without an interval",
     [{"Interval": ""}]),
    ("KS107", "invalid", "receipt_status outside the allowed list",
     [{"RcptStatus": "Maybe Later"}]),
    ("KS108", "invalid", "lines of one PO disagree on vendor",
     [{"Vendor": "ACME"}, {"Vendor": "OTHERCO"}]),
    ("KS109", "invalid", "physical line without a material type",
     [{"Format": "Print", "OrderType": "Mono", "Interval": "", "SubTo": "",
       "Loc": "MAIN"}]),
    ("KS110", "invalid", "payment_status outside the allowed list",
     [{"PayStatus": "Paid-ish"}]),

    ("KS201", "map-error", "translate miss on Format",
     [{"Format": "Carrier pigeon"}]),
    ("KS202", "map-error", "unparseable date", [{"RcptDate": "31/31/2026"}]),

    ("KS301", "lookup-failed", "vendor code the tenant does not have",
     [{"Vendor": "NOSUCHVENDOR"}]),

    ("KS401", "exists", "PO already in FOLIO is skipped", [{}]),

    ("KS501", "error", "FOLIO rejects the POST; the run continues", [{}]),
]

EXPECTED = {po: status for po, status, _, _ in CASES}
MAP_ERROR_POS = {po for po, status, _, _ in CASES if status == "map-error"}
EXISTING = {"KS401"}
REJECTED = {"KS501"}


def rows():
    for po, _, _, overrides in CASES:
        for over in overrides:
            row = dict.fromkeys(COLUMNS, "")
            row.update(BASE)
            row.update(over)
            row["PO"] = po
            yield row


def _direct(folio_field, column, **extra):
    return dict(folio_field=folio_field, legacy_field=column, **extra)


def build_map():
    data = [
        _direct("po_number", "PO"),
        _direct("vendor_code", "Vendor"),
        _direct("title", "Title"),
        _direct("order_format", "Format", translate={
            "Online": "Electronic Resource", "Print": "Physical Resource",
            "Mix": "P/E Mix"}),
        _direct("cost", "Cost"),
        _direct("currency", "Currency"),
        _direct("fund_code", "Fund", rules=[
            {"op": "strip_prefix", "text": "x-"}, {"op": "upper"}]),
        _direct("expense_class_code", "ExpClass"),
        _direct("fund_distribution[0].code", "Fund1"),
        _direct("fund_distribution[0].expense_class_code", "Exp1"),
        _direct("fund_distribution[0].value", "Pct1"),
        _direct("fund_distribution[1].code", "Fund2"),
        _direct("fund_distribution[1].expense_class_code", "Exp2"),
        _direct("fund_distribution[1].value", "Pct2"),
        _direct("order_type", "OrderType",
                translate={"Sub": "Ongoing", "Mono": "One-Time"}),
        _direct("interval_days", "Interval"),
        _direct("acquisition_method", "Method", translate={
            "Purchase": "Purchase At Vendor System"}),
        _direct("material_type", "MatType"),
        _direct("location_code", "Loc"),
        _direct("locations[0].code", "L1"),
        _direct("locations[0].quantity_physical", "L1p"),
        _direct("locations[0].quantity_electronic", "L1e"),
        _direct("locations[1].code", "L2"),
        _direct("locations[1].quantity_physical", "L2p"),
        _direct("locations[1].quantity_electronic", "L2e"),
        _direct("quantity_physical", "QtyP"),
        _direct("quantity_electronic", "QtyE"),
        _direct("product_ids[0].value", "ISSN"),
        dict(folio_field="product_ids[0].type", legacy_field="Not mapped",
             value="ISSN"),
        _direct("subscription_to", "SubTo", date_format="%Y-%m-%d"),
        _direct("receipt_date", "RcptDate", date_format="%m/%d/%Y"),
        _direct("receipt_status", "RcptStatus"),
        _direct("payment_status", "PayStatus"),
        _direct("notes", "Notes"),
        _direct("tags", "Tags"),
        _direct("bill_to", "BillTo"),
        _direct("po_number_prefix", "Prefix"),
        _direct("contributors[0].name", "Contrib1"),
        _direct("contributors[0].type", "Contrib1Type"),
        _direct("contributors[1].name", "Contrib2"),
        _direct("contributors[1].type", "Contrib2Type"),
        _direct("resource_url", "Url"),
        _direct("volumes", "Volumes"),
        _direct("rush", "Rush"),
    ]
    return {"reader": {"delimiter": "\t", "encoding": "utf-8-sig"}, "data": data}


def write_tsv(path):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter="\t",
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows())


def write_map(path):
    Path(path).write_text(json.dumps(build_map(), indent=2) + "\n",
                          encoding="utf-8")


def main():
    FIXTURES.mkdir(exist_ok=True)
    write_tsv(FIXTURES / "kitchen_sink.tsv")
    write_map(FIXTURES / "kitchen_sink_map.json")
    print("wrote", FIXTURES / "kitchen_sink.tsv", "and kitchen_sink_map.json")


if __name__ == "__main__":
    main()
