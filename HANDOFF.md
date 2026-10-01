# Handoff (2026-09-30): continue building folio_orders_loader

Read `FINDINGS.md` (spike results, verdict GO) and the approved plan
`C:\Users\marnold\.claude\plans\idempotent-crafting-rivest.md`. `API_SPIKE.md` is the original brief.
**We work in Linux (WSL Ubuntu), not Windows.** Work in WSL `~/scratch/folio_orders` (run via `wsl.exe -e bash -lc`; write files through the
`\\wsl.localhost\Ubuntu-24.04\home\marnold\...` path, not bash heredocs, which mangle backticks).
Venv: `.venv/bin/python`.

## Decisions
- Standalone repo `folio_orders_loader` (marnold-ebsco, SSH), no git-init until code is worth
  keeping. `folio_ebsconet_orders` (`~/scratch/EBSCOnet`) later depends on it by git tag;
  do not modify that repo yet. EBSCONET keeps `read_sops/classify/enrich` and maps rows to the
  neutral line-record format in `folio_orders_loader/records.py`.
- Bugfest only (`~/scratch/EBSCOnet/sunflower_bugfest.ini`, never copy/commit). Dry run before
  every live POST. PO numbers must be `^[a-zA-Z0-9]{1,22}$`.
- The tool is also standalone against customer-provided delimited files, so a mapping file is
  REQUIRED for CLI input (only the EBSCONET adapter bypasses it by emitting neutral records).
- Map file uses the folio-migration-mapper row format (`~/folio-migration-mapper`, see its
  README and `php/mapping/orders/`), but `folio_field` holds our NEUTRAL keys (not real FOLIO
  paths): builder.py and the code->UUID Resolver stay as-is. Moving to real FOLIO paths is a
  possible later change, only if a customer needs a field the builder does not hardcode.

## Done
- Package: `records.py` (validate, group_by_po), `lookups.py` (Resolver), `builder.py`,
  `loader.py` (`load(client, lines, live=False)`, skips existing POs), `mapping.py`, `cli.py`,
  `__main__.py`, `client.py` (ini/connect), `tools.py` (delete/export), `pyproject.toml`,
  `README.md`. Spike scripts are in `spike/`.
- `mapping.py`: `template()`, `load_map`, `check_map`, `read_rows`, `map_row`, `map_file`.
  Source precedence per field: legacy_field, fallback_legacy_field, value, fallback_value;
  then `translate` (exact, then case-insensitive; an unmatched value is an ERROR, see Next item 2).
  Coerces cost ($ and commas) and booleans; assembles `product_ids[n].type/value`.
  Reader settings in map header `reader` (default tab, utf-8-sig).
  Also `rules` and `date_format` (Next item 2).
- 26 pytest tests pass; flake8 clean (`--max-line-length=100`).
- `rules`/`date_format` are documented in README.md; `template()` hints `date_format` on date fields.

## Live results (bugfest, 2026-09-30; every test PO was deleted afterwards)
- CLI load (dry run and --live), re-run (existing PO skipped as `exists`), export, and delete
  (dry run, JSON backup, live) all work.
- Verified live: electronic, physical and P/E Mix lines (material type and location stored,
  quantities and prices correct); Ongoing PO (interval, isSubscription, renewalDate = latest
  subscription_to; subscriptionFrom/To on lines); a multi-PO file in one run (2 POs, 3 lines);
  `translate` tables (order_type Sub/Mono, format Online); `$` in cost.
- Working test codes: vendor SRAR (or ebsconet), funds TEST-ELEC / TEST-PRINT, expense class GEN,
  acquisition method Depository, location TEST-EBSCONET-LOC, material type journal.
- Found: fund ZSS2025 with expense class `access` has no budget, so FOLIO returns 400
  `budgetExpenseClassNotFound`. The loader reports it cleanly and creates nothing, but
  `validate` cannot catch it.
- `pip install -e .` into the venv: not separately confirmed (run it in the venv, not system
  python, which is externally managed).

## Next
1. DONE (2026-09-30): `budgets.py check_budgets` + `Resolver.active_budget`, called from
   `validate` when --ini is given. Flags a fund with no Active budget for the current fiscal year
   (ZSS2025 returns currentFiscalYearNotFound) and an expense class not Active on the budget
   (its statusExpenseClasses, only present on /finance/budgets/{id}). Verified live on bugfest;
   22 tests pass, flake8 clean. `load` does not run this check (FOLIO still rejects cleanly).
2. DONE (2026-09-30): `date_format` (strptime -> ISO, date fields only), `rules` (split,
   combine, strip_prefix/suffix, upper/lower; our own op set, the mapper has no examples),
   quoted-delimiter test. Translation misses and bad dates are now ERRORS (validate prints
   them and fails; `load` refuses to run). `map_row`/`map_file` return (line, errors).
   26 tests pass, flake8 clean. Not run live (mapping-only change).
3. Resume after mid-file failure: DONE live (2026-09-30). 3-PO file, RSM2 failed
   (budgetExpenseClassNotFound), RSM1/RSM3 still created (a failure does not stop the run);
   after fixing RSM2 a re-run created only RSM2 and skipped the others as `exists`; a third
   run skipped all. Test POs deleted. The `error` detail is now trimmed to
   "message (code)" by `loader.error_message` (DONE, tested). All open checks are closed (see below).
   Clean-venv `pip install -e .[dev]` confirmed (2026-09-30). Not done: adapter live re-run
   (bugfest login returned 503), an "open order" step.
   Payment status + vendor reference numbers: CODED (2026-09-30): `payment_status`,
   `vendor_reference_number` + `vendor_reference_type` (enums from the acq-models schemas;
   "Vendor title number" is a reference type, probably what "title number" meant), 31 tests
   pass, README updated. LIVE CHECK PENDING (bugfest login 503): load one PO with both,
   export it, confirm paymentStatus and vendorDetail.referenceNumbers, delete it.
   PO-level `notes`, `tags` ({tagList}), `bill_to`, `ship_to` (address UUIDs, not looked up)
   also CODED (2026-09-30, 33 tests); same pending live check. Address names -> UUID lookup
   not built (find where the tenant keeps addresses first).
4. Commit: DONE locally (2026-09-30): git init (branch main), commit 43d13d5, tag v0.1.0. NOT pushed:
   GitHub remote `marnold-ebsco/folio_orders_loader` not created/added yet.
5a. EBSCONET adapter written locally (uncommitted, in ~/scratch/EBSCOnet): pipeline/folio_orders_adapter.py
   (prep workbooks -> neutral records -> folio_orders_loader.load; run `python -m pipeline.folio_orders_adapter --in-dir DIR --ini INI [--live]`) + tests/test_orders_adapter.py (3 pass, flake8 clean). The loader is
   pip-installed editable into EBSCOnet/.venv (not in requirements.txt yet). LIVE RUN DONE (2026-09-30, bugfest):
   three_type_test workbooks, 140/140 POs created, 0 errors, ~2 min (~0.9 s/PO). Order numbers were NOT
   ZT-prefixed (real-looking, e.g. M2822798). Not spot-checked in the FOLIO UI. All 140 then deleted with
   JSON backups (kept in ~/scratch/ebsconet_bugfest_backup_2026-09-30, outside the repo).
   Gaps vs Data Import route: builder ignores PO line description, receipt status, account fields.
5. DONE locally: pyproject version 0.1.0 (commit e950d7c), tag v0.1.0 moved to it (unpushed, so safe).
   PUSHED (2026-09-30): https://github.com/marnold-ebsco/folio_orders_loader (main + v0.1.0).
   Adapter committed and pushed in EBSCOnet; pin is now @v0.2.0 (see below).

## Session log (2026-09-30, late)
- Verified item 2 code is committed (in 43d13d5); handoff was accurate.
- Ran validate --ini sunflower_bugfest.ini, dry run, then LIVE load of 2 POs (ZTLD001/2) with a
  scratch map/data in /tmp/t, then deleted them. All OK. The delete CSV needs columns
  `type,number` (e.g. `PO,ZTLD001`), not po_number.

## Suggested order for the next session
Builder gaps DONE (2026-09-30): description (poLineDescription), receipt_status, vendor_account
(vendorDetail.vendorAccount), verified live on bugfest (test PO deleted); 28 tests pass.
Loader v0.2.0 tagged and pushed. EBSCOnet adapter passes description + per-route receipt_status,
requirements.txt pins the loader @v0.2.0, pushed (4fc1a9d). The adapter has no source column for
vendor_account. Not yet re-run live with the new fields.
Receipt status + account (vendor_account) CLOSED 2026-09-30: already in builder/records/mapping/README with tests and
verified live; no further account fields needed (paymentStatus, reference numbers deferred until a customer needs them).
Throughput CLOSED 2026-09-30 (bugfest): 500 single-line POs (ISSN + Local identifier, e/p mix) loaded in 7m20s
(0.88 s/PO), 0 errors; deleting them took 10m22s (1.2 s/PO); all 500 deleted. No open checks remain.
Open checks CLOSED (2026-09-30, live on bugfest, test POs deleted): ISSN + title number works as two
product_ids (type names must be tenant names: ISSN and Local identifier; there is no Title number type).
Over-budget: a Pending PO for 99,999,999 on TEST-ELEC was created with no error; encumbrance is only
checked when a PO is opened, so the loader (Pending only) cannot hit it. Nothing to fix in the loader.

## Field coverage and remaining groups (2026-09-30)
Roughly 35% of settable PO/line top-level fields are covered. DONE: PO number, vendor, orderType,
ongoing, workflowStatus (always Pending), notes, tags, bill_to, ship_to; line title, acquisition
method, format, source, checkinItems, cancellationRestriction, fundDistribution (ONE fund, 100%),
cost (list price only), details (productIds, subscriptionFrom/To), publisher, description,
receiptStatus, paymentStatus, vendorDetail (account, referenceNumbers), eresource (accessProvider,
activated, createInventory), physical (materialType, createInventory), locations (ONE, qty 1).
Live check still PENDING for payment_status, vendor reference numbers, notes/tags/bill_to/ship_to
(bugfest login was 503 on 2026-09-30 evening).

Remaining line-field groups, in order (do one group per session; schema:
https://github.com/folio-org/acq-models mod-orders-storage/schemas/po_line.json):
1. **Funds, locations, quantity, cost**: CODED and COMMITTED locally (92a5610, not pushed/tagged), 42 tests pass, flake8
   clean, README updated. Neutral keys: `fund_distribution[n].code/.expense_class_code/.value/.type`
   (percentage default; must sum 100), `locations[n].code/.quantity_physical/.quantity_electronic`
   (must sum to line quantities), `quantity_physical/_electronic`, `discount`, `discount_type`,
   `additional_cost`, `exchange_rate`. `fund_code`/`expense_class_code`/`location_code` remain the
   single shorthand (fund fields moved out of records.REQUIRED; validate_line/check_map require
   one form). Repeating groups generalised via records.REPEATING in mapping.py. budgets.py now
   checks every fund in the distribution. LIVE CHECK PENDING (bugfest login 503): scratch map/data
   at /tmp/g1 (PO ZTG1001, P/E Mix, 60/40 TEST-ELEC/TEST-PRINT, qty 3/2, discount 10%, additional
   cost 4); dry run, --live, export, delete. Also bump version/tag v0.3.0 and update the EBSCOnet pin
   after the live check.
2. **Bibliographic**: CODED and COMMITTED locally (a31b7ec, not pushed/tagged), 46 tests pass, flake8 clean,
   README updated. Neutral keys: `contributors[n].name/.type` (type = contributor name type name,
   looked up via `Resolver.contributor_name_type` on /contributor-name-types), `edition`,
   `publication_date` (free text). LIVE CHECK PENDING: load a line with two contributors
   (e.g. Personal name, Corporate name), export, confirm contributors/edition/publicationDate, delete.
   Group 1 live check also still pending; then bump to v0.3.0, tag, push, update the EBSCOnet pin.
   (Original brief, kept for reference: follow the group-1 pattern: add a `contributors` entry to
   records.REPEATING with sub-keys name/type, validate in records.py, build in builder.py, map in
   mapping.py via REPEATING_RE, tests in tests/, README section; contributor name type needs a
   Resolver lookup by name against /contributor-name-types): contributors (name + contributor name type), edition, publicationDate.
3. **People/flags/tags**: CODED and COMMITTED locally (not pushed/tagged), 49 tests pass, flake8 clean,
   README updated. Neutral keys: `line_tags` (| list -> line tags.tagList; `tags` stays PO level),
   `requester`, `selector`, `rush` (boolean). LIVE CHECK PENDING: load, export, confirm, delete.
4. **Electronic extras**: CODED and COMMITTED locally (not pushed/tagged), 54 tests pass, flake8 clean, README updated. Neutral keys: resource_url, user_limit, trial, volumes (| list), material_supplier_code (org code), expected_receipt_date, receiving_note, is_acknowledged, subscription_interval, receipt_date, renewal_note, cancellation_restriction_note, product_ids[n].qualifier. Dates sent as T00:00:00.000+00:00. LIVE CHECK PENDING (groups 1-4 all unchecked live; then bump v0.3.0, tag, push, update EBSCOnet pin). Original list: eresource.resourceUrl, userLimit, trial; physical volumes,
   materialSupplier, expectedReceiptDate; details receivingNote, isAcknowledged,
   subscriptionInterval, productIds qualifier; receiptDate; renewalNote, cancellationRestrictionNote.
5. **Maybe**: CODED and COMMITTED locally (57 tests, README updated; live check pending): automatic_export, collection, suppress_from_discovery, multi_year_payment, claiming_active, is_package, claiming_interval, donor, donor_organization_codes, instance_id, agreement_id, package_po_line_id. NOT built: paymentTerms, customFields, claims. Original list: donor/donorOrganizationIds, paymentTerms, multiYearPayment, claiming*, automaticExport,
   collection, suppressInstanceFromDiscovery, instanceId, agreementId, isPackage/packagePoLineId,
   customFields. Skip system fields (id, metadata, poLineNumber, purchaseOrderId, searchLocationIds,
   lastExport, lastEDIExportDate).
Also unbuilt: address name -> UUID lookup for bill_to/ship_to, an "open order" step, PO-level
acqUnitIds, poNumberPrefix/Suffix, assignedTo, template, manualPo, reEncumber, customFields.

## Not done, and recommendations (2026-09-30, after group 5)

### Not verified
- No live bugfest check for ANY of groups 1-5, nor for payment_status, vendor reference numbers,
  notes/tags/bill_to/ship_to (bugfest login returned 503). Group 1 scratch map/data: /tmp/g1.
  For each group: dry run, --live one PO, export, confirm the FOLIO fields, delete.
- Not released: groups 1-5 are committed locally only (latest 0051a41). Still to do after the
  live checks: bump pyproject to v0.3.0, tag, push, update the EBSCOnet pin in requirements.txt.
- EBSCOnet adapter not re-run live with the new loader fields.
- Group 4/5 dates are sent as `YYYY-MM-DDT00:00:00.000+00:00`; FOLIO acceptance is untested.
- Group 4 `user_limit`/`trial`/`resource_url` are not rejected on physical-only lines (the
  builder just ignores them); same for `volumes`/`material_supplier_code` on electronic lines.

### Deliberately not built (group 5 leftovers)
- `paymentTerms` (multi-year prepayment object), `customFields`, `claims` (array of claim
  records), `locations` receipt/other sub-fields, `eresource.license`, `expectedActivation`,
  `activationDue`, `eresource.materialType`, `physical.receiptDue`, `physical.createInventory`
  other than "None", `checkinItems` (always false), `source` (always "User").
- PO level: address name -> UUID lookup (bill_to/ship_to), acqUnitIds, poNumberPrefix/Suffix,
  assignedTo, template, manualPo, reEncumber, customFields, and an "open order" step
  (loader is Pending-only).

### Group 6 (items 1-3 below): CODED and COMMITTED locally, 61 tests, README updated, live check pending
Keys: create_inventory_physical / create_inventory_electronic (two keys, since electronic has no
Item option; default None), checkin_items, PO-level acq_unit_names (units have NO code, so the
name is used; Resolver.acquisition_unit queries /acquisitions-units/units by name; not verified live).

### Recommended additions, in priority order
1. **`create_inventory`** (eresource and physical; "None" / "Instance" / "Instance, Holding" /
   "Instance, Holding, Item"). Hardcoded to "None" today; real migrations nearly always need it.
   Small change: enum check in records.py, one key.
2. **PO-level `acq_unit_codes`** (acqUnitIds, via a /acquisitions-units/units lookup). Tenants
   commonly restrict POs by acquisition unit, so the load fails or the PO is invisible without it.
3. **`checkin_items`** (boolean). Needed to receive serials/ongoing lines by check-in; one key.
4. **`activation_due` / `expected_activation`** and **`receipt_due`**. Cheap, round out the
   electronic/physical receiving dates.
5. **Address name -> UUID lookup** for bill_to/ship_to, so customers do not hand-copy UUIDs.
   First find where this tenant stores addresses.
6. **Open-order step** (workflowStatus Open) once encumbrance behavior is decided; large, own session.
7. **`po_number_prefix`/`suffix`, `manual_po`, `re_encumber`, `assigned_to`**: small PO-level
   keys; add only when a customer asks.
8. **`customFields`, `paymentTerms`, `claims`**: skip unless a customer needs them; tenant
   specific and schema-heavy.
9. Reject electronic-only keys on physical lines (and vice versa) in `validate_line`.

## Working notes
- Keep sessions short and single-purpose; start a fresh one for each Next item using this file.
- Run only relevant tests with `| tail`; delegate broad searches to an Explore agent.
- Test data and maps for live runs go in the session scratchpad, not the repo.

## Group 6 items 4-7 (2026-09-30): CODED, 69 tests, flake8 clean, README updated; NOT live-checked
4. ,  (days), .
5. ; bill_to/ship_to accept a name or UUID (mod-settings entries first,
   mod-configuration fallback; UNVERIFIED which this tenant uses).
6.  / : GET the created PO, set workflowStatus Open, PUT;
   failure -> , PO stays Pending.
7. , , , , .
Live checks pending for all (and groups 1-6 generally); then v0.3.0, tag, push, EBSCOnet pin.
