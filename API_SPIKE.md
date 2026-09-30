# API spike: load EBSCONET orders through the FOLIO Orders API

Handoff written 2026-09-30 from the session that finished the three-spreadsheet work in
`folio_ebsconet_orders`. Read this file first; it is meant to replace re-reading that
whole history. Not under git yet (by choice). Keep the spike small and cheap.

## Goal
Find out, with the smallest possible amount of work, whether creating orders directly with
`POST /orders/composite-orders` (instead of MARC + Data Import) is worth building. Decision
to reach: **go / no-go / what shape**. Do not build the full loader in the spike.

## Why
Data Import can only create basic One-Time / Pending orders. Its order mapping profile has
no `order.po.ongoing.*` fields (only `orderType`), so the existing project needs a second
step (`finish`) that PUTs each order to add the ongoing block (interval, isSubscription,
manualRenewal, renewalDate). The API can set everything at creation, and also handles
multi-line POs, product IDs and per-line detail without MARC tricks. Removed by an API
route: MARC conversion, Data Import profiles/`setup`, `folio_import`, `finish`/ongoing
conversion, empty-product-ID cleanup, `folio_add_po_lines`, `folio_retry_failed`.

## The existing project (source of reusable pieces)
WSL: `~/scratch/EBSCOnet` (GitHub `marnold-ebsco/folio_ebsconet_orders`, `main`, SSH
remote). Its `RUNBOOK.md` (workflow) and `PLAN.md` (decisions) are the short docs; read
those, not the code, first. Venv: `.venv/bin/python`; tests pytest (185), lint flake8.
Run everything through `wsl.exe -e bash -lc '...'`; write scripts to files rather than
inlining code (shell quoting breaks).

Reusable as-is or nearly (import or copy, do not rewrite):
- `pipeline/ebsconet_prep.py`: reads the SOP / returned spreadsheets, row rules
  (zero-dollar, Fee, package members, ISSN), `enrich()` (adds fund, expense class, org,
  order type, interval, location, material type, generated IDs), `order_settings()`.
  `prepare()` currently writes per-route xlsx files; an API loader needs the same enriched
  row dicts, so the spike can call `read_sops`, `classify`, `enrich` directly.
- `pipeline/folio_preflight.py`: tenant checks (funds/budgets, expense classes, orgs,
  locations, material types, acquisition method, identifier types, PO already exists).
  The lookups show how to resolve codes/names to IDs.
- `pipeline/folio_common.py` (`connect(ini)` returns a FolioClient-style client),
  `pipeline/folio_export_pols.py`, `folio_delete_orders.py`, `folio_cleanup_test_pos.py`.
- Config: `pipeline/pipeline_config.json` (columns, routes), `ebsconet_config.json`
  (library choices, `folio` section).
- Tenant ini: `~/scratch/EBSCOnet/sunflower_bugfest.ini` (credentials, git-ignored; never
  copy it into a repo). Bugfest IDs for test fund/class/org/location are in
  `~/scratch/EBSCOnet/test_data_created.json`.
- Test data: `~/scratch/EBSCOnet/out/three_type_test/filled/*.xlsx` (three filled-in
  customer spreadsheets) and `out/three_type_test/order_settings.csv`.

MARC-specific, NOT needed: `ebsconet_to_marc.py`, `folio_setup.py`, `folio_import.py`,
`folio_ongoing.py`, `folio_clean_product_ids.py`, `order_marc_headers.xlsx`.

## Conventions to keep (from the project and user rules)
- Python 3.12+, pytest, flake8; use the FOLIO-FSE `FolioClient` library for FOLIO access.
- PO number = EBSCONET order number; first line's number is `<PO>-1` (EBSCONET matches
  renewals on this). Repeated order numbers = one multi-line PO.
- Orders are created **Pending**, never opened; vendor is the EBSCONET organization
  (`folio.vendor_org_code` in the config).
- Customer columns: FOLIO Org / Fund / Expense Class / Order Type (Ongoing|One-Time) /
  Renewal Interval (Days) / Location / Material Type, with the defaults in the config.
  Ongoing block today: interval from the customer, `isSubscription` true,
  `manualRenewal` false, renewalDate = latest line `subscriptionTo`
  (see `folio_ongoing.build_ongoing`).
- Deterministic ids, if ids are ever set by us: uuid5 from FOLIO's namespace
  `8405ae4d-b315-42e1-918a-d1919900cf3f` with `"{tenant}:{recordType}:{key}"`.

## Open questions the spike must answer (in this order)
1. Can one `POST /orders/composite-orders` create a Pending order with its line AND the
   `ongoing` block (interval, isSubscription, manualRenewal, renewalDate)? Is
   `renewalDate` accepted at creation? (Expected yes; verify.)
2. Which fields must be IDs rather than codes/names: vendor, acquisitionMethod, fundId,
   expenseClassId, locationId, materialType, accessProvider, productIdType? What is the
   minimum valid payload for an electronic line, a physical line and a P/E mix line?
3. Does FOLIO assign `poLineNumber` as `<PO>-1` when we supply `poNumber`, and what
   happens with `manualPo` / `poNumber` uniqueness? Multi-line POs: include all lines
   in `compositePoLines` in one call?
4. Product IDs: ISSN plus title number with its type, and the generated `NOISSN-<order>`
   case; no empty product-ID rows (the MARC route needed a cleanup step for that).
5. Fund distribution + expense class behavior on a Pending order; any encumbrance or
   budget validation errors at creation (the ledger "restrict encumbrance" setting).
6. Electronic line details: `eresource.accessProvider`, `activated`, `userLimit`, URL
   (`resourceUrl`), createInventory `None`, and physical `createInventory`, `materialType`.
7. Throughput and error format: time per order, how errors are reported, whether a
   batch can be resumed safely (idempotency = check PO number exists first).

## Suggested spike (small; stop when questions 1-4 are answered)
1. New Python script in this folder, `spike_one_po.py`: use `enrich()` on one row of the
   test data, resolve the IDs it needs with FolioClient lookups, build one composite
   order (ongoing electronic), print the JSON, then POST it to bugfest.
2. Use an obviously-test PO number (for example `SPIKE-1`) so it can be found and
   deleted: `folio_delete_orders.py` (CSV `PO,<number>`, Pending only, `--live`).
   Do NOT use `folio_cleanup_test_pos.py` for spike orders (it works from .mrc files).
3. Repeat for a physical line, a P/E line, a One-Time line and a two-line PO.
4. Write down the minimum payloads and the errors met in `FINDINGS.md` (short).
5. Decide: go (then plan the shared package and the loader), or no-go.

## Guardrails
- Bugfest only (`sunflower_bugfest.ini`). The tenant holds 1000+ POs from other vendors;
  delete only your own spike POs. Dry-run / print the payload before every live POST.
- Never commit ini files or credentials. Do not git-init this folder until there is code
  worth keeping; when there is, decide between a new repo and a shared package that the
  existing repo also imports (keep prep/preflight free of MARC imports).
- Do not modify `folio_ebsconet_orders` during the spike; read it, import it, copy from it.

## Cost discipline for the session doing this
- Start a fresh session in `~/scratch/folio_orders` (this file is the only context).
- Use plan mode for the first pass; let an Explore/general subagent read the existing
  code and return a short summary instead of reading files in the main session.
- Read only the functions listed above, with offsets/limits. Do not read whole files.
- Trim command output (`| head`, `| tail`, `--quiet`); run single tests, not the suite.
- One question at a time: finish question 1 (one POST) before building anything else.
- Wrap up and start a new session once context passes roughly 100k tokens; write
  findings to `FINDINGS.md` first so nothing is lost.
