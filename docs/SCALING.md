# Osok-AI — scaling plan (founder/CTO notes)

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

## Next (v0.4) — vs Instinct & Muse
1. **E2E-encrypted sync relay**: phone works off-LAN via encrypted Supabase relay; server never sees plaintext. Instinct does cloud sync; we keep the local-first guarantee.
2. **On-device small model (full)**: graduate the fast lane from patterns to a bundled SLM; escalate to Groq only on low confidence. Zero-latency, zero-cost default.
3. **Wake-word + streaming voice**: hands-free surface with barge-in; opponents treat voice as a feature, we make it a surface.
4. **Marketplace sandbox enforcement**: per-pack permission gates (loops.write, files.read…) actually enforced at install + runtime, plus publisher reputation.
5. **Team billing + roles**: per-seat usage rollups, admin/member/viewer roles, team budgets — the SMB wedge Instinct/Muse price out.
6. **Scheduled autonomy**: cron-style goal auto-steps (nightly research sweeps, morning briefings compiled, not just pushed).

## Next (v0.5) — the separation round
7. **Plugin sandbox runtime**: marketplace packs run in a restricted executor (allow-listed tools, file-scope jail, network off by default) — signed + sandboxed beats Muse's unsigned extensions.
8. **Cross-device handoff**: start a goal on desktop, continue mid-step on phone — orchestrator state streams over the encrypted relay with conflict-free resume.
9. **Proactive research digests**: nightly topic sweeps per user interest compiled into the 8am briefing with citations — Instinct answers questions; we deliver answers first.
10. **Spend optimizer**: auto-pick cheapest capable model per task from usage history; show saved-$ on the dashboard — turns the cost moat into a growth loop.
11. **Public share links**: read-only goal/progress pages with revocation — viral loop for team adoption that neither competitor has in this form.
12. **Eval-gated auto-deploy**: CI runs the full 32-eval battery + live smoke on a scratch DB; green builds tag releases automatically.

## Moats to protect
- Encrypted vault + approval mediation (payment/captcha) — trust story.
- 32 nightly evals gating every release — reliability story.
- Single SQLite brain, portable, no vendor lock — exit story.
