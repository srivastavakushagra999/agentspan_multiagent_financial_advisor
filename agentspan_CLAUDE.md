# Project: Multi-Agent Expert System (Agentspan)

## Goal
Side/portfolio project to learn multi-agent frameworks + MCP-style patterns, closing skill gaps identified for AI engineer roles (esp. Capgemini "Agentic AI Engineer" JD — CrewAI/AutoGen/Semantic Kernel, MCP agent-to-agent comms, RAG depth).

Not for production banking use — this is a personal/learning project (separate from BankerIQ). No bank-related data or context belongs here.

## Stack
- **Agent runtime**: Agentspan (https://agentspan.ai/) — `pip install agentspan` (currently `0.2.0`, latest) — durable execution, built on Conductor (open-source, MIT licensed, self-hosted)
- **Server**: `agentspan server start` — runs locally on `localhost:6767`. Its own execution-trace DB lives at `~/.agentspan/server/agent-runtime.db` (SQLite by default; `SPRING_PROFILES_ACTIVE=postgres` + `SPRING_DATASOURCE_*` env vars to point it at a custom Postgres instead — this is a fully standard DB we own, no lock-in, could sync/export to Langfuse etc. later if wanted).
- **LLM**: Anthropic Claude (`anthropic/claude-sonnet-4-6`)
- **DB (our own conversation memory, separate from Agentspan's trace DB above)**: SQLite (Postgres later if scaling) — not built yet, see Build order.
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

## Conversation Memory
- NOT using Agentspan's default in-memory `ConversationMemory` — wiring a custom SQLite-backed store instead (single source of truth for chat history).
- Schema: `history(session_id, role, content, ts)`
- Context sent to LLM per turn = last 10 raw messages + running summary (if exists)
- When message count > 10: summarize older messages (use a cheap model, e.g. haiku/gpt-4o-mini), store summary, prune raw messages from what's sent to LLM. Full raw history stays in DB for audit; only the LLM-bound context gets trimmed.
- Agentspan's own execution trace (tool calls, timing, LLM calls) is a SEPARATE store, managed by the Agentspan server itself — not the same as this conversation DB. Don't conflate the two.

## Components checklist
- [x] Tools — `@tool` decorator; went straight to real APIs (NewsAPI, Alpaca) rather than dummy-data stubs first, since the actual providers were simple enough to wire directly.
- [ ] Database — our own SQLite for conversation history (custom, not Agentspan default) — NOT built yet.
- [x] Loop/execution — Agentspan `run()` / `runtime.run()` — crash-safe by default, but see memory caveat below (NOT conversation-continuous by default).
- [x] Trace — Agentspan built-in: `agentspan agent execution` (list), `agentspan agent status <execution_id>` (full input/output detail — `--name`/`--since` filters on `execution` are flaky, plain `agentspan agent execution` with no filter is reliable).
- [x] Audit — same execution history, queryable.
- [ ] Guardrails — not started.
- [ ] Human-in-the-loop — not started.

## Build order (progress as of this session)
1. [x] Skeleton: install, start server, one dummy agent via `mock_run`.
2. [x] Specialist agents — ended up with **2**, not 3: `news_agent` (financial+political merged into one agent, one tool, LLM classifies via query construction rather than us splitting tools) and `chart_agent` (stocks+crypto, 3 horizons, 3 computed indicators). Went straight to real APIs, skipped the dummy-stub stage.
3. [x] Router wired with `strategy="handoff"` (it's a string param, not a `Strategy.HANDOFF` enum as originally assumed) and `agents=[news_agent, chart_agent]`. Routing itself verified correct (single-specialist queries route to the right one; single combined query triggers chart_agent then can hand off). **BUT**: sub-agents must NOT have `output_type` set when used under a router — see known issue below. Currently `chart_agent`'s `output_type=ChartReport` is commented out/removed for this reason; needs a real decision (see below) before calling this step done.
4. [ ] SQLite table + save/fetch functions for conversation history — next up.
5. [ ] Wire custom memory backend into agents (sliding window + summarization).
6. [x] Real APIs wired (see Stack) — done earlier than planned, alongside step 2.
7. [ ] Guardrails + HITL — not started.
8. [ ] (new, not in original plan) `backtest_agent` — simple long/short rule backtest on historical price data + save results for reference. Explicitly scoped down from an earlier "continuously self-improving" idea, which was rejected — real risk of overfitting without proper train/test validation, and too large a scope departure from the multi-agent-patterns learning goal.

## Known constraints / honest notes
- Agentspan is a new tool (2026) — not battle-tested like LangSmith/Langfuse. Fine for learning; would need security review before any production/regulated use.
- This is explicitly NOT the BankerIQ pattern (which uses a deterministic process-map DAG for compliance/audit reasons). Agentspan's LLM-driven HANDOFF routing is intentionally more flexible/non-deterministic — good for this use case, wrong for regulated banking flows. Understand the difference; don't blur the two projects.
- At scale (1000+ users): SQLite → Postgres, summarization should move to async/background, Agentspan server needs proper multi-replica deployment. Not needed for this project's current scope.

### Real bugs/gotchas hit this session (all workarounds already applied in code unless noted)
- **Multiprocessing pickling crash on `run()`**: `agentspan`/Conductor's default `spawn` start method fails to pickle `@tool` functions (`Can't pickle <function ...>: it's not found as agentspan.agents.runtime._dispatch.<name>`). Fix: set `CONDUCTOR_MP_START_METHOD=fork` in `.env` (known upstream issue, conductor-python#264).
- **`output_type` (Pydantic structured output) doesn't produce a typed object**: `result.output` is always a raw dict (`{"result": ..., "finishReason": ..., "context": ...}`), and `result.output["result"]` is sometimes a plain dict, sometimes a markdown-fenced JSON *string* — never a validated Pydantic instance, contradicting the docs. Workaround: `agents/utils.py` has `parse_structured_output(raw_result, model_class)` — strips markdown fences if present, then `model_class.model_validate_json(...)` / `model_validate(...)`. Always route agent output through this before touching structured fields (REPL loops, and later the router/orchestrator, all need this).
- **`output_type` breaks router `handoff` context tracking**: when a sub-agent has `output_type` set, the router's own conversation log of that sub-agent's prior response shows up as `{}` (empty) — so the router thinks the sub-agent returned nothing and re-invokes it repeatedly (observed 3x re-calls, each one individually succeeding but wasted, before the router gave up and told the user "technical difficulties" despite good data existing in every one of those 3 sub-calls). Confirmed via `agentspan agent status <execution_id>` showing accumulating `[chart_agent]: {}` in each retry's input prompt. **Fix applied**: removed `output_type` from `chart_agent` before it's used as a router sub-agent (single call now, correct result). Still need to decide: keep `output_type` for standalone testing only (two code paths), or drop it everywhere and accept free-text output at the specialist level too (router/orchestrator was always going to produce free text as the final answer anyway).
- **No conversation memory across `runtime.run()` calls**: each call is a fresh, isolated execution — confirmed by testing a follow-up question ("why has it fallen") after an initial Bitcoin query; the router had zero idea what "it" referred to. This is expected — it's exactly why build order steps 4-5 (SQLite memory) exist — but note Agentspan also has a lighter-weight *same-process* option (`runtime.start(agent, prompt)` → `AgentHandle`, then `handle.send(followup)` keeps context within one running session) that could patch the REPL loop specifically without needing the full SQLite layer yet. Full custom SQLite memory is still the plan for cross-session persistence/audit.
- **`pandas-ta` is unmaintained and broken**: `ImportError: cannot import name 'NaN' from 'numpy'` on numpy 2.0+ (`np.NaN` was removed). Use `pandas-ta-classic` (actively maintained fork, same API, e.g. `df.ta.rsi(...)`) instead.
- **Alpaca `/v2/stocks/bars` needs an explicit `start` param**: omitting it returns only the single most recent bar regardless of `limit`.
- **RSI needs chronological (oldest-first) order and enough data points**: Alpaca bars come back `sort=desc` (newest-first) for our use case (recency-first for display), but indicator calculation requires reversing to chronological order first. RSI(14) needs 15+ data points minimum — our "long" horizon fetches 15 months (not the originally-planned 12) specifically so RSI is computable on all 3 horizons.
- **Git repo corruption mid-session**: multiple `.git/objects/*` went 0-byte/corrupt (cause unclear — not disk space, which was fine). Recovered cleanly by re-cloning from `origin` (which already had the latest pushed commit) and swapping in the fresh `.git` folder — no work was lost since corruption was git-internal only, working-tree files were untouched. Lesson: origin is the real backup; local `.git` corruption is recoverable as long as you've pushed.

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
