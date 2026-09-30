# Osok-AI — session handoff (read this + docs/SCALING.md in every new session)

> Living continuity file. Update at the end of every session (discussion or build)
> until merchant-services building starts. Conversations are RAM; this file is disk.

## Where we are
- **Version**: v0.4.x (cloud pack latest). **Tests**: 42/42 green.
- **Last shipped**: v0.4.x feature scale-up — outfit planner (occasion/week-plan/pack/scores/laundry/vision intake)
  + bill splitting (quick-split/UPI links/repeats/ledger/receipt-scan/team-house) + cloud pack
  (prod compose + Caddy TLS, portable data dirs, secrets/backup scripts, DEPLOY.md, CI docker build).
- **Before that**: v0.4 platform (scheduled autonomy, sandbox enforcement, team billing, relay-lite,
  SLM confidence routing, voice sessions) · v0.3 (usage dashboard, signed marketplace, team mode,
  fast lane, voice loop) · v0.2 (proactive engine, orchestrator, memory 2.0, hybrid RAG, rate limits, Docker/CI).
- **Repo**: `github.com/rawfounders26-cmyk/Osokai`, branch `main`.

## What's paused / what's next
- **v0.5 platform work ON HOLD** — resume only when user says "start v0.5".
- **Current front line**: merchant-services ("Muse-connectors for India") — DISCUSSION ONLY, Phase 0 validation.
  No code until user says build.

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
### D. v0.5 platform items — parked: client-held E2E keys, bundled SLM, wake-word/streaming, spend optimizer,
#    public share links, eval-gated auto-deploy, proactive research digests (see SCALING.md Next v0.5/v0.6)

## Session log
- 2026-09-30: v0.4.x shipped + pushed (40 tests) → cloud pack shipped + pushed (42 tests) →
  merchant-services strategy discussion (no code) → HANDOFF.md created. Next: Phase 0 validation or user calls v0.5.
