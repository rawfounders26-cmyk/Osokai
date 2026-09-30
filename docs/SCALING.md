# Osok-AI — scaling plan (founder/CTO notes)

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

## Next (v0.5) — full versions of v0.4 foundations, vs Instinct & Muse
1. **Client-held E2E keys**: graduate relay-lite to true end-to-end (X25519 device keys, server never holds plaintext keys). Instinct does cloud sync; we keep the local-first guarantee.
2. **Bundled SLM weights**: graduate confidence routing from patterns to an on-device small model; Groq only on low confidence. Zero-latency, zero-cost default.
3. **Wake-word + streaming voice**: hands-free surface with barge-in; opponents treat voice as a feature, we make it a surface.

## Next (v0.6) — the separation round
7. **Plugin sandbox runtime**: marketplace packs run in a restricted executor (allow-listed tools, file-scope jail, network off by default) — signed + sandboxed beats Muse's unsigned extensions.
8. **Cross-device handoff**: start a goal on desktop, continue mid-step on phone — orchestrator state streams over the encrypted relay with conflict-free resume.
9. **Proactive research digests**: nightly topic sweeps per user interest compiled into the 8am briefing with citations — Instinct answers questions; we deliver answers first.
10. **Spend optimizer**: auto-pick cheapest capable model per task from usage history; show saved-$ on the dashboard — turns the cost moat into a growth loop.
11. **Public share links**: read-only goal/progress pages with revocation — viral loop for team adoption that neither competitor has in this form.
12. **Eval-gated auto-deploy**: CI runs the full 32-eval battery + live smoke on a scratch DB; green builds tag releases automatically.

## Moats to protect
- Encrypted vault + approval mediation (payment/captcha) — trust story.
- 37 nightly evals gating every release — reliability story.
- Single SQLite brain, portable, no vendor lock — exit story.
