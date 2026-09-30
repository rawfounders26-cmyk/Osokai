# Osok-AI — PRD (Product Requirements Document)

**Codename:** Osok-AI | **Type:** local-first Muse-type personal agent | **Date:** 2026-09-28

## 1. Vision
Human-like agent that codes, organizes, researches. Local-first, private by default. Command Port on desktop, monitor + chat on mobile, web tasks via Chrome extension.

## 2. Goals / Non-goals
Goals: persistent memory, plan->act loop, Kinso-style unified inbox, cross-device.
Non-goals V1: no cloud TEE (like Muse Confidential VM), no auto-purchase without approval, no full WhatsApp automation.

## 3. Scope
- Backend: Python FastAPI + Grok LLM + Supabase (sync) + SQLite local mirror
- Command Port desktop: .exe (Win) + .dmg (Mac), tab-bar Send/Screenshot/3-dots
- Mobile: Play Store + App Store, 5 tabs: Home, Chat, Files, History, Settings+Connectors
- Chrome extension MV3: read tab -> send to backend

## 4. Architecture
```
[Command Port] [Mobile] [Extension]
      \            |           /
   FastAPI http://localhost:8765 (/health,/chat,/tasks,/files,/inbox,/connectors)
       Agent Core: planner/executor + Sentinel gate + memory + connector hub
       Tools: files, terminal, code-run, web-search, inbox-ranker
       Data: Supabase (cloud sync) + SQLite local.db mirror + workspace/ + audit.log
       Auth: Supabase Auth + OS keychain vault (Fernet), surrogate tokens
```
Wiring: all frontends use `API_BASE_URL` env (default localhost:8765). Same JSON contract in `shared/api-contract.json`.

## 5. Tech stack
- Brain: Python 3.12, LiteLLM-style Grok client (`xAI Grok API`), Supabase-py
- API: FastAPI + Uvicorn + WebSocket `/ws/tasks`
- Memory: Supabase tables + local SQLite cache
- Desktop: Electron + Vite + React + Tailwind, electron-builder, PyInstaller sidecar
- Mobile: Flutter, supabase_flutter, http
- Extension: MV3 TypeScript, fetch to localhost
- Packaging: .exe/.dmg installers, EAS/Play/App Store later

## 6. Shortcuts (F3.1)
- Primary universal: **Alt+Space (Win) / Option+Space (Mac)** — show/hide Command Port, focus Send. Esc hides. Customizable in Settings, synced to mobile.
- Win impl: low-level hook (WH_KEYBOARD_LL) because Alt+Space = system menu; fallback Ctrl+Alt+P if blocked.
- Mac impl: globalShortcut Option+Space, needs Accessibility + Input Monitoring permission prompt.
- Installer enables autostart on login, writes default to config.json.

## 7. Connectors (3-dots + mobile Settings)
Gmail OAuth, Outlook MS-Graph, Slack, Discord, WhatsApp (Baileys unofficial, last). Each connects individually, Kinso-style ranking + drafting + morning briefing. Tokens in vault only.

## 8. Mobile screens
Home/Dashboard (running tasks, priority inbox, briefing), Chat (goals), Files (workspace browser), History (running+previous + logs), Settings+Connectors (per-service connect, permissions, memory clear, shortcut display).

## 9. Phases + acceptance
P1 backend health+chat, P2 desktop shell, P3 connectors, P4 mobile+ext. V1 accept: goal -> plan -> sentinel ask if sensitive -> complete -> persists -> visible in History.

## 10. Env / keys (you provide)
`GROK_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` in `backend/.env` (see `.env.example`). Frontends only need `API_BASE_URL`.

## 11. Agent powers (any-task)
- Fast regex intents: youtube play, google/images search, open app/URL (milliseconds).
- General tool loop (`backend/app/agent.py`, Groq function calling): open_url, open_app, browser (browser-use CLI headless), web_search.
- Skills copied from osokai into `backend/skills/`: browser-use, agent-browser, browser-automation, playwright-skill, web-search-scraper-api-skill, search, gmail/whatsapp-automation (docs), youtube-full.
- Extension auto-completes YouTube (search->click->play) via content script.

## 12. Routing (locked)
- Simple (open app/URL, play/watch song/video/episode, search, shopping browse, vault ops): instant regex intents -> system Chrome via extension.
- Complex (files, research, plans, multi-step browser, logins/forms/scraping): agent loop, SAME VM workspace/ the mobile Files tab shows.
- Sensitive (buy/order/pay/send/delete): dual Approve/Reject (extension popup + mobile chat) before anything runs.
- YouTube covers songs AND episodes/videos; mobile opens them in the phone app directly.
