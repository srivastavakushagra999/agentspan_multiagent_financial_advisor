# Agentspan Multi-Agent Financial Advisor

Multi-agent financial advisor built on [Agentspan](https://agentspan.ai/).

## Prerequisites

- Python 3.14+
- Java 21+ (required by the Agentspan server)
  ```bash
  sudo apt install -y openjdk-21-jdk
  ```

## Setup

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   NEWS_API_KEY=...
   CONDUCTOR_MP_START_METHOD=fork
   ```
   - `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
   - `NEWS_API_KEY` — from [newsapi.org](https://newsapi.org)
   - `CONDUCTOR_MP_START_METHOD=fork` — required workaround for a multiprocessing pickling bug in Agentspan's worker startup ([conductor-python#264](https://github.com/conductor-sdk/conductor-python/issues/264))

## Running

1. Start the Agentspan server (first run downloads ~175MB, then serves the dashboard at `http://localhost:6767`):
   ```bash
   agentspan server start
   ```

2. In a separate terminal, run an agent (from the project root, not from inside `agents/`, so `.env` loads correctly):
   ```bash
   python -m agents.news_agent
   ```
   This starts an interactive chat loop. Type `exit` or `quit` to stop.

## Agents

- `agents/news_agent.py` — searches and summarizes recent financial and political news via the NewsAPI `/v2/everything` endpoint. Returns a structured `NewsReport` (summary, sentiment, key articles).
