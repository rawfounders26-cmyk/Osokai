# Osok-AI
Local-first presistent personal agent. See PRD.md.

## Wiring
All UIs -> `http://127.0.0.1:8765` (API_BASE_URL):
- desktop (Electron, Alt+Space), mobile (Flutter 5 tabs), extension (MV3)

## Run backend
```
cd backend
copy .env.example .env  # paste GROK_API_KEY + SUPABASE_URL + SUPABASE_ANON_KEY
pip install -r requirements.txt
uvicorn app.main:app --port 8765
# test: curl http://localhost:8765/health
```

## Desktop
```
cd desktop
npm install
npm start  # Alt+Space toggles Command Port
npm run dist-win  # .exe
npm run dist-mac  # .dmg (run on Mac)
```

## Mobile / Extension
- mobile: `flutter run --dart-define=API_BASE_URL=http://<PC-LAN-IP>:8765`
- extension: load unpacked `extension/`, backend must be running.

## learned memory (our own design)
- Multi-factor recall (`GET /memory/recall-explain` shows every factor: salience, keyword,
  recency, relationship, goal relevance, confirmation, source trust)
- Write-time dedup + promotion, TTL tiers (7/30/180/permanent), recall feedback loop
  (`POST /memory/confirm`), nightly consolidation (`POST /memory/consolidate`)
- Evidence per release: `docs/EVIDENCE.md`

## v0.3 scale-up
- Usage/cost dashboard (`/usage/summary`, `/usage/budget`) · skill marketplace (`/marketplace`)
- Team mode (`/teams/*`) · local fast lane (zero-token answers) · voice loop (`/voice/command`, `/voice/speak`)
- Mobile dashboard: nudges + AI spend · orchestrator respects budget caps

## v0.2 scale-up (kept)
- Usage/cost dashboard (`/usage/summary`, `/usage/budget`) · skill marketplace (`/marketplace`)
- Team mode (`/teams/*`) · local fast lane (zero-token answers) · voice loop (`/voice/command`, `/voice/speak`)
- Mobile dashboard: nudges + AI spend · orchestrator respects budget caps
- Proactive engine (nudges, 8am briefing) · orchestrator auto-steps (`POST /goaltrees/{id}/auto-step`)
- Memory 2.0 facts/recall · hybrid RAG with citations (`POST /rag/answer`)
- Rate limits + request ids · device presence + offline outbox · Docker + CI
- See `docs/ARCHITECTURE.md` and `docs/SCALING.md`.

```
docker compose up --build  # backend on :8765
```
