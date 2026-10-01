# Handoff (2026-10-01): folio_orders_loader v0.3.0 released

## Session 2026-10-01 (later): Orders API is now the DEFAULT load in EBSCOnet
Branch `api-load-default` in `~/scratch/EBSCOnet`, pushed (head `ef3b124`), NOT yet merged to
`main` and no PR opened. 195 tests pass, flake8 clean. Decide: open a PR / merge to main.
- `ebsconet.py load` / `finish` use the Orders API (`pipeline/folio_orders_adapter.py`
  `load_orders()`); `--use-marc` on both selects the MARC / Data Import backup route.
  `--skip-accounts` skips the vendor-account step. `load` processes every PO, then exits 1 if any
  is invalid / lookup-failed / error / open-error; re-runs skip existing POs.
  `finish` on the API route only writes `out/pol_export.csv` (no ongoing conversion).
- Each `load` writes `<out>/logs/accounts_<YYYYMMDD_HHMMSS>.txt` (mode, tenant ini name,
  start / end / elapsed of the account step, account numbers added / present, orgs not found).
  Timing covers only the account step; a whole-run summary log was offered, not built.
- Docs split: `README_API.md` and `README_DATA_IMPORT.md` (each standalone, Setup near the top),
  `README.md` is an index; `RUNBOOK.md` and `PLAN.md` updated (MARC steps are "M6-M9").
  `README_API.md` lists the dry-run checks (fund, expense class, org, location, material type,
  budget) without verification against the loader code: check it.
- Live bugfest test, 25 POs (20 electronic, 3 print, 2 P/E) from trimmed copies of
  `out/three_type_test/*.xlsx` in `/tmp/live25`: dry run, live load (25 created), UI-free API
  check vs workbooks (0 mismatches), re-run (25 exists), then all 25 deleted; backups in
  `~/scratch/ebsconet_bugfest_backup_live25` (outside repo; delete when no longer needed).
  Two vendor accounts remain on org EBSCO (RZ41049-91, XW14722-82); remove if unwanted.
- Gotcha: shell heredocs with backticks mangle docs; write edit scripts with the Write tool.
- Still open: item 3 below; `RUNBOOK.md` "Lessons" and some MARC-only tool rows are labelled
  but not rewritten; consider updating the EBSCOnet `HANDOFF_ebsconet_three_spreadsheets.md`.

## Item 4 DONE (2026-10-01): all four `~/scratch/ebsconet_bugfest_backup_*` folders deleted.
`out/three_type_test/*.xlsx` deliberately KEPT (needed for the item 3 sandbox test and reload
recipes); delete them after item 3. Item 3 was skipped for now: user has no sandbox/UAT `.ini`
yet (must live outside the repos, never committed).

## NEXT: item 3 - test the adapter against a non-bugfest tenant (sandbox / UAT)
Bugfest allows overspend and is lenient, so budget enforcement, acquisition-unit restrictions and
`open-error` have only unit tests. Ask the user for the tenant `.ini` (never copy/commit one; put it
outside the repo), then: (1) `python -m folio_orders_loader validate` / the adapter dry run first,
(2) load a SMALL batch (about 5-7 POs, one per format) from `/tmp`, not all 140, (3) have the user
check them in the UI, (4) delete them with `folio_delete_orders.py` (dry run, then `--live`).
Tenant codes (vendor, fund, expense class, location, acquisition method) will differ from the
bugfest "Working test codes" below; fix `ebsconet_config.json` values in a copy, not the repo.
Afterwards delete `out/three_type_test/*.xlsx` (derived, real-looking orders; sensitive).

## Done this session (2026-10-01, EBSCOnet repo `~/scratch/EBSCOnet`, commit 0878ccc, pushed)
- Item 1: 7 adapter POs (3 electronic, 2 physical, 2 P/E) checked in the FOLIO UI by the user: good.
  Deleted; backups in `~/scratch/ebsconet_bugfest_backup_2026-10-01c`.
- Item 2: `pipeline/folio_orders_adapter.py` now maps SOP `Account Number` -> `vendor_account`
  (`pipeline/pipeline_config.json` columns.account) and `ensure_accounts()` adds each missing account
  to the organization on the line (FOLIO Org), payment method `folio.account_payment_method`;
  `--skip-accounts` opts out. FOLIO stores `vendorAccount` without checking it against the org.
  Live-verified on bugfest (account added, PO saved, then PO deleted and account removed).
  Reference numbers deliberately NOT mapped (no SOP column; MARC route never had one).
- README ("Alternative load: the Orders API") and RUNBOOK section D now document the adapter.
  191 EBSCOnet tests pass; flake8 clean.
- Quick batch recipe: trim copies of `out/three_type_test/library-EBSCONET_*.xlsx` into
  `/tmp/<dir>` (keep a few rows each), then
  `.venv/bin/python -m pipeline.folio_orders_adapter --in-dir /tmp/<dir> --ini <ini> [--live]`.
  Note the print workbook is `library-EBSCONET-print.xlsx` (hyphen).
- Writing files from Bash heredocs inside `wsl.exe -e bash -lc '...'` breaks on quotes; use the
  Edit/Write tools on the `\\wsl.localhost\...` path (Read the file first).

Background: `FINDINGS.md` (spike results, verdict GO), `API_SPIKE.md` (original brief), the plan
`C:\Users\marnold\.claude\plans\idempotent-crafting-rivest.md`, and `README.md` (field reference,
"Known gaps", "Kitchen-sink fixture").
**We work in Linux (WSL Ubuntu), not Windows.** Work in WSL `~/scratch/folio_orders` (run via
`wsl.exe -e bash -lc`; write files through the `\\wsl.localhost\Ubuntu-24.04\home\marnold\...`
path, not bash heredocs, which mangle backticks; for Python with quotes write a script file).
Venv: `.venv/bin/python`. 90 pytest tests pass; flake8 clean (`--max-line-length=100`).

## Decisions
- Standalone repo `marnold-ebsco/folio_orders_loader` (SSH, pushed; `main`, tags v0.1.0-v0.3.0).
  `folio_ebsconet_orders` (`~/scratch/EBSCOnet`) depends on it by git tag. EBSCONET keeps
  `read_sops/classify/enrich` and maps rows to the neutral line-record format in `records.py`.
- Bugfest only (`~/scratch/EBSCOnet/sunflower_bugfest.ini`, never copy/commit). Dry run before
  every live POST. PO numbers must be `^[a-zA-Z0-9]{1,22}$`. Delete every test PO afterwards.
- CLI input requires a mapping file (folio-migration-mapper row format, `~/folio-migration-mapper`),
  but `folio_field` holds our NEUTRAL keys, not FOLIO paths. Only the EBSCONET adapter bypasses
  the map by emitting neutral records.

## State
- Package: `records.py`, `lookups.py` (Resolver), `builder.py`, `loader.py`, `mapping.py`,
  `budgets.py`, `cli.py` (`load|validate|template|delete|export`), `client.py`, `tools.py`.
- Field groups 1-6 (funds/locations/cost, bibliographic, people/flags, electronic extras, misc,
  inventory/acq units/addresses/open/PO-number keys) are coded, documented in README, and
  VERIFIED LIVE on bugfest (load, export, compare, delete).
- v0.3.0 released 2026-10-01 (commit 53a6323, tag pushed). EBSCOnet `requirements.txt` pins
  `@v0.3.0` (84a99ac); its 188 tests pass against the tag.

## Live-verified (bugfest, 2026-09-30 / 10-01)
- Everything in the field groups, incl. acquisition units (Law, user is a member now), address
  names (via mod-configuration `tenant.addresses`), prefix/suffix (tenant has `abc`, `test`, ...),
  `manual_po`, `re_encumber`, `assigned_to` (user UUID), non-Pending receipt/payment status,
  `exchange_rate`, donors, `instance_id`, `agreement_id`, `package_po_line_id`, dates, `--open`.
- Budget check in `validate` (fund with no Active budget / expense class not on budget).
- Resume after mid-file failure; throughput ~0.9 s/PO create, ~1.2 s/PO delete.
- EBSCOnet adapter re-run with loader v0.3.0 (2026-10-01): 140/140 POs created, 0 errors; all 140
  deleted, JSON backups in `~/scratch/ebsconet_bugfest_backup_2026-10-01b` (outside the repo).
  Spot-checked by API only, never in the FOLIO UI.
- `out/three_type_test/*.xlsx` hold DERIVED (real-looking) orders, not synthetic; treat as
  sensitive and do not commit them or their PO numbers into fixtures.

## Gotchas
- Working test codes: vendor SRAR, funds TEST-ELEC / TEST-PRINT, expense class GEN, acquisition
  method Depository, location TEST-EBSCONET-LOC, material type journal, org SRACS.
- Fund ZSS2025 with expense class `access` has no budget: FOLIO returns 400
  `budgetExpenseClassNotFound` (clean error; nothing created).
- Product-ID type names must be tenant names (ISSN, Local identifier); no "Title number" type.
- `suppress_from_discovery` was removed: bugfest rejects `suppressInstanceFromDiscovery`.
- Delete CSV columns are `type,number` (e.g. `PO,ZTX1`); `delete` caps at 50 entries (`--max N`)
  and skips Open POs. To clean up an Open PO, PUT it back to Pending, then delete.
- Over-budget POs open fine on bugfest (overspend allowed), so `open-error` cannot be triggered.
- An electronic line with a quantity and no location loads; the mismatch error only fires when
  locations are present but do not match.
- Dates are sent as `YYYY-MM-DDT00:00:00.000+00:00` (accepted).
- Physical-only keys on Electronic lines (and vice versa) are rejected by `validate_line`;
  P/E Mix allows both. `material_type` and `access_provider_code` are deliberately not checked.
- Installing the loader in EBSCOnet's venv does not auto-upgrade: after a pin bump run
  `.venv/bin/pip install --force-reinstall --no-deps` on the requirements line.

## Not done
- `open-error` path exercised by unit tests only (see gotchas).
- Deliberately not built: `paymentTerms`, `customFields` (PO and line), `claims`, location
  receipt sub-fields, `eresource.license`/`materialType`, `physical.createInventory` beyond the
  option set, `checkinItems` beyond the boolean key, `source` (always "User"), and system fields.
- The adapter has no source column for `vendor_account` or reference numbers.
- Add only when a customer asks: further PO-level keys not listed in the README.

## Working notes
- Keep sessions short and single-purpose. Run only relevant tests with `| tail`; delegate broad
  searches to an Explore agent. Test data and maps for live runs go in the scratchpad or /tmp,
  not the repo.
