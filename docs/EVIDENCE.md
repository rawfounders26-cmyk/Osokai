# Osok-AI evidence (F31 truth-in-advertising: numbers, not adjectives)

Updated per release. Everything below is measured by the repo's own battery
(`backend/tests/`: 116 evals) and harness — rerun any of it.

## Current release
- **Evals**: 116/116 green (`pytest backend/tests/ -q`)
- **Benchmark plan mode**: 100/100 (`POST /benchmark/run {"mode":"plan"}`)
- **Benchmark live mode**: opt-in only (`OSOKAI_BENCH_LIVE=1`, budget-capped); history at `GET /benchmark/history`
- **North star**: avg interventions per goal at `GET /benchmark/interventions` (last measured 0.15; lower is better)
- **Recall quality**: factor-explained ranking at `GET /memory/recall-explain`; shadow-feedback loop records every exposure, confirmations lift ranking (see recall_feedback table)

## What the numbers mean
- Plan 100/100 = routing sends every battery task to a capable tool with the right approval gate. It measures the *plumbing*, not live model quality.
- Interventions/goal = approvals opened per goal pursuit (event-window attributed). Falls as autonomy improves; rises if gates over-fire.
- Eval count = regression net. A release that drops it is blocked by CI (`scripts/release-gate.sh`).

## History
| Date | Evals | Plan score | Interventions/goal | Note |
|---|---|---|---|---|
| 2026-10-01 | 116 | 100/100 | 0.15 | learned memory (factors, dedup, tiers, feedback) |
| 2026-09-30 | 104 | 100/100 | 0.15 | review batches 1–4 (34 findings fixed) |
| 2026-09-30 | 86 | 100/100 | 0.15 | benchmark harness first green |
| 2026-09-30 | 68 | — | — | hierarchy steps 1–4 complete |
