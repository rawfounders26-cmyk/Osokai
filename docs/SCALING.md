# Osok-AI — scaling plan (founder/CTO notes)

## v0.3 — shipped (this round)
- **Usage/cost dashboard**: every LLM call logged (tokens, ms, $), monthly rollups, per-task leaders, budget caps that gate autonomous work. Nobody in this class shows cost — we do.
- **Skill marketplace**: HMAC-signed packs, checksum + signature verification, one-tap install/enable/uninstall, cache-safe router rescan. Ships with habit-tracker + pdf-summarizer.
- **Team mode**: teams, members, shared goal trees, attributed multi-user approvals. Personal data stays personal; only shared goals cross the boundary.
- **Local-first fast lane**: time/date/calc/conversions/status answer on-device in microseconds, zero tokens. Same interface ready for a future small model.
- **Voice loop**: `/voice/command` (one call: route + short spoken reply) and `/voice/speak` (host TTS, degrades cleanly without pyttsx3).
- **Surfaces**: mobile dashboard shows nudges + AI spend; api service covers nudges/usage/market/teams/voice/auto-step.

## v0.2 — shipped (previous round)
- **Proactive engine**: 60s tick, deduped nudges, 8am briefing, hub push.
- **Orchestrator**: planner→executor→critic auto-steps, daily cap, human pause points, history log.
- **Memory 2.0**: salience-ranked episodic facts, recall API, rolling LLM summary every 50 turns.
- **RAG upgrade**: overlap chunking, hybrid BM25+path-boost ranking, citation ids, grounded `/rag/answer`.
- **Reliability**: per-IP rate limits (heavy endpoints 60/min), request-id tracing, device presence + offline outbox.
- **DevOps**: Dockerfile, compose, GitHub Actions CI, versioned `/updates/latest`.

## Next (v0.4) — vs Instinct & Muse
1. **E2E-encrypted sync relay**: phone works off-LAN via encrypted Supabase relay; server never sees plaintext. Instinct does cloud sync; we keep the local-first guarantee.
2. **On-device small model (full)**: graduate the fast lane from patterns to a bundled SLM; escalate to Groq only on low confidence. Zero-latency, zero-cost default.
3. **Wake-word + streaming voice**: hands-free surface with barge-in; opponents treat voice as a feature, we make it a surface.
4. **Marketplace sandbox enforcement**: per-pack permission gates (loops.write, files.read…) actually enforced at install + runtime, plus publisher reputation.
5. **Team billing + roles**: per-seat usage rollups, admin/member/viewer roles, team budgets — the SMB wedge Instinct/Muse price out.
6. **Scheduled autonomy**: cron-style goal auto-steps (nightly research sweeps, morning briefings compiled, not just pushed).

## Moats to protect
- Encrypted vault + approval mediation (payment/captcha) — trust story.
- 32 nightly evals gating every release — reliability story.
- Single SQLite brain, portable, no vendor lock — exit story.
