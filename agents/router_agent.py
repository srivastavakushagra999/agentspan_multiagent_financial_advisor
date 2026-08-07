from agentspan.agents import Agent, AgentRuntime
from agents.news_agent import agent as news_agent
from agents.chart_agent import agent as chart_agent

router =  Agent(
    name="router",
    model="anthropic/claude-sonnet-4-6",
    instructions="""You are a router in a multi-agent financial advisory system. Based on the user's query, delegate to the appropriate specialist:
                    - news_agent: for questions about financial or political news, sentiment, or recent events affecting an asset or market.
                    - chart_agent: for questions about price trends, technical indicators, or how a stock/crypto has been performing.
                    If the query needs both (e.g. "should I invest in Bitcoin"), you may need to consider both perspectives.""",
    agents=[news_agent,chart_agent],
    strategy="handoff",
)

if __name__ == "__main__":
    with AgentRuntime() as runtime:
        while True:
            user_input = input("You: ")
            if user_input.lower() in ("exit", "quit"):
                break
            result = runtime.run(router, user_input)
            print("Router result:", result.output)