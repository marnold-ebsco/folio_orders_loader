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

Each row may have: `folio_field`, `legacy_field` (source column; `"Not mapped"` = none),
`fallback_legacy_field` (second column), `value` (literal), `fallback_value`, `translate`,
`description`. The source value is the first non-empty of: `legacy_field`,
`fallback_legacy_field`, `value`, `fallback_value`.

`translate` maps source values to target values (exact match first, then case-insensitive).
A value with no entry passes through unchanged and produces a **warning**, so it is easy to
see which source values the table missed. Cost accepts `$` and commas; boolean fields accept
true/yes/y/1. `product_ids[n].type` / `.value` build the line's product ID list.

A `translate` miss or an unparseable date is an **error**: `validate` fails and `load`
refuses to run until it is fixed.

Optional line fields `description` (PO line description), `receipt_status` (one of
Pending, Awaiting Receipt, Partially Received, Fully Received, Receipt Not Required, Ongoing,
Cancelled; anything else is an error) and `vendor_account` (vendorDetail.vendorAccount) are
written when present.

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
