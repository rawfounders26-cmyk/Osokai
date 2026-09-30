# Osok-AI — scaling plan (founder/CTO notes)

## v0.6 — ✅ DONE (shipped, verified, pushed to main)
- [x] **Plugin sandbox runtime**: allow-listed pack actions, perm-gated via grant ledger (default-deny), workspace file jail, network off unless `net.fetch` granted, per-call audit, per-pack kill-switch. Verified live: unknown action, jail escape, net-off, kill/revive, 4-row audit.
- [x] **Cross-device handoff**: goal snapshot (title/progress/next task) relayed sealed, single-accept with expiry + wrong-device rejection, resume nudge on accept. Verified live: create → pending → accept → re-accept 409.
- [x] **SLM weights drop-in**: URL fetch into the weights slot with size cap, GGUF magic verification, traffic flips automatically via existing status/routing. Bad URLs rejected with cleanup.

## v0.5 — ✅ DONE (shipped, verified, pushed to main)
- [x] **Client-held E2E keys**: X25519 device keypairs (private never leaves device), server stores pubkeys only, v2 envelopes via ECDH+HKDF+Fernet, blind relay store-and-forward. Server-verified blind: ciphertext at rest, full client roundtrip through server store.
- [x] **SLM provider slot**: llama_cpp/transformers/onnx backends, env-configured weights path, status endpoint, fail-soft escalate to Groq. SLM-zone chat integration with usage logging — weights drop in with zero code change.
- [x] **Wake-word + streaming voice**: PCM energy VAD, configurable keyword/threshold/cooldown, stream sessions with speech-end detection auto-transcribing via whisper.
- [x] **Spend optimizer**: per-task cost history, cheapest-capable routing policy (auto/groq-always/local-max), `/usage/optimize` report with projected SLM savings.
- [x] **Public share links**: unguessable expiring revocable capability URLs, read-only goal progress HTML, no-auth view, full lifecycle verified (200 → revoke → 404).
- [x] **Eval-gated auto-deploy**: `scripts/release-gate.sh` (evals + docker build + import smoke), CI release workflow auto-tagging `[release]` commits.
- [x] **Research digests**: interest topics CRUD, depth-1 nightly sweeps with citation nudges, `research_digest` scheduler kind.

## v0.4.x — ✅ DONE: outfit planner + bill splitting scale-up (chat-driven)
- [x] **Outfit**: calendar-aware occasion looks, 7-day no-repeat week plan, trip pack-a-bag with live weather, learned item scores (likes/wears/dislikes), laundry-cycle guard + reset, photo intake via vision. Chat: `plan my outfits`, `what should i wear to …`, `pack for N days in …`, `i wore …`, `laundry done`, `add … to wardrobe`.
- [x] **Bills**: chat quick-split, settle-up with one-tap UPI links, member UPI ids, monthly repeats (scheduler-posted), house ledger, receipt-scan drafts via vision, team-house links. Chat: `split 1200 for dinner with flat`, `settle up flat`, `repeat rent 9000 monthly in flat`, `house ledger for flat`.
- [x] **Surfaces**: mobile Outfit screen (week plan, pack, laundry, photo intake), Bill screen (scan receipt, UPI pay buttons, repeats, ledger), Split screen receipt prefill, Command Port works via chat with zero changes.

## v0.4 — ✅ DONE (shipped, verified, pushed to main)
- [x] **Scheduled autonomy**: cron-style jobs (daily HH:MM or every-N-min) for goal auto-steps, compiled briefings, research sweeps, nudge scans. 30s scheduler, run log, run-now, hub push.
- [x] **Marketplace sandbox enforcement**: risk-tiered perms, high-risk install ack, grant ledger with default-deny runtime `check()`/`guard()`, audit trail, star ratings + install-based reputation with low-rep warnings.
- [x] **Team billing + roles**: viewer/member/admin/owner hierarchy, role-gated approvals and member/budget management, per-seat AI spend from actor-attributed usage, team budget caps.
- [x] **E2E relay-lite**: Fernet-sealed envelopes, store-and-forward inbox, TTL + deliver-once pull. Server holds ciphertext only (step 1; client-held keys ride the same format later).
- [x] **SLM confidence routing**: `confidence()` scores every message; 1.0 answers on-device, 0.5–0.9 marked SLM-zone (escalates today), local calls logged with est. saved-$ on the dashboard.
- [x] **Voice sessions**: start/chunk/finish chunked-audio API feeding Groq whisper, returning text ready for `/voice/command`.

## v0.3 — ✅ DONE (shipped, verified, pushed to main)
- [x] **Usage/cost dashboard**: every LLM call logged (tokens, ms, $), monthly rollups, per-task leaders, budget caps that gate autonomous work. Nobody in this class shows cost — we do.
- [x] **Skill marketplace**: HMAC-signed packs, checksum + signature verification, one-tap install/enable/uninstall, cache-safe router rescan. Ships with habit-tracker + pdf-summarizer.
- [x] **Team mode**: teams, members, shared goal trees, attributed multi-user approvals. Personal data stays personal; only shared goals cross the boundary.
- [x] **Local-first fast lane**: time/date/calc/conversions/status answer on-device in microseconds, zero tokens. Same interface ready for a future small model.
- [x] **Voice loop**: `/voice/command` (one call: route + short spoken reply) and `/voice/speak` (host TTS, degrades cleanly without pyttsx3).
- [x] **Surfaces**: mobile dashboard shows nudges + AI spend; api service covers nudges/usage/market/teams/voice/auto-step.

## v0.2 — ✅ DONE (shipped, verified, pushed to main)
- [x] **Proactive engine**: 60s tick, deduped nudges, 8am briefing, hub push.
- [x] **Orchestrator**: planner→executor→critic auto-steps, daily cap, human pause points, history log.
- [x] **Memory 2.0**: salience-ranked episodic facts, recall API, rolling LLM summary every 50 turns.
- [x] **RAG upgrade**: overlap chunking, hybrid BM25+path-boost ranking, citation ids, grounded `/rag/answer`.
- [x] **Reliability**: per-IP rate limits (heavy endpoints 60/min), request-id tracing, device presence + offline outbox.
- [x] **DevOps**: Dockerfile, compose, GitHub Actions CI, versioned `/updates/latest`.

## Next (v0.7) — merchant wedge + hardening
1. **Merchant services Phase 1** (needs explicit user go — still discussion-only): machine-readable schemas for cabs/technicians/food (see HANDOFF.md thread A).
2. **SLM quantize + benchmark**: pick weights, measure quality/latency vs Groq per task, publish the numbers on the dashboard.
3. **Handoff for loops + drafts**: extend snapshots beyond goals (open loops, receipt drafts, packing lists).

## Moats to protect
- Encrypted vault + approval mediation (payment/captcha) — trust story.
- 51 nightly evals gating every release — reliability story.
- Single SQLite brain, portable, no vendor lock — exit story.
