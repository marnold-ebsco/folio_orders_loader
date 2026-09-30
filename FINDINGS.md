# Findings: EBSCONET orders via POST /orders/composite-orders

Tested 2026-09-30 on sunflower bugfest with `spike_one_po.py` (dry run by default, `--live`
to POST). Test data: `EBSCOnet/out/three_type_test/filled/*.xlsx`, rows run through the
existing `classify()` / `enrich()`.

## Verdict: GO
One POST creates a Pending PO with its lines and the full ongoing block. No MARC, Data
Import, `finish` step or empty-product-ID cleanup is needed.

## Results (all created Pending)
| PO | Case | Result |
|----|------|--------|
| SPIKE1 | Ongoing, electronic | OK; `ongoing` (interval, isSubscription, manualRenewal, renewalDate) saved; line `SPIKE1-1` |
| SPIKE2 | Ongoing, physical (location + material type) | OK; `SPIKE2-1` |
| SPIKE3 | Ongoing, P/E mix | OK; `SPIKE3-1` |
| SPIKE4 | One-Time, electronic | OK; `SPIKE4-1` |
| SPIKE5 | One-Time, physical | OK; `SPIKE5-1` |
| SPIKE6 | Two-line PO (2 lines in one POST) | OK; lines `SPIKE6-1`, `SPIKE6-2` |

## Rules learned
- `poNumber` must match `^[a-zA-Z0-9]{1,22}$`: no hyphens. EBSCONET numbers (`M2822798`)
  are fine. FOLIO assigns `poLineNumber` = `<PO>-<n>` automatically, in order given.
- Cost fields are `listUnitPriceElectronic` / `listUnitPrice` (not `listPrice*`), with
  `quantityElectronic` / `quantityPhysical`. `poLineEstimatedPrice` is computed.
- IDs required (resolved by lookup): vendor org (code), acquisitionMethod (by `value`),
  `fundDistribution[].fundId` + `code` + `expenseClassId`, `productIdType`, `locationId`,
  material type (physical/P-E), `eresource.accessProvider` (vendor org id).
- Dates accepted as `YYYY-MM-DD`, stored as `...T00:00:00.000+00:00`.
- Generated `NOISSN-<order>` product ID with type "Local identifier" saves fine; we only
  send one product ID, so there are no empty ones.
- Minimum line: titleOrPackage, acquisitionMethod, orderFormat, source "User",
  checkinItems false, fundDistribution, cost{currency, list price, quantity},
  details.productIds, publisher; `eresource{createInventory "None", accessProvider,
  activated false}` for electronic/P-E; `physical{createInventory "None"}` for
  physical/P-E; `locations[]` when a location applies.
- Errors arrive as HTTP 422 with a clear per-field message (FolioValidationError).

## Not yet checked
- Throughput on a large batch; resume/idempotency (script checks PO number exists first).
- Budget/encumbrance errors (restrictEncumbrance) on an over-budget fund.
- Electronic `resourceUrl`, `userLimit`; `manualPo`; printed/receipt status fields
  (`receiptStatus` per route in the config); account number / payment method.
- Lines with ISSN as well as title number (this spike sent only the title number).

## Cleanup
Spike POs SPIKE1..SPIKE6 are on bugfest, Pending. Delete with
`folio_delete_orders.py` (CSV `type,number,note`; `PO,SPIKE1` ...; `--live`).
