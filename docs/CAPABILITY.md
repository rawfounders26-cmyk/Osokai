# Osok-AI capability matrix (F31) — truth in advertising

Status key: ✅ working (verified) · 🟡 partial/stub · 📋 planned.

## Chat + agent core
| Capability | Status | Notes |
|---|---|---|
| Chat fast intents | ✅ | 30+ intent types, Tamil SOV, eval battery |
| Agent tool loop (38 tools) | ✅ | capability-routed, live verified |
| Goal trees + subtasks + verify | ✅ | checkpoint only on verify-pass |
| Planner pack (60 examples) | ✅ | few-shot compile, retrieval evals |
| Benchmark 100-task | ✅ | plan 100/100, live opt-in |

## Memory / context
| Capability | Status | Notes |
|---|---|---|
| Turns + facts + summary | ✅ | |
| People/places/episodic/routines | ✅ | unified recall |
| Event bus + wake conditions | ✅ | consume-once firing |
| Supabase mirror | 🟡 | config present, mirror not continuously synced — stub |

## Money / bills
| Capability | Status | Notes |
|---|---|---|
| Groups/expenses/settle/UPI | ✅ | incl. mobile create + UPI pay |
| Receipt scan | ✅ | vision draft + confirm (needs Groq key) |
| Recurring + scheduler post | ✅ | idempotency fixed |
| Team billing | ✅ | organizational labels, single-owner |

## Voice / mobile
| Capability | Status | Notes |
|---|---|---|
| Transcribe endpoint | ✅ | multipart binding fixed (needs Groq key + python-multipart) |
| Voice sessions/streaming | ✅ | protocol verified; whisper needs key |
| Offline queue + idempotency | ✅ | full-suffix retention, server replay |
| Expo app | ✅ | files read/preview, bills, outfit, goals |
| Flutter app | 📋 | legacy tree, known defects — Expo is the surface |

## Connectors / OAuth
| Capability | Status | Notes |
|---|---|---|
| Token pairing | ✅ | |
| OAuth login-CSRF state | ✅ | single-use, 10-min, provider-bound |
| Live Gmail/Outlook/Slack sync | 🟡 | needs user OAuth creds + polling |

## E2E / sync
| Capability | Status | Notes |
|---|---|---|
| Relay-lite + v2/v3 envelopes | ✅ | per-ID ack, sender signatures |
| Presence + outbox | ✅ | per-ID ack |
| Public share links | ✅ | signed, revocable, expiring |

## Platform
| Capability | Status | Notes |
|---|---|---|
| Docker + Caddy TLS | ✅ | directive fixed (see Batch 4) |
| Backups | 🟡 | scripts work; encryption + volume alignment land in Batch 4 |
| CI evals | ✅ | 95+ and growing |
| Packaged .exe | 🟡 | sidecar path fixed as found; full installer test pending |
