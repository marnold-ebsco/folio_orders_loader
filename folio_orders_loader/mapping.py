"""Map customer delimited files to neutral line records (see records.py).

Map file format (mapper-style rows, neutral keys in ``folio_field``)::

    {"reader": {"delimiter": "\\t", "encoding": "utf-8-sig"},
     "data": [{"folio_field": "vendor_code", "legacy_field": "Vendor",
               "translate": {"Acme Books": "ACME"}}, ...]}

Per field the source value is the first non-empty of: ``legacy_field``
column, ``fallback_legacy_field`` column, ``value``, ``fallback_value``.
Then ``translate`` (exact, then case-insensitive) is applied; a value
with no match is an error. ``rules`` is an optional list of transforms run
before ``translate``: ``{"op": "split", "sep": ";", "index": 0}``,
``{"op": "combine", "fields": ["A", "B"], "sep": " "}`` (joins source
columns, replacing the value), ``{"op": "strip_prefix"|"strip_suffix",
"text": "..."}``, ``{"op": "upper"|"lower"}``. ``date_format`` (a strptime
pattern such as ``%m/%d/%Y``) converts date fields to ISO ``YYYY-MM-DD``.
"""
import csv
import json
import re
from datetime import datetime

from .records import REQUIRED

OPTIONAL = ("interval_days", "is_subscription", "manual_renewal",
            "renewal_date", "subscription_from", "subscription_to",
            "publisher", "cancellation_restriction", "access_provider_code",
            "location_code", "material_type", "description", "receipt_status",
            "vendor_account")
BOOLEAN = ("is_subscription", "manual_renewal", "cancellation_restriction")
PRODUCT_ID_RE = re.compile(r"^product_ids\[(\d+)\]\.(type|value)$")
ROW_KEYS = ("folio_field", "legacy_field", "value", "description",
            "fallback_legacy_field", "fallback_value", "translate",
            "rules", "rules_apply_scope", "date_format")
DATES = ("renewal_date", "subscription_from", "subscription_to")
RULE_OPS = ("split", "combine", "strip_prefix", "strip_suffix", "upper", "lower")
NOT_MAPPED = "Not mapped"
DEFAULT_READER = {"delimiter": "\t", "encoding": "utf-8-sig"}


def known_field(name):
    return name in REQUIRED or name in OPTIONAL or bool(PRODUCT_ID_RE.match(name))


def _describe(name):
    if name in REQUIRED:
        return "REQUIRED"
    if name in DATES:
        return 'optional "date_format": "%m/%d/%Y" converts to ISO'
    return ""


def template():
    """Blank map with every known neutral key unmapped."""
    names = list(REQUIRED) + list(OPTIONAL) + [
        "product_ids[0].type", "product_ids[0].value"]
    return {"reader": dict(DEFAULT_READER), "data": [
        {"folio_field": n, "legacy_field": NOT_MAPPED, "value": "",
         "description": _describe(n)} for n in names]}


def load_map(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def check_map(mapping):
    """Return problems with the map itself (empty when usable)."""
    problems = []
    rows = mapping.get("data")
    if not isinstance(rows, list):
        return ["map needs a top-level 'data' list"]
    seen = set()
    for i, row in enumerate(rows, 1):
        name = row.get("folio_field")
        if not name:
            problems.append(f"row {i}: missing folio_field")
            continue
        if not known_field(name):
            problems.append(f"row {i}: unknown folio_field {name!r}")
        if name in seen:
            problems.append(f"row {i}: duplicate folio_field {name!r}")
        seen.add(name)
        for key in row:
            if key not in ROW_KEYS:
                problems.append(f"row {i} ({name}): unexpected key {key!r}")
        for rule in row.get("rules") or []:
            if not isinstance(rule, dict) or rule.get("op") not in RULE_OPS:
                problems.append(f"row {i} ({name}): bad rule {rule!r}")
        if row.get("date_format"):
            if name not in DATES:
                problems.append(f"row {i} ({name}): date_format on a non-date field")
            else:
                try:
                    datetime.strptime(datetime(2000, 1, 2).strftime(
                        row["date_format"]), row["date_format"])
                except ValueError:
                    problems.append(f"row {i} ({name}): bad date_format")
    for name in REQUIRED:
        row = next((r for r in rows if r.get("folio_field") == name), None)
        if row is None or not _has_source(row):
            problems.append(f"required field {name!r} is not mapped")
    return problems


def _has_source(row):
    legacy = row.get("legacy_field")
    return bool((legacy and legacy != NOT_MAPPED)
                or row.get("fallback_legacy_field")
                or row.get("value") not in (None, "")
                or row.get("fallback_value") not in (None, ""))


def read_rows(path, reader=None):
    """Yield each data row of a delimited file as a dict keyed by header."""
    opts = {**DEFAULT_READER, **(reader or {})}
    with open(path, newline="", encoding=opts["encoding"]) as fh:
        yield from csv.DictReader(fh, delimiter=opts["delimiter"])


def _cell(row, column):
    if not column or column == NOT_MAPPED:
        return ""
    return (row.get(column) or "").strip()


def _source_value(spec, row):
    for value in (_cell(row, spec.get("legacy_field")),
                  _cell(row, spec.get("fallback_legacy_field"))):
        if value:
            return value
    for literal in (spec.get("value"), spec.get("fallback_value")):
        if literal not in (None, ""):
            return literal
    return ""


def _apply_rules(spec, value, row):
    for rule in spec.get("rules") or []:
        op = rule["op"]
        if op == "combine":
            cells = [_cell(row, c) for c in rule.get("fields", [])]
            value = rule.get("sep", " ").join(c for c in cells if c)
            continue
        if not isinstance(value, str):
            continue
        text = rule.get("text", "")
        if op == "split":
            parts = value.split(rule.get("sep", ","))
            idx = rule.get("index", 0)
            value = parts[idx].strip() if -len(parts) <= idx < len(parts) else ""
        elif op == "strip_prefix":
            value = value[len(text):] if text and value.startswith(text) else value
        elif op == "strip_suffix":
            value = value[:-len(text)] if text and value.endswith(text) else value
        elif op == "upper":
            value = value.upper()
        elif op == "lower":
            value = value.lower()
    return value


def _to_iso(name, spec, value):
    """Return (value, error) with dates converted by spec['date_format']."""
    if name not in DATES or not isinstance(value, str):
        return value, None
    fmt = spec.get("date_format") or "%Y-%m-%d"
    try:
        return datetime.strptime(value, fmt).date().isoformat(), None
    except ValueError:
        return value, f"{name}: {value!r} is not a date in {fmt}"


def _translate(spec, value):
    table = spec.get("translate")
    if not table or not isinstance(value, str):
        return value, None
    if value in table:
        return table[value], None
    folded = {k.casefold(): v for k, v in table.items()}
    if value.casefold() in folded:
        return folded[value.casefold()], None
    return value, f"{spec['folio_field']}: no translation for {value!r}"


def _coerce(name, value):
    if name in BOOLEAN and isinstance(value, str):
        return value.strip().casefold() in ("true", "yes", "y", "1")
    if name == "cost" and isinstance(value, str):
        return value.replace("$", "").replace(",", "")
    return value


def map_row(mapping, row):
    """Return (line_record, errors) for one source row.

    Errors are translation misses and unparseable dates; the line is still
    returned so callers decide whether to stop.
    """
    line, errors, ids = {}, [], {}
    for spec in mapping["data"]:
        name = spec["folio_field"]
        value = _apply_rules(spec, _source_value(spec, row), row)
        value, err = _translate(spec, value)
        if err:
            errors.append(err)
        if value not in ("", None):
            value, err = _to_iso(name, spec, value)
            if err:
                errors.append(err)
        if value in ("", None):
            continue
        match = PRODUCT_ID_RE.match(name)
        if match:
            ids.setdefault(int(match.group(1)), {})[match.group(2)] = value
        else:
            line[name] = _coerce(name, value)
    if ids:
        line["product_ids"] = [ids[i] for i in sorted(ids)]
    return line, errors


def map_file(mapping, path):
    """Map a whole file. Returns (lines, errors) with 'row N:' prefixes."""
    lines, errors = [], []
    for n, row in enumerate(read_rows(path, mapping.get("reader")), 2):
        line, errs = map_row(mapping, row)
        lines.append(line)
        errors += [f"row {n}: {e}" for e in errs]
    return lines, errors
