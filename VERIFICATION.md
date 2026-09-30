# Osok-AI — VERIFICATION (what's real vs stub)

Updated 2026-09-29. Everything marked LIVE was executed, not assumed.

## LIVE (tested end-to-end)
- Chat: normal + agent tool loop (Groq function calling) + salvage parser
- Fast intents: open app/URL, YouTube play/watch (songs + episodes), Google/images search, shopping browse, Gmail/Outlook shortcuts
- Approvals: create → pending on all surfaces → Allow/Deny from extension popup or mobile chat; **persisted in SQLite, survive backend restarts**
- Real-time sync: `/ws/sync` push on every mutation (socket test: rev bump received)
- Connectors: 5 providers with meta/enabled/honest status/unread + PATCH enable + vault-encrypted tokens
- Encrypted vault: cards (number/CVV masked), logins, connector tokens (Fernet, key in `.env`); decrypt-only-at-entry; extension autofill on Flipkart/Amazon checkout
- Bill splitter: groups/expenses/equal+custom splits/debt-simplify/settle/activity — math verified
- Month history: buckets + labels + per-day graph data from real turns
- Desktop: Alt+Space toggle, traffic lights, vertical icon rail, gear settings, mini pill with edge dock + bell polling
- Mobile (Expo Go): 5 tabs + bill/split routes, file routes, live sync
- pytest suite: `backend/tests/test_Osok-AI.py` — 8 tests green (intents, router, bills math, vault, durable approvals, goal prices)
- Goals: create/list/delete/manual-check + change/price/text watches, deduped alerts merged into bell count
- Takeover console: `/browser/state` + `/browser/screenshot` wired to Command Port 📷 (shows live VM browser + state text)
- Real OAuth code: Gmail/Microsoft/Slack authorize + callback + encrypted token store + auto-refresh + live unread; returns exact missing-key instructions without credentials (needs your CLIENT_ID/SECRET to activate)
- Durable task runs: agent goals tracked with progress + receipts in SQLite, retryable, visible in `/tasks/runs`
- Proactive briefing: `/briefing` aggregates approvals, debts, goal alerts, weather, outfit pick, running tasks
- Trusted sharing: osokai-to-Osok-AI encrypted bundles (`/share/export|import|list`), code-based decrypt
- Voice: mic button in mobile chat → Groq whisper `/voice/transcribe` → text lands in the input box
- Auth hardening: 5-fails-per-IP lockout + `/auth/rotate` (pro proven: 5×401→429; legit traffic resets)

## STUB / HONEST GAPS (never faked)
- OAuth live counts: code complete, needs YOUR Google/Microsoft/Slack CLIENT_ID+SECRET in `.env` to activate
- browser-use CLI upgraded syntax (Python-over-stdin) — adopted; needs one-time Chrome "Allow remote debugging" tick on the chrome://inspect popup it opened
- WhatsApp: unofficial pairing only (no Meta API)
- Connector unread counts: 0 until real polling; bell demo uses `/notifications/simulate`
- `.dmg` Mac build: code ready, must be built on a Mac
- Play Store / App Store binaries: not yet packaged
- TEE/confidential-VM style crypto: not attempted; local-first + Fernet instead
- Flutter app: ported screens, needs `flutter pub get` + on-device build test
- Groq free tier: 7k tokens/min — agent loop trims context + retries on 429
