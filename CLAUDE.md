# CLAUDE.md

Guidance for Claude Code in `folio_orders_loader`.

## Session workflow
- At the start of a session, read `HANDOFF.md` first, then `FINDINGS.md` if needed.
- Work in WSL (`~/scratch/folio_orders`, venv `.venv/bin/python`), not Windows.
- At the end of each task, update `HANDOFF.md` (mark items done, note live results and
  what is still open), then commit and push to `main` without asking.
- Live runs go to Bugfest only (`~/scratch/EBSCOnet/sunflower_bugfest.ini`): dry run first,
  and delete every test PO afterwards.
- Keep test data and maps for live runs outside the repo (scratchpad or `/tmp`).
