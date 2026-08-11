from agents.memory import save_message, get_context
from agentspan.agents import Agent, AgentRuntime, agent_tool
from agents.news_agent import agent as news_agent
from agents.chart_agent import agent as chart_agent

router =  Agent(
    name="router",
    model="anthropic/claude-sonnet-4-6",
    instructions = """You are a router in a multi-agent financial advisory system. You have two tools:
- news_agent: for questions about financial or political news, sentiment, or recent events affecting an asset or market.
- chart_agent: for questions about price trends, technical indicators, or how a stock/crypto has been performing.
BEFORE calling any tool, first reason explicitly: is the answer to the user's question already present in the conversation history/context above (e.g. they're asking you to recall, repeat, clarify, or rephrase something already discussed)? State this to yourself first.
- If YES, answer directly from the context. Do NOT call any tool.
- If NO, only then decide which tool(s) to call.
Example: if the user asks "what was the price you mentioned" and a price is already visible above in the conversation, do NOT call chart_agent — just repeat that value.
When you DO call a tool, write a short, self-contained "request" describing only what that specialist needs to do — not the full conversation history. E.g. "Get the latest news and sentiment on Bitcoin", not a copy of the whole conversation so far.
If the query genuinely needs both perspectives (e.g. "should I invest in Bitcoin"), you may call both tools.
Do not narrate your own reasoning process in the final answer — just present the findings directly.""",

    tools=[agent_tool(news_agent), agent_tool(chart_agent)]
)

SESSION_ID = "default_session"

if __name__ == "__main__":
    with AgentRuntime() as runtime:
        while True:
            user_input = input("You: ")
            if user_input.lower() in ("exit", "quit"):
                break

            context = get_context(SESSION_ID)
            full_prompt = f"{context}\n\nuser: {user_input}" if context else user_input

            result = runtime.run(router, full_prompt)
            response_text = result.output.get("result", result.output)

            print("Router result:", response_text)

            save_message(SESSION_ID, "user", user_input)
            save_message(SESSION_ID, "assistant", str(response_text))
