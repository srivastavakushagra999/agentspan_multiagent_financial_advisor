# Project: Multi-Agent Expert System (Agentspan)

## Goal
Side/portfolio project to learn multi-agent frameworks + MCP-style patterns, closing skill gaps identified for AI engineer roles (esp. Capgemini "Agentic AI Engineer" JD — CrewAI/AutoGen/Semantic Kernel, MCP agent-to-agent comms, RAG depth).

Not for production banking use — this is a personal/learning project (separate from BankerIQ). No bank-related data or context belongs here.

## Stack
- **Agent runtime**: Agentspan (https://agentspan.ai/) — `pip install agentspan` (currently `0.2.0`, latest) — durable execution, built on Conductor (open-source, MIT licensed, self-hosted)
- **Server**: `agentspan server start` — runs locally on `localhost:6767`. Its own execution-trace DB lives at `~/.agentspan/server/agent-runtime.db` (SQLite by default; `SPRING_PROFILES_ACTIVE=postgres` + `SPRING_DATASOURCE_*` env vars to point it at a custom Postgres instead — this is a fully standard DB we own, no lock-in, could sync/export to Langfuse etc. later if wanted).
- **LLM**: Anthropic Claude (`anthropic/claude-sonnet-4-6`)
- **DB (our own conversation memory, separate from Agentspan's trace DB above)**: SQLite, `memory.db` in project root (gitignored) — built, see `agents/memory.py` and Conversation Memory section below.
- **UI**: Streamlit (`app.py`, project root) — chat interface, streams progress events live, wraps `router` + `get_context`/`save_message`. Run with `streamlit run app.py`. Built entirely by Claude at Kushagra's explicit request ("I won't learn that") — the one piece of this project that's an exception to the hands-on-build-it-yourself pattern used everywhere else.
- **Data providers (decided, in use)**:
  - News (financial + political, merged into one agent): **NewsAPI.org** `/v2/everything` — free dev tier, 100 req/day, query-based keyword search.
  - Stocks + crypto price/technical data: **Alpaca Market Data API** (`data.alpaca.markets`) — free tier, 200 req/min, ~15min delay, covers both stocks (`/v2/stocks/bars`, `/v2/stocks/trades/latest`) and crypto (`/v1beta3/crypto/us/bars`, `/v1beta3/crypto/us/latest/trades`) with the same key pair. Chosen over Tiingo (no crypto on free tier) and financialdata.net (stock data ~1yr stale on free tier; commodities endpoint still free there if ever needed).
  - Technical indicators: computed ourselves (not from a paid indicator API) — % change and SMA in plain Python, RSI via `pandas-ta-classic` (NOT `pandas-ta` — that's unmaintained and broken on numpy 2.0+; `pandas-ta-classic` is the actively maintained fork).
- **Deployment target for later**: Hetzner VPS (existing infra used for other personal projects)

## Architecture
```
router (strategy="handoff")
  ├── news_agent    — financial + political news search/summarize (merged; NOT split into two agents)
  └── chart_agent   — stock + crypto price data + technical indicators (RSI/SMA/% change), 3 horizons (short/medium/long)
```
Router decides which specialist handles each query (or both, sequentially, via handoff — see known issue below re: `output_type` + router).
`backtest_agent` (simple rule-based long/short simulation on historical data, results saved for reference — explicitly NOT auto-improving/ML) is a noted future addition, not yet started.

## Conversation Memory (built — `agents/memory.py`)
- NOT using Agentspan's default in-memory `ConversationMemory` — custom SQLite store instead (single source of truth for chat history). `session_id` is currently a fixed constant per entrypoint (`"default_session"` in `router_agent.py`'s REPL, `"streamlit_session"` in `app.py`) — single-user only for now; would need to become dynamic (per-browser-session or per-login) for multi-user.
- Schema: `history(session_id, role, content, ts)` + `session_summary(session_id PRIMARY KEY, summary_text, summarized_checkpoint, updated_at)`.
- `save_message(session_id, role, content)` — appends one row to `history`.
- `get_context(session_id, window_size=10)` — the retrieval/summarization logic, batch-based (not per-message):
  - `checkpoint` = how many messages (from the start) are already folded into `summary_text`, stored in `session_summary`.
  - Trigger a new summarization pass only when `total_count - checkpoint >= window_size`. Batch = the next `window_size` messages starting at `checkpoint`; folded into existing summary via a **separate, cheap model call** (`summarize_batch`, direct Anthropic SDK call to `claude-haiku-4-5-20251001` — deliberately NOT routed through Agentspan/`Agent`, since summarization is a plain completion, not an agentic task; avoids dragging in tool-worker/multiprocessing overhead for a one-shot text call). `checkpoint += window_size` after.
  - This means raw (non-summarized) messages sent to the LLM can temporarily grow up to `window_size - 1` before the next batch trigger fires — a deliberate tradeoff (fewer, cheaper summarization calls) vs. a smaller-but-more-frequent-summarized alternative. Rejected the "summarize every single message past the threshold" variant — too many small LLM calls.
  - Raw-message selection has 3 cases (see code for the exact reasoning trail — this took several iterations to get right): `checkpoint == 0` → return everything (no summary yet); `total_count % window_size == 0` → we're exactly at a trigger point where the just-summarized batch would otherwise leave a raw gap of zero messages, so special-case a fallback of just the single most-recent message + the summary (better than nothing, though still loses verbatim access to the rest of that batch — a known, accepted limitation); else → everything since `checkpoint`.
  - Full raw history stays in DB forever (audit); only what's sent to the LLM gets trimmed via the summary+window logic above.
- Wired into `router_agent.py`'s REPL and `app.py`: `context = get_context(session_id)` before each call, prepended to the user's new message as `full_prompt`; `save_message` for both the user's message and the assistant's final answer after.
- Agentspan's own execution trace (tool calls, timing, LLM calls) is a SEPARATE store (`~/.agentspan/server/agent-runtime.db`), managed by the Agentspan server itself — not the same as this conversation DB. Don't conflate the two.

## Components checklist
- [x] Tools — `@tool` decorator; went straight to real APIs (NewsAPI, Alpaca) rather than dummy-data stubs first, since the actual providers were simple enough to wire directly.
- [x] Database — our own SQLite for conversation history, built (`agents/memory.py`) and wired into both the REPL and the UI.
- [x] Loop/execution — Agentspan `run()` / `runtime.run()` / `runtime.stream()` — crash-safe by default. Conversation continuity now comes from our own memory layer (context prepended per call), not from Agentspan itself.
- [x] Trace — Agentspan built-in: `agentspan agent execution` (list), `agentspan agent status <execution_id>` (full input/output detail — `--name`/`--since` filters on `execution` are flaky, plain `agentspan agent execution` with no filter is reliable). Used heavily this session to diagnose the `output_type`/handoff bug below — this is the tool that made the root cause visible.
- [x] Audit — same execution history, queryable.
- [x] UI — Streamlit chat app (`app.py`), streams live progress (routing/tool-call events) instead of a blocking spinner.
- [ ] Guardrails — not started.
- [ ] Human-in-the-loop — not started.

## Build order (progress as of this session)
1. [x] Skeleton: install, start server, one dummy agent via `mock_run`.
2. [x] Specialist agents — ended up with **2**, not 3: `news_agent` (financial+political merged into one agent, one tool, LLM classifies via query construction rather than us splitting tools) and `chart_agent` (stocks+crypto, 3 horizons, 3 computed indicators). Went straight to real APIs, skipped the dummy-stub stage.
3. [x] Router wired with `strategy="handoff"` (it's a string param, not a `Strategy.HANDOFF` enum as originally assumed) and `agents=[news_agent, chart_agent]`. `output_type` removed from both sub-agents (see known issue below — required, not optional, under a router). Router instructions explicitly tell it to answer directly from conversation context when possible rather than always delegating — reduces but does NOT eliminate unnecessary sub-agent calls, since `handoff` routing is LLM-driven/probabilistic, not a hard rule.
4. [x] SQLite table + save/fetch functions for conversation history — done, see Conversation Memory section.
5. [x] Wire custom memory backend into agents (sliding window + summarization) — done, wired into router REPL + Streamlit UI.
6. [x] Real APIs wired (see Stack) — done earlier than planned, alongside step 2.
7. [ ] Guardrails + HITL — not started.
8. [ ] (new, not in original plan) `backtest_agent` — simple long/short rule backtest on historical price data + save results for reference. Explicitly scoped down from an earlier "continuously self-improving" idea, which was rejected — real risk of overfitting without proper train/test validation, and too large a scope departure from the multi-agent-patterns learning goal.
9. [x] (new, not in original plan) Streamlit UI (`app.py`) — chat interface + live streaming of progress events, wraps the router+memory. Built by Claude directly (explicit exception to Kushagra building everything himself — he said he didn't want to learn frontend/Streamlit specifically).

## Known constraints / honest notes
- Agentspan is a new tool (2026) — not battle-tested like LangSmith/Langfuse. Fine for learning; would need security review before any production/regulated use.
- This is explicitly NOT the BankerIQ pattern (which uses a deterministic process-map DAG for compliance/audit reasons). Agentspan's LLM-driven HANDOFF routing is intentionally more flexible/non-deterministic — good for this use case, wrong for regulated banking flows. Understand the difference; don't blur the two projects.
- At scale (1000+ users): SQLite → Postgres, summarization should move to async/background, Agentspan server needs proper multi-replica deployment. Not needed for this project's current scope.

### Real bugs/gotchas hit this session (all workarounds already applied in code unless noted)
- **Multiprocessing pickling crash on `run()`**: `agentspan`/Conductor's default `spawn` start method fails to pickle `@tool` functions (`Can't pickle <function ...>: it's not found as agentspan.agents.runtime._dispatch.<name>`). Fix: set `CONDUCTOR_MP_START_METHOD=fork` in `.env` (known upstream issue, conductor-python#264).
- **`output_type` (Pydantic structured output) doesn't produce a typed object**: `result.output` is always a raw dict (`{"result": ..., "finishReason": ..., "context": ...}`), and `result.output["result"]` is sometimes a plain dict, sometimes a markdown-fenced JSON *string* — never a validated Pydantic instance, contradicting the docs. Workaround: `agents/utils.py` has `parse_structured_output(raw_result, model_class)` — strips markdown fences if present, then `model_class.model_validate_json(...)` / `model_validate(...)`. Always route agent output through this before touching structured fields (REPL loops, and later the router/orchestrator, all need this).
- **`output_type` breaks router `handoff` context tracking**: when a sub-agent has `output_type` set, the router's own conversation log of that sub-agent's prior response shows up as `{}` (empty) — so the router thinks the sub-agent returned nothing and re-invokes it repeatedly (observed 3x re-calls, each one individually succeeding but wasted, before the router gave up and told the user "technical difficulties" despite good data existing in every one of those 3 sub-calls). Confirmed via `agentspan agent status <execution_id>` showing accumulating `[chart_agent]: {}` in each retry's input prompt. **Fix applied**: removed `output_type` from `chart_agent` before it's used as a router sub-agent (single call now, correct result). Still need to decide: keep `output_type` for standalone testing only (two code paths), or drop it everywhere and accept free-text output at the specialist level too (router/orchestrator was always going to produce free text as the final answer anyway).
- **No conversation memory across `runtime.run()`/`runtime.stream()` calls by default**: each call is a fresh, isolated execution — confirmed by testing a follow-up question ("why has it fallen") after an initial Bitcoin query; the router had zero idea what "it" referred to. **RESOLVED**: this is exactly why build order steps 4-5 (SQLite memory, `agents/memory.py`) were built — see Conversation Memory section above. (Agentspan does also have a lighter-weight *same-process* option, `runtime.start(agent, prompt)` → `AgentHandle` → `handle.send(followup)`, for context within one running session only — not used; our own SQLite layer was built instead since it needed to survive restarts anyway.)
- **`pandas-ta` is unmaintained and broken**: `ImportError: cannot import name 'NaN' from 'numpy'` on numpy 2.0+ (`np.NaN` was removed). Use `pandas-ta-classic` (actively maintained fork, same API, e.g. `df.ta.rsi(...)`) instead.
- **Alpaca `/v2/stocks/bars` needs an explicit `start` param**: omitting it returns only the single most recent bar regardless of `limit`.
- **RSI needs chronological (oldest-first) order and enough data points**: Alpaca bars come back `sort=desc` (newest-first) for our use case (recency-first for display), but indicator calculation requires reversing to chronological order first. RSI(14) needs 15+ data points minimum — our "long" horizon fetches 15 months (not the originally-planned 12) specifically so RSI is computable on all 3 horizons.
- **Git repo corruption mid-session**: multiple `.git/objects/*` went 0-byte/corrupt (cause unclear — not disk space, which was fine). Recovered cleanly by re-cloning from `origin` (which already had the latest pushed commit) and swapping in the fresh `.git` folder — no work was lost since corruption was git-internal only, working-tree files were untouched. Lesson: origin is the real backup; local `.git` corruption is recoverable as long as you've pushed.
- **`output_type` + router `handoff` has TWO distinct failure modes, not one**: confirmed via `agentspan agent status` on real execution IDs. (a) Sub-agent's response shows as `{}` in the router's own internal conversation log → router thinks it got nothing, re-invokes the same sub-agent repeatedly (wasted real API calls each time, all individually succeeding but unused). (b) Sub-agent's response arrives *after* the router has already written `DONE` and moved on — confirmed by inspecting the raw `conversation` field of a `router_router_wf`-level execution trace, where a fully valid `[news_agent]: ...` JSON response appeared textually *after* the `DONE` marker in the log. Net effect is the same either way (wasted call, result unused), but the mechanism differs — this looks like a race/timing issue in how `handoff` tracks sub-agent completion relative to the coordinator's own decision to finish, not purely a serialization bug. Root-caused, not fully fixed — removing `output_type` from sub-agents avoids it, no other workaround found.
- **Even with `output_type` removed + explicit "answer from context, don't delegate unnecessarily" instructions, the router can still make unneeded sub-agent calls sometimes**: `handoff` is LLM-driven routing, not a deterministic rule — instructions reduce but don't guarantee correct behavior. Confirmed by testing the same "what was my last question" recall-only query multiple times; sometimes zero unnecessary calls, sometimes still one. Accepted as an inherent tradeoff of this architecture (already noted elsewhere in this doc: HANDOFF is "intentionally more flexible/non-deterministic"). A fully deterministic fix would require a pre-filter/classifier before the router LLM even runs — not implemented, judged not worth the added complexity for a learning project.
- **Streaming (`runtime.stream()`) events are NOT token-level deltas**: event types are coarse-grained — `thinking`, `tool_call`, `tool_result`, `handoff`, `waiting`, `guardrail_pass`/`fail`, `message`, `done` (each an `AgentEvent` with `.type`, `.content`, `.tool_name`, `.args`, `.result`, `.target`, `.output`, `.workflow_id`, `.guardrail_name`). No raw LLM token/delta events documented. Used in `app.py` to show live progress ("Routing to X...", "Calling Y...") via a generator fed to Streamlit's `st.write_stream()` — genuinely improves perceived latency even without true token streaming, since the multi-second waits are no longer silent.
- **Bug we introduced ourselves: saving the full streamed text (including our own UI progress markers) into conversation memory.** `st.write_stream()` returns the full concatenated text of everything yielded — if you naively `save_message(..., that_return_value)`, the persisted "assistant" message contains literal `*Routing to news_agent...*` / `*Calling \`search_news\`...*` text baked in as if it were real conversation content. This then gets fed back into future prompts as "history," polluting context with UI-only noise (confirmed via `agentspan agent status` showing this exact text inside a later execution's input prompt). Fix: track the final `done` event's output separately (e.g. via a mutable list closed over by the generator, since plain `nonlocal` doesn't work at Streamlit's module-level script scope) and save *only* that clean text to memory — `st.write_stream()`'s return value is fine for display but must not be what gets persisted.

## Best practices to follow while building
- **Tools**: small, single-purpose, clear docstrings (docstring = schema the LLM sees). Return structured data, not free text, where possible.
- **Instructions**: narrow and specific per agent. Don't make one agent do everything — that's why we have a router.
- **Errors**: every tool should fail loudly with a clear message, not silently return None/empty. Let guardrails/retry logic handle it.
- **Secrets**: API keys via env vars, never hardcoded. `.env` in `.gitignore`.
- **Test before wiring to real APIs**: use `mock_run` to validate agent logic first, so bugs are isolated from flaky external APIs.
- **Idempotency**: tools that call external APIs (esp. anything that writes/spends) should be safe to retry — Agentspan retries automatically.
- **Observability from day 1**: don't bolt on tracing later — use Agentspan's built-in trace from the first working agent so you can see routing decisions as you build.
- **Cost awareness**: log token usage per run early; router + specialist = min 2 LLM calls per query, add up fast.
- **Version control**: commit working checkpoints often — easier to debug when something breaks mid-build.
- **Eval set (separate offline flow, not part of runtime)**: fixed set of test queries + expected outcomes per agent. Run in batch (CI or periodic), not on every live request — catches regressions when prompts/tools change. Can reuse `mock_run`/`expect()` pattern for this.
- **Rate limiting / timeout handling**: external APIs (news, price data) can be slow or down — every tool needs a timeout + fallback, not an unbounded wait.
- **Prompt injection awareness**: any tool that fetches external content (news article, webpage) — that content can contain text trying to hijack the agent's instructions. Treat fetched content strictly as data, never as instructions.
- **Fallback response**: if router can't classify a query, or a specialist fails, agent should return a graceful "couldn't handle this" — not crash.

## User context (for continuity)
- Kushagra — data engineer at a bank (Amsterdam, EU), building AI engineer skills outside of work.
- Kushagra is on a journey to become the best AI engineer he can be. This project is a real step on that path — Claude is his helper throughout, not just a code generator.
- Prefers short, direct, simple communication. Hinglish. Tables only when useful, not by default.
- Learns by building real things, not tutorials.
