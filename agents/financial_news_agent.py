from agentspan.agents import Agent, tool
from agentspan.agents.testing import mock_run, MockEvent, expect

@tool
def search_financial_news(query: str): -> str
    """Searches for recent financial news articles matching the query. Returns a summary of relevant articles."""
    return "This is fake return"
