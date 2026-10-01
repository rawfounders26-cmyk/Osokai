# Osok-AI — scaling plan (founder/CTO notes)

## benchmark harness — ✅ DONE: 100-task battery, plan 100/100, north-star metric
- [x] `app/benchmark/tasks.py`: 100 tasks × 8 categories (browser/research/email_calendar/coding/personal/bills/wardrobe/long_running) with expected tools + approval flags.
- [x] `app/benchmark/run.py`: PLAN mode (offline routing+gate accuracy, CI-safe) + LIVE mode (env-gated, budget-capped, cost/intervention tracking) + run history + `interventions_per_goal` (event-window attribution).
- [x] Tuned 74 → **100/100** plan score. Every fix was principled: lakh/crore parsing, email/complaint/leave gating, money-reminder ≠ payment, planning-with-budget is free.
- [x] Endpoints + first live numbers: bills 12/12, avg interventions 0.15/goal.

## capability router — ✅ DONE: goal-aware tool selection (keyword flags retired)
- [x] `app/capabilities.py`: 38 tools scored by weighted keyword phrases + role-signal overlap; base capabilities always ride; capped at 18; every inclusion explained.
- [x] Wired into `run_goal` with safe fallback. Bidirectional substring matching (catches `ppt`→`pptx`).
- [x] Live-verified agent loop on the routed set. 3 evals: domain tools, base+cap+determinism, role signal.

## policy engine — ✅ DONE: risk tiers + scope + injection guards (sentinel upgraded)
- [x] `app/policy/` package: `risk.py` (LOW/MEDIUM/HIGH/CRITICAL with amount thresholds + reasons), `scope.py` (tool+destination+quiet-hours evaluation), `guards.py` (12 instruction-override patterns + scrub markers).
- [x] Chat gate: policy first, injection scan, keyword sentinel as fallback. Verified live: benign→local, email→approval, injection→confirm-intent approval.
- [x] Caught live: `\b` vs underscores (`send_email`) — scope text normalized.

## memory package — ✅ DONE: people/places/episodic/procedural + consolidation (façade untouched)
- [x] `app/memory/` package (`memory.py` → `__init__.py`, all 72 prior tests green unmodified): people, places, episodic log + decay, routines with use-counts, unified salience+recency recall across facts/people/places/episodes.
- [x] `consolidation.run()`: events → episodes (idempotent), 90-day decay, wake-fired prune; `memory_consolidate` scheduler kind. Verified live.
- [x] `memory/api.py` router (people/places/recall-all/consolidate) + mobile wrappers. Live-verified end-to-end, probe rows cleaned.

## context engine — ✅ DONE: event bus + snapshot + wake conditions (no new screens)
- [x] `app/context/events.py`: normalized bus (19 types), validated emit, indexed list. Emitters in goals/loops/approvals/calendar/bills/tasks (lazy, guarded, never-raise).
- [x] `app/context/store.py`: on-demand world snapshot (goals, approvals, loops, today, events, spend) + one-paragraph brief for prompts.
- [x] `app/context/wake.py`: stored WHEN-event-THEN conditions (nudge/loop/schedule), match filters, consume-once firing inside the proactive tick. Verified live: chat loop → event → wake → nudge.
- [x] `app/context/api.py` router (7 endpoints, one include — monolith rule honored) + mobile wrappers.
- [x] Fixed real test-pollution trap along the way (dual `app.*` vs top-level modules now patched both ways in evals).

## hierarchy STEP 4 — ✅ DONE: planner pack + 60-example battery (quality compounds)
- [x] `app/planner_pack.py`: all 60 examples as data (goal-title-weighted retrieval, few-shot `compile_prompt`, vault/approval hard rules).
- [x] `goal-planner` skill pack: decomposition doctrine for the router.
- [x] Wired into `compile_goal`; live-verified (family-trip compile mirrors the pack example with mixed kinds).
- [x] Battery: pack shape (60 examples, valid kinds), sensitive-kind rules (#53 vault/human-wait, #46/#55 approval), retrieval accuracy, prompt injection.

## hierarchy STEP 3 — ✅ DONE: observe/verify/checkpoint (correctness gate)
- [x] `app/verify.py`: `execute()` runs one validated action with evidence; `verify()` re-reads world state (file exists, event on calendar, loop open, HTTP 200, draft id); `run_verified()` retries once, then escalates.
- [x] Orchestrator walks subtasks: propose → execute → verify → checkpoint subtask done ONLY on verify-pass; parent task completes when all subtasks verified; tasks without subtasks keep the legacy path.
- [x] Fixed layering bug found by evals: `_next_task` queried the orchestrator DB instead of goal tables.
- [x] Live-verified auto-step end-to-end. Next: step 4 planner pack + 60-example evals.

## hierarchy STEP 2 — ✅ DONE: action registry + validation (contract only, no execution yet)
- [x] `app/actions.py`: 12-action closed registry (args, types, effects, approval flags).
- [x] `validate()`: unknown actions rejected, required-arg/type checks, workspace jail, http(s) URLs, sensitive actions flagged for approval.
- [x] `propose()`: deterministic subtask → candidate actions (calendar/email/search/open/create/remind/vault), human/approval kinds map to ask/notify, safe default never empty.
- [x] Next: step 3 observe/verify/checkpoint (execution + correctness gate).

## hierarchy STEP 1 — ✅ DONE: subtask level (structure only, chat entry unchanged)
- [x] `subtasks` table + insert/get/set, `get_tree()` nests subtasks per task, progress math untouched.
- [x] Compile rule: 2–6 subtasks only for multi-step/outside-world tasks, atomic actions stay flat, hard cap 6.
- [x] Live-verified via chat ("help me prepare… interview" → 3 objectives, 8 tasks, 16 subtasks). No new screens, additive keys only.
- [x] Next: step 2 action registry → step 3 observe/verify/checkpoint → step 4 planner pack + 60-example evals.

## hardening round — ✅ DONE (no new features; strength only)
- [x] **Recurring-bill double-post fixed**: `last_post` update never committed (split-connection bug) — scheduler reposted every 30s. Single-connection fix + idempotency eval.
- [x] **Shared DB helper** (`app/db.py`): WAL mode + 5s busy timeout + FK pragmas across all 26 modules. Real DB confirmed on WAL.
- [x] **Thread-safe memory**: shared connection + scheduler/chat threads were silently losing writes (12/20 in test). RLock around all memory writes; concurrency eval now 20/20.
- [x] **Secrets audit**: no .env/.db/keys tracked; no hardcoded tokens in code.
- [x] **Deep health**: `/health` now reports db writability, free disk MB, version.
- [x] **Input clamps**: list limits and recall bounded server-side.
- [x] **Hardening evals**: concurrency smoke, malformed-input battery (12 fail-soft paths), recurring idempotency, nudge hygiene (orphan refs filtered, no path leaks).

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
- 84 nightly evals gating every release — reliability story.
- Single SQLite brain, portable, no vendor lock — exit story.
