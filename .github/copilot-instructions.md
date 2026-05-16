# Copilot project instructions

This repository is set up to be worked on with either GitHub Copilot CLI or
Claude Code. To avoid drift between two long instruction files, the canonical
project conventions live in **[CLAUDE.md](../CLAUDE.md)** and
**[design.md](../design.md)**. Read those first.

For current goals, status, and backlog, read **[plan.md](../plan.md)**.

## Quick "do not" list (full rationale in `CLAUDE.md` and `design.md`)

- **Do not switch the CPI series from `CPIAUCNS` to `CPIAUCSL`.** The seasonally
  adjusted series only starts in 1947 and silently truncates 21 years of Ken
  French history. Keep NSA.
- **Do not treat Ken French values as decimal.** Source values are percent
  (`2.50` = 2.5%). `src/ingest.py` divides by 100; downstream math assumes
  decimal.
- **Do not propose collapsing the Python pipeline into pure JS** without
  re-reading `design.md` § "Why this architecture." Ken French's server has no
  CORS and pandas keeps future stats analyses cheap.
- **Do not change the rolling-window start-date convention** in
  `src/analysis.py`. Windows are labeled by their *start* date, not their end,
  and the JSON schema + `docs/app.js` depend on it.
- **Do not commit secrets or large generated artifacts.** `data/raw/`,
  `data/processed/`, and `reports/` are gitignored and regenerable.
  `docs/data/*.json` *is* committed — that is the data the live site needs.

## Adding a new scenario

The project supports multiple analysis scenarios. To add one:

1. Add a module under `src/scenarios/<slug>.py` implementing the `Scenario`
   protocol from `src/scenarios/base.py`.
2. Append an instance to `SCENARIOS` in `src/scenarios/__init__.py`.
3. Add `docs/scenarios/<slug>.html` and a matching `notebooks/NN_<slug>.ipynb`.
4. Re-run `python -m src.export` and `python -m src.report`.
5. Update `plan.md`, `design.md`, and `CLAUDE.md` in the same commit.

## Doc sync rule (applies to any architectural change)

When changing the data flow, modules, dependencies, or commands, update
`plan.md`, `design.md`, **this file**, and `CLAUDE.md` in the same turn as the
code change — not as a follow-up.
