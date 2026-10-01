# Osok-AI — session handoff (read this + docs/SCALING.md in every new session)

> Living continuity file. Update at the end of every session (discussion or build)
> until merchant-services building starts. Conversations are RAM; this file is disk.

## Where we are
- **Version**: v0.6.0 + hardening + hygiene + hierarchy steps 1–4 COMPLETE + context engine + memory package + policy engine + capability router + benchmark harness + persistent specialists + review batches 1–4 + learned memory + fortify round + social connectors + connectors tier-1+2 + connectors 1000x. **Tests**: 134/134 green. **Benchmark**: plan 130/130, avg interventions 0.15/goal.
- **Last shipped**: hardening (no features) — recurring double-post fix, shared WAL DB helper,
  thread-safe memory, secrets audit clean, deep health, input clamps, 3 hardening evals.
- **Before that**: v0.6 platform · v0.5 · v0.4.x (outfit + bills, mobile screens, cloud pack) ·
  v0.4 · v0.3 · v0.2.
- **Repo**: `github.com/rawfounders26-cmyk/Osokai`, branch `main`.

## What's paused / what's next
- **v0.6 DONE** — shipped this session per user go.
- **Current front line**: merchant-services ("Muse-connectors for India") — DISCUSSION ONLY, Phase 0 validation.
  Next build candidates (v0.7): merchant Phase 1 (needs explicit go), SLM quantize + benchmark,
  handoff for loops/drafts. No code until user says build.

## Standing instructions
- Don't build without an explicit go from the user. Discussion sessions = no code, no commits except docs.
- Features are chat-driven (mobile ChatScreen + desktop Command Port via `/chat` fast intents).
- When building: verify live before commit, clean probe data, evals must stay green, push to `main`.
- New tabs start blank — this file + SCALING.md + `git log --oneline -10` reconstruct everything.

## Open threads

### A. Meta-connectors-for-India plan (the big bet)
- **Thesis**: Meta opened Muse to outside services via connectors (live US, not India yet).
  Whoever owns India's machine-readable service layer first wins discovery when assistants arrive.
  The next interface for a business may be a conversation, not its website.
- **What Muse connectors really are**: (1) machine-readable business (prices/availability/booking as API),
  (2) agent-executable booking (search → quote → confirm → book, no human clicks),
  (3) distribution (Meta owns users + interface; businesses get discovered in-conversation).
- **Osok-AI audit**: ~60% already there (agent loop, 85 skills, approval mediation, API-first backend,
  signed marketplace + sandbox). Missing: merchant-facing side, standard protocol (MCP), directory/trust layer.
- **Phases**: 1) machine-readable schemas for 3 services (mock providers first) → 2) agent booking with
  approvals → 3) MCP server for outside agents → 4) merchant onboarding + directory → 5) distribution loops
  (piggyback ONDC first, viral, creators, directory/SEO).
- **Wedge vs Meta** (what they structurally can't do): UPI-native money, ONDC alignment, vernacular/voice-first
  (Tamil SOV routing as moat prototype), messy high-trust categories (technicians you let indoors),
  relationship memory over transaction memory (switching costs deepen per booking).
- **API-first doctrine**: every merchant action headless before it gets UI. Test: if all our apps vanished
  and only the API remained, would the business still function? If no — it's a feature, not infrastructure.
- **Trust is the product**: approval cards as state machines (quoted → approved → executing → confirmed → rated),
  idempotency keys everywhere, verified-bookings-only ratings (= the data moat), human pauses for first-time
  merchants / over-threshold amounts / low confidence. Market accountability, not magic.
- **Anna Nagar doctrine**: one neighborhood, three services, fifty merchants. Density > spread; liquidity is local;
  ops fit on a bicycle; word-of-mouth needs a saturable container. Expand only on per-pincode repeat growth.
- **Timing**: 12–18 month window before Meta/funded clones operate here. Moat = merchant density + booking history
  + ratings data (ground truth no one can copy). Data moats outlive feature moats.
- **Pre-build checklist (Phase 0, current stage)**: 3 decisions (beachhead / first 3 services: cabs, technicians,
  one food flow / commission-leaning model) → merchant interviews (15–20 shops) → WhatsApp concierge test
  (20–30 manual bookings, repeat rate is the only metric) → rate-card photo collection → schema doc on paper →
  ONDC Chennai reconnaissance → one-page trust policy. Explicitly NOT now: registering merchants, launch dates,
  directory UI, fundraising on the story.

### B. Beachhead — UNDECIDED (lean: Anna Nagar or equivalent; must be walkable for founder)
### C. Concierge test — PENDING (see Phase 0 above)
### D. v0.5 — ✅ DONE this session (see SCALING.md). v0.6 candidates parked: plugin sandbox runtime,
#    cross-device handoff, SLM weights drop-in, merchant-services Phase 1.

## Session log
- 2026-10-01: connectors 1000x shipped (pooled transport, breakers, cache, webhooks,
  5 modules migrated, unsigned rejected live) → 134 tests, plan 130/130.
- 2026-10-01: connectors tier-1+2 shipped (telegram, calendar depth, github, razorpay,
  whatsapp business, youtube RSS; 12 providers; 5 real bugs caught) → 131 tests, plan 118/118.
- 2026-10-01: social connectors shipped (manifests, mock/x/linkedin, idempotent gated
  publish, chat→approval→post verified live) → 124 tests.
- 2026-10-01: fortify round shipped (32 indexes, N+1 fix, sentinel ×19 patterns, vault locks,
  bills invariants, weather cache; 4 real bugs caught) → 121 tests.
- 2026-10-01: learned memory shipped (multi-factor recall, dedup+promotion, TTL tiers,
  feedback loop, EVIDENCE.md + README) → 116 tests. Clean-room: ideas only, zero foreign code.
- 2026-10-01: code-review batch 4 shipped (Caddy, mounts, encrypted backups, dockerignore,
  CI contracts, liveness/readiness) → 112 tests. All 34 findings now fixed.
- 2026-10-01: code-review batch 3 shipped (voice binding, OAuth state, fail-closed critic,
  waiting states, capability matrix + mobile flows) → 104 tests. Next: batch 4 (delivery).
- 2026-10-01: code-review batch 2 shipped (per-ID ack, mobile retention + idempotency,
  scheduler validation, real retry + reconcile, size validation) → 99 tests. Next: batch 3.
- 2026-10-01: code-review batch 1 shipped (F01–F03, F13–F16, F19, F26–F29; 9 new evals,
  live verified incl. v3 envelopes + placeholder refusal) → 95 tests. Next: batch 2 (data loss).
- 2026-10-01: persistent specialists shipped (identity + triggers + tick + seed trio,
  7 endpoints, 2 evals, live verified) → 86 tests. Reference plan complete except
  browser sub-agent, computer-use, cloud always-on, model training.
- 2026-10-01: benchmark harness shipped (100 tasks × 8 cats, plan/live runner, history,
  interventions metric, tuned 74→100/100) → 84 tests. Next: persistent specialists.
- 2026-10-01: capability router shipped (goal+role tool scoring, keyword flags retired,
  3 evals, live agent loop verified) → 81 tests. Next: benchmark harness (100-task battery)
  or persistent specialists.
- 2026-10-01: policy engine shipped (risk tiers, scope eval, injection guards, chat gate,
  3 evals, live verified incl. confirm-intent) → 78 tests. Next: capability router
  (replacing keyword tool selection) or benchmark harness.
- 2026-10-01: memory package shipped (people/places/episodic/procedural/retrieval/consolidation,
  façade + router + scheduler kind, 3 evals, live verified) → 75 tests. Next: policy engine
  (risk tiers replacing keyword sentinel) or capability router.
- 2026-10-01: context engine shipped (event bus + snapshot + wake conditions + normalizers,
  router, 4 evals, live chat→event→wake→nudge verified) → 72 tests. Next: memory package
  (episodic/semantic/procedural + consolidation) or policy engine.
- 2026-09-30: hierarchy STEP 4 shipped (60-example planner pack, retrieval + few-shot compile,
  goal-planner skill, 4 evals, live chat compile mirrors pack) → 68 tests. Hierarchy complete:
  goal → objective → project → task → subtask → action → observe → verify → checkpoint.
- 2026-09-30: hierarchy STEP 3 shipped (verify engine, subtask walk, checkpoint, 3 evals,
  live auto-step verified) → 64 tests. Next: step 4 planner pack + 60-example evals.
- 2026-09-30: hierarchy STEP 2 shipped (action registry, validate, propose, 3 evals) → 61 tests.
  Next: step 3 observe/verify/checkpoint.
- 2026-09-30: hierarchy STEP 1 shipped (subtask table, insert/get/set, compile rule, 3 evals,
  live chat compile verified with 16 subtasks) → 58 tests. Next: step 2 (action registry).
  Constraints locked: chat-only entry, no new screens, additive wiring.
- 2026-09-30: nudge-hygiene fix from screenshot (basename paths, orphan goal/handoff filter,
  2-line home alerts) + stale probe cleanup → 55 tests.
- 2026-09-30: hardening round shipped + pushed (54 tests: recurring fix, WAL helper, memory locks,
  secrets audit, deep health, clamps). Agent strengthened, zero new features.
- 2026-09-30: v0.6 platform shipped + pushed (51 tests) → HANDOFF + SCALING updated.
- 2026-09-30: v0.5 shipped + pushed (48 tests) → HANDOFF + SCALING updated.
- 2026-09-30 (earlier): v0.4.x shipped + pushed (40 tests) → cloud pack shipped + pushed (42 tests) →
  merchant-services strategy discussion (no code) → HANDOFF.md created.
