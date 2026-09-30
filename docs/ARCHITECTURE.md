# Osok-AI — architecture (v0.2)

Local-first persistent personal agent. One brain, every surface.

```
┌──────────┐ ┌──────────┐ ┌───────────┐
│ Command  │ │ Mobile   │ │ Chrome    │   thin clients: chat UI + approvals
│ Port .exe│ │ Expo app │ │ extension │   + fill mediation + offline queue
└────┬─────┘ └────┬─────┘ └─────┬─────┘
     └────────────┼─────────────┘
          HTTPS + token (LAN)
     ┌────────────▼─────────────┐
     │  FastAPI gateway (:8765) │  auth, rate limits, request ids,
     │  /chat /ws/sync /nudges  │  proactive loop, orchestrator
     └────────────┬─────────────┘
  ┌───────────────┼────────────────┐
  │               │                │
agent loop     goal trees +     vault-2 (Fernet,
(planner→       orchestrator     policies, TOTP,
 executor→      (planner→        DPAPI, audit)
 critic)        executor→critic)
  │               │                │
memory 2.0 ── RAG (FTS5 hybrid + citations) ── skills (85 roles)
(episodic facts, rolling summary)
  │
proactive engine (60s tick: loops, approvals, goals, bills, briefing)
  │
SQLite (durable) ── optional Supabase mirror
```

Key flows:
- **Chat**: fast intent → system Chrome | big goal → compile tree | else agent tool loop.
- **Autonomy**: proactive tick writes nudges → hub push → all surfaces refresh; orchestrator `auto-step` advances goals with critic review, pausing for humans on approval/human/wait tasks.
- **Offline**: presence heartbeat + per-device outbox; phone picks up where desktop left off.
- **Trust**: Fernet vault (policies/domain allowlist/audit), approvals survive restarts, brute-force lockout, rate limits.
