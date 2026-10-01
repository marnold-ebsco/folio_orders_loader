# Handoff (2026-10-01): folio_orders_loader v0.3.0 released

This file covers the loader package only. The EBSCOnet side (adapter, `ebsconet.py` workflow,
`api-load-default` branch, vendor accounts, real-tenant test) is tracked in
`~/scratch/EBSCOnet/HANDOFF.md`; read that for EBSCOnet work.

## What the loader owes EBSCOnet (cross-project facts)
- EBSCOnet depends on this package by git tag (`requirements.txt` pins `@v0.3.0`, 84a99ac).
  Installing in EBSCOnet's venv does not auto-upgrade: after a pin bump run
  `.venv/bin/pip install --force-reinstall --no-deps` on the requirements line.
- The EBSCOnet adapter emits neutral line records (`records.py`) and bypasses the mapping file.
- `loader.load()` does not call `budgets.check_budgets`; only the loader CLI `validate` does
  (cli.py). The EBSCOnet adapter calls `check_budgets` itself on its dry run
  (`check_dry_run_budgets`, EBSCOnet 2026-10-01), so no loader change or release was needed.
  Library users calling `load()` directly still only see a budget problem at `--live`
  (`budgetExpenseClassNotFound`). Possible follow-up: an opt-in `check_budget` option on `load()`.
- Lookups (`lookups.py` Resolver) raise `LookupError_` for organization, fund, expense class,
  location and material type, which `loader.load` reports as `lookup-failed`.

**We work in Linux (WSL Ubuntu), not Windows.** Work in WSL `~/scratch/folio_orders` (run via
`wsl.exe -e bash -lc`; write files through the `\\wsl.localhost\Ubuntu-24.04\home\marnold\...`
path, not bash heredocs, which mangle backticks; for Python with quotes write a script file).
Venv: `.venv/bin/python`. 90 pytest tests pass; flake8 clean (`--max-line-length=100`).

Background: `FINDINGS.md` (spike results, verdict GO), `API_SPIKE.md` (original brief), the plan
`C:\Users\marnold\.claude\plans\idempotent-crafting-rivest.md`, and `README.md` (field reference,
"Known gaps", "Kitchen-sink fixture").

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
- v0.3.0 released 2026-10-01 (commit 53a6323, tag pushed). EBSCOnet's 188 tests passed against
  the tag when it was pinned.

## Live-verified (bugfest, 2026-09-30 / 10-01)
- Everything in the field groups, incl. acquisition units (Law, user is a member now), address
  names (via mod-configuration `tenant.addresses`), prefix/suffix (tenant has `abc`, `test`, ...),
  `manual_po`, `re_encumber`, `assigned_to` (user UUID), non-Pending receipt/payment status,
  `exchange_rate`, donors, `instance_id`, `agreement_id`, `package_po_line_id`, dates, `--open`.
- Budget check in `validate` (fund with no Active budget / expense class not on budget).
- Resume after mid-file failure; throughput ~0.9 s/PO create, ~1.2 s/PO delete.
- EBSCOnet adapter re-run with loader v0.3.0: 140/140 POs created, 0 errors, then deleted.

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
  P/E Mix allows both. `material_type` and `access_provider_code` are deliberately not checked
  by `validate_line` (material type is still resolved at build time).

## NEXT (for the loader-CLI session): make the expense class optional, release v0.3.1
Found 2026-10-01 from the EBSCOnet side. FOLIO does not require expense classes, but the loader
does, so a tenant that does not use them cannot be loaded:
- `records.py` `_check_funds` (lines ~97-108) marks a line `invalid` when `fund_code` /
  `expense_class_code` is missing, and per `fund_distribution` entry ("missing expense_class_code").
  `FUND_FIELDS = ("fund_code", "expense_class_code")` (line 21) is used for the check.
- `builder.py` `build_line` (line ~16) always calls `r.expense_class(...)` and sets
  `expenseClassId`; with a blank code `lookups._q(None)` would query `code=="None"`.
- `budgets.py` `check_budgets` always resolves the class and compares it to the budget's Active
  `statusExpenseClasses`.
- Wanted: blank class is allowed (fund still required): no `expenseClassId` in the payload, no
  "missing" problem, and `check_budgets` keeps the "no Active budget" check but skips the class
  half. A class that IS given must still resolve and be Active on the budget. Add unit tests
  (records, builder, budgets), update README ("Known gaps"/field reference), tag v0.3.1.
- Then in EBSCOnet (`~/scratch/EBSCOnet`, see its HANDOFF.md): bump the `requirements.txt` pin
  and make `pipeline/folio_orders_adapter.py` honour `rules.use_expense_classes: false`. It
  currently falls back to `default_expense_class` for a blank cell (line ~43), so a tenant
  without classes still gets one put on the lines, or all POs go `invalid` if the default is
  empty. README_API.md already claims "no class is put on the lines".

## Not done
- `open-error` path exercised by unit tests only (see gotchas); the user will exercise
  budget / acquisition-unit / open-error behaviour on a real tenant later.
- Deliberately not built: `paymentTerms`, `customFields` (PO and line), `claims`, location
  receipt sub-fields, `eresource.license`/`materialType`, `physical.createInventory` beyond the
  option set, `checkinItems` beyond the boolean key, `source` (always "User"), and system fields.
- Add only when a customer asks: further PO-level keys not listed in the README.

## Working notes
- Keep sessions short and single-purpose. Run only relevant tests with `| tail`; delegate broad
  searches to an Explore agent. Test data and maps for live runs go in the scratchpad or /tmp,
  not the repo.
