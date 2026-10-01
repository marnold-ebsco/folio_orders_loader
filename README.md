# folio_orders_loader

Creates **Pending** purchase orders (with their lines) in FOLIO from a delimited file, using
one `POST /orders/composite-orders` per PO. No MARC or Data Import is involved.

```
python -m folio_orders_loader template --out map.json     # blank mapping file
python -m folio_orders_loader validate data.tsv --mapping map.json --ini tenant.ini
python -m folio_orders_loader load data.tsv --mapping map.json --ini tenant.ini          # dry run
python -m folio_orders_loader load data.tsv --mapping map.json --ini tenant.ini --live   # POST
python -m folio_orders_loader export PO1 PO2 --ini tenant.ini --out pos.json
python -m folio_orders_loader delete to_delete.csv --ini tenant.ini [--live]
```

* `load` is a **dry run unless `--live`**. Re-running is safe: POs that already exist are skipped.
* `validate` never POSTs. It checks the map, the data (PO number format, required fields,
  lines of one PO agreeing on PO-level fields) and, with `--ini`, that every vendor, fund,
  expense class, location, material type, identifier type and acquisition method resolves.
* `--delimiter` (e.g. `\t`) and `--encoding` override the map's `reader` settings.
* `delete` only removes **Pending** orders, saves each as JSON in `--backup-dir` first, and
  refuses lists longer than `--max`. CSV columns: `type,number,note` (`PO` or `POL`).
* The `.ini` file holds `okapiUrl`, `tenant_id`, `username`, `password`, `sslVerify`. Never commit
  a filled-in one.
* PO numbers must match `^[a-zA-Z0-9]{1,22}$`. Lines sharing a `po_number` form one PO.

## Mapping file

A mapping file is required for file input. It uses the folio-migration-mapper row format, but
`folio_field` holds this tool's **neutral keys** (run `template` for the full list; required
ones are marked `REQUIRED`).

```json
{"reader": {"delimiter": "\t", "encoding": "utf-8-sig"},
 "data": [
   {"folio_field": "po_number", "legacy_field": "Order No"},
   {"folio_field": "vendor_code", "legacy_field": "Vendor",
    "translate": {"Acme Books": "ACME"}},
   {"folio_field": "currency", "legacy_field": "Cur", "fallback_value": "USD"},
   {"folio_field": "product_ids[0].type", "value": "ISSN"},
   {"folio_field": "product_ids[0].value", "legacy_field": "ISSN"}
 ]}
```

`product_ids[n].type` must be an identifier type name that exists in the tenant (for example
`ISSN`, `ISBN`, `Local identifier`; there is no "Title number" type). Add `product_ids[1]`
for a second ID such as a title number.

Each row may have: `folio_field`, `legacy_field` (source column; `"Not mapped"` = none),
`fallback_legacy_field` (second column), `value` (literal), `fallback_value`, `translate`,
`description`. The source value is the first non-empty of: `legacy_field`,
`fallback_legacy_field`, `value`, `fallback_value`.

`translate` maps source values to target values (exact match first, then case-insensitive).
A value with no entry passes through unchanged and produces a **warning**, so it is easy to
see which source values the table missed. Cost accepts `$` and commas; boolean fields accept
true/yes/y/1. `product_ids[n].type` / `.value` build the line's product ID list.

### Several funds, several locations, quantity and cost extras

- `fund_code` + `expense_class_code` remain the one-fund shorthand (100%). For several funds map
  `fund_distribution[n].code`, `.expense_class_code` (falls back to the line's
  `expense_class_code`), `.value` and `.type` (`percentage` default, or `amount`). Percentages
  must add to 100; `$` and commas are accepted in `.value`.
- `quantity_physical` / `quantity_electronic` set the copies (default 1 for each format the line
  has). `locations[n].code`, `.quantity_physical`, `.quantity_electronic` give several locations;
  their quantities must add up to the line quantities (a single location defaults to the line
  quantities). Use `location_code` for the one-location shorthand, not both.
- `discount` with `discount_type` (`amount` default, or `percentage`), `additional_cost` and
  `exchange_rate` go on the cost block. `cost` stays the list unit price.

### Bibliographic fields

`edition` and `publication_date` (free text, sent as is). `contributors[n].name` and `.type`
build the contributor list; `.type` must be a contributor name type name in the tenant (for
example `Personal name`, `Corporate name`, `Meeting name`).

### People, flags and line tags

`line_tags` (`|`-separated list or a list; goes to the PO line's `tags.tagList`, unlike `tags`,
which is PO level), `requester` and `selector` (free text), `rush` (boolean, true/yes/y/1).

### Electronic and receiving extras

Electronic lines: `resource_url`, `user_limit` (text), `trial` (boolean). Physical lines:
`volumes` (`|`-separated list), `material_supplier_code` (organization code) and
`expected_receipt_date`. Any line: `receiving_note`, `is_acknowledged` (boolean),
`subscription_interval` (days), `receipt_date`, `renewal_note`,
`cancellation_restriction_note`, and `product_ids[n].qualifier`. The two date fields accept
`date_format` and are sent as midnight UTC date-times.

### Other line flags and links

Booleans: `automatic_export`, `collection`, `suppress_from_discovery`, `multi_year_payment`,
`claiming_active`, `is_package`. `claiming_interval` (days), `donor` (text),
`donor_organization_codes` (`|`-separated organization codes), and the UUIDs `instance_id`,
`agreement_id`, `package_po_line_id` (not looked up). Payment terms and custom fields are not
supported.

A `translate` miss or an unparseable date is an **error**: `validate` fails and `load`
refuses to run until it is fixed.

Optional line fields `description` (PO line description), `receipt_status` (one of
Pending, Awaiting Receipt, Partially Received, Fully Received, Receipt Not Required, Ongoing,
Cancelled; anything else is an error) and `vendor_account` (vendorDetail.vendorAccount) are
written when present.

PO-level optional fields (must agree on every line of a PO): `notes` and `tags` (a list, or one
string with items separated by `|`), and `bill_to` / `ship_to` (the address UUID from the
tenant's address settings; names are not looked up).

Also optional: `payment_status` (one of Awaiting Payment, Cancelled, Fully Paid, Partially Paid,
Payment Not Required, Pending, Ongoing) and a vendor reference number, given as
`vendor_reference_number` plus `vendor_reference_type` (one of Vendor continuation reference
number, Vendor order reference number, Vendor subscription reference number, Vendor internal
number, Vendor title number), written to `vendorDetail.referenceNumbers`. The type is required
with the number. "Vendor title number" is the place for a vendor's title number if you do not
want it as a product ID.

`date_format` (date fields only: `renewal_date`, `subscription_from`, `subscription_to`) is a
Python strptime pattern that converts the source value to ISO `YYYY-MM-DD`, e.g.
`{"folio_field": "subscription_to", "legacy_field": "End", "date_format": "%m/%d/%Y"}`.
Without it the value must already be ISO.

`rules` is an optional list of transforms applied in order, before `translate`:

| op | keys | effect |
| --- | --- | --- |
| `split` | `sep` (default `,`), `index` (default 0) | keep one part of the value |
| `combine` | `fields` (columns), `sep` (default space) | join source columns, replacing the value |
| `strip_prefix` / `strip_suffix` | `text` | remove it if present |
| `upper` / `lower` | | change case |

```json
{"folio_field": "fund_code", "legacy_field": "Fund",
 "rules": [{"op": "strip_prefix", "text": "X-"}, {"op": "upper"}]}
```

## Development

```
python -m venv .venv && .venv/bin/pip install -e .[dev]
.venv/bin/python -m pytest tests -q
.venv/bin/flake8 --max-line-length=100 folio_orders_loader tests
```
