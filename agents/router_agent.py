from agents.memory import save_message, get_context
from agentspan.agents import Agent, AgentRuntime
from agents.news_agent import agent as news_agent
from agents.chart_agent import agent as chart_agent

router =  Agent(
    name="router",
    model="anthropic/claude-sonnet-4-6",
    instructions="""You are a router in a multi-agent financial advisory system. Based on the user's query, delegate to the appropriate specialist:
                    - news_agent: for questions about financial or political news, sentiment, or recent events affecting an asset or market.
                    - chart_agent: for questions about price trends, technical indicators, or how a stock/crypto has been performing.
                    If the query needs both (e.g. "should I invest in Bitcoin"), you may need to consider both perspectives.
                    IMPORTANT: Before delegating to any specialist, first check if the answer is already present in the conversation history/context above (e.g. the user is asking you to recall, repeat, or clarify something already discussed). If the answer is already there, answer directly yourself and do NOT call any tool or sub-agent. Only delegate to news_agent or chart_agent when the user's question genuinely requires new external data (fresh news, or current price/chart data) that is not already in the conversation above.""",
    agents=[news_agent,chart_agent],
    strategy="handoff",
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
