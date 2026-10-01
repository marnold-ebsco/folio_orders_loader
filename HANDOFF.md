# Handoff (2026-10-01): folio_orders_loader v0.3.5 released

This file covers the loader package only. The EBSCOnet side (adapter, `ebsconet.py` workflow,
`api-load-default` branch, vendor accounts, real-tenant test) is tracked in
`~/scratch/EBSCOnet/HANDOFF.md`; read that for EBSCOnet work.

## What the loader owes EBSCOnet (cross-project facts)
- EBSCOnet depends on this package by git tag (pinned to v0.3.4; v0.3.2 only adds the opt-in check_budget, v0.3.3/4 only add the installer).
  Installing in EBSCOnet's venv does not auto-upgrade: after a pin bump run
  `.venv/bin/pip install --force-reinstall --no-deps` on the requirements line.
- The EBSCOnet adapter emits neutral line records (`records.py`) and bypasses the mapping file.
- `loader.load()` does not call `budgets.check_budgets`; only the loader CLI `validate` does
  (cli.py). The EBSCOnet adapter calls `check_budgets` itself on its dry run
  (`check_dry_run_budgets`, EBSCOnet 2026-10-01), so no loader change or release was needed.
  Library users calling `load()` directly still only see a budget problem at `--live`
  (`budgetExpenseClassNotFound`). Released in v0.3.2: opt-in `check_budget=True` on `load()` runs check_budgets per PO (invalid on failure); default off. 95 tests pass.
- Lookups (`lookups.py` Resolver) raise `LookupError_` for organization, fund, expense class,
  location and material type, which `loader.load` reports as `lookup-failed`.

**We work in Linux (WSL Ubuntu), not Windows.** Work in WSL `~/scratch/folio_orders` (run via
`wsl.exe -e bash -lc`; write files through the `\\wsl.localhost\Ubuntu-24.04\home\marnold\...`
path, not bash heredocs, which mangle backticks; for Python with quotes write a script file).
Venv: `.venv/bin/python`. 93 pytest tests pass; flake8 clean (`--max-line-length=100`).

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
- v0.3.1 released 2026-10-01 (commit 636fd9a, tag pushed): expense class is optional (see below).
- v0.3.2 released 2026-10-01 (commit 2a931ae, tag pushed): opt-in check_budget=True on load() (default off);
  invalid + no POST when a fund has no Active budget or the class is not Active on it. 95 tests pass.
- v0.3.3 / v0.3.4 released 2026-10-01 (tags pushed; v0.3.4 = 9cb603e): `install.sh` + README
  "Install on a host (no clone)". v0.3.3's tag lacks the README section; use v0.3.4. No code change.
  EBSCOnet pin bumped to v0.3.4 (f625908), 197 tests pass.
- v0.3.5 released 2026-10-01 (tag pushed, 7c2ef79): `template` omits the `reader` block by default (it conflicted
  with other mapping tools); `template --with-reader` writes it. Loading is unchanged: a map with no
  `reader` uses DEFAULT_READER (tab, utf-8-sig); `--delimiter`/`--encoding` still override. 96 tests pass.
  EBSCOnet pin stays v0.3.4 (adapter does not use template). Untracked `map.json` in the repo root is
  not ours; left alone.
- Installer (`install.sh`, repo root): downloads one release tarball via the GitHub API
  (`GITHUB_TOKEN` required, repo is private; read-only fine-grained token, Contents: read),
  pip-installs it into `<dir>/venv` (default `~/folio-orders-loader`), links `folio-orders-loader`
  into `/usr/local/bin` or `~/.local/bin`. Flags: `-v tag|latest`, `-d dir`, `-b bindir`. Upgrade =
  re-run with a newer `-v`. Tested in WSL 2026-10-01 with `GITHUB_TOKEN=$(gh auth token)` (not set
  in the shell by default): v0.3.4 and `-v latest` resolution OK. NOT tested on a real EC2, without
  python3-venv, or with the fine-grained token.
- Live-verified on bugfest 2026-10-01: a PO with a blank expense class loads, and opens with --open
  (export shows no expenseClassId). Deleted afterwards (Open POs must be PUT back to Pending first).

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

## Expense class is optional (v0.3.1, done)
FOLIO does not require expense classes. A blank class is now allowed (fund still required):
- `records.py` no longer reports a missing expense class; `FUND_FIELDS` is now `("fund_code",)`.
- `builder.py` omits `expenseClassId` from the fund distribution when the code is blank.
- `budgets.py` keeps the "no Active budget" check but skips the class half for a blank class.
  A class that IS given must still resolve and be Active on the budget.
- README fund shorthand text updated; tests added in test_budgets, test_builder,
  test_funds_locations.

## NEXT
- Nothing open for the loader. The EBSCOnet pin bump to v0.3.1 and the adapter use_expense_classes
  change are done (see EBSCOnet HANDOFF).
- Optional: switch the EBSCOnet adapter to load(check_budget=True) instead of its own check_dry_run_budgets;
  bump its pin to v0.3.2 if so.
- Run `install.sh` on a real EC2 with the fine-grained token (only WSL tested so far).
- Untested: a fund with no budget on a real tenant, and over-budget behaviour (bugfest allows overspend).

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
