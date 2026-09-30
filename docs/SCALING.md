# Osok-AI — scaling plan (founder/CTO notes)

## v0.2 — shipped (this round)
- **Proactive engine**: 60s tick, deduped nudges, 8am briefing, hub push.
- **Orchestrator**: planner→executor→critic auto-steps, daily cap, human pause points, history log.
- **Memory 2.0**: salience-ranked episodic facts, recall API, rolling LLM summary every 50 turns.
- **RAG upgrade**: overlap chunking, hybrid BM25+path-boost ranking, citation ids, grounded `/rag/answer`.
- **Reliability**: per-IP rate limits (heavy endpoints 60/min), request-id tracing, device presence + offline outbox.
- **DevOps**: Dockerfile, compose, GitHub Actions CI, versioned `/updates/latest`.

## Next (v0.3) — 
1. **On-device small model**: route trivial chat locally (zero latency/cost), escalate to Groq only when stuck. Instinct is cloud-only; Muse rents models — local-first is the moat.
2. **Skill marketplace**: versioned, signed community skills with sandbox permissions. Muse has extensions; ours are signed + policy-gated by vault-2.
3. **E2E-encrypted sync**: replace LAN token sync with encrypted cloud relay (Supabase) so phone works off-network. Instinct does this; we keep the local-first guarantee.
4. **Voice loop**: wake-word + streaming STT/TTS for hands-free; opponents treat voice as a feature, we make it a surface.
5. **Usage-based cost dashboard**: per-task token spend + budgets — nobody in this class shows it; founders love it.
6. **Team mode**: shared goal trees + multi-user approvals (the wedge into SMBs that Instinct/Muse price out).

## Moats to protect
- Encrypted vault + approval mediation (payment/captcha) — trust story.
- 22+ nightly evals gating every release — reliability story.
- Single SQLite brain, portable, no vendor lock — exit story.
