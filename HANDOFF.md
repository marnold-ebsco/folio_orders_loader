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
  then `translate` (exact, then case-insensitive; unmatched passes through with a warning).
  Coerces cost ($ and commas) and booleans; assembles `product_ids[n].type/value`.
  Reader settings in map header `reader` (default tab, utf-8-sig).
  Also `rules` and `date_format` (see Next item 2); misses/bad dates are errors.
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
   run skipped all. Test POs deleted. Note: the `error` detail is FOLIO's raw response
   (up to 500 chars, multi-line) - consider trimming to the message.
   Remaining open checks: over-budget/encumbrance errors, ISSN + title number, receipt status,
   account fields (these three are not in builder.py yet), throughput on a larger file.
4. Commit: DONE locally (2026-09-30): git init (branch main), commit 43d13d5, tag v0.1.0. NOT pushed:
   GitHub remote `marnold-ebsco/folio_orders_loader` not created/added yet.
5a. EBSCONET adapter written locally (uncommitted, in ~/scratch/EBSCOnet): pipeline/folio_orders_adapter.py
   (prep workbooks -> neutral records -> folio_orders_loader.load; ) + tests/test_orders_adapter.py (3 pass, flake8 clean). The loader is
   pip-installed editable into EBSCOnet/.venv (not in requirements.txt yet). Dry run on the three_type_test
   workbooks (order numbers prefixed ZT): 140/140 dry-run OK. NOT yet run live. Gaps vs Data Import
   route: builder ignores PO line description, receipt status, account fields; pyproject version is
   0.1.0.dev0 though tagged v0.1.0.
5. Create the GitHub remote and push main + tag, then the EBSCONET adapter in folio_ebsconet_orders
   (depends on this repo by git tag; maps its rows to the records.py neutral format).

## Working notes
- Keep sessions short and single-purpose; start a fresh one for each Next item using this file.
- Run only relevant tests with `| tail`; delegate broad searches to an Explore agent.
- Test data and maps for live runs go in the session scratchpad, not the repo.
