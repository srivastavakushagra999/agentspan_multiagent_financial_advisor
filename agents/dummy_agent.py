from agentspan.agents import Agent, tool
from agentspan.agents.testing import mock_run, MockEvent, expect

@tool
def dummy_tool(query: str) -> str:
    """Returns a fake response for testing."""
    return f"dummy result for: {query}"

agent = Agent(
    name="dummy_agent",
    model="anthropic/claude-sonnet-4-6",
    tools=[dummy_tool],
    instructions="You are a test agent that calls dummy_tool.",
)

result = mock_run(agent, "test query", events=[
    MockEvent.tool_call("dummy_tool", {"query": "test query"}),
    MockEvent.done("done"),
])
expect(result).completed().used_tool("dummy_tool")
print("Skeleton works!")
