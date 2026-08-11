from agentspan.agents import Agent, tool, AgentRuntime, agent_tool
from agentspan.agents.testing import mock_run, MockEvent, expect
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Literal
import json
from agents.utils import parse_structured_output
load_dotenv()
#Schema 
class Article(BaseModel):
    title: str
    source: str
    url: str

class NewsReport(BaseModel):
    summary: str
    sentiment: Literal["bullish", "bearish", "neutral", "mixed"]
    key_articles: list[Article]

@tool
def search_news(query: str) -> list[dict]: 
    """Searches for recent financial and political news related to the query, including news that could impact the asset or topic being discussed."""
    response = requests.get(
        "https://newsapi.org/v2/everything",
        params={
        "q": query,
        "sortBy": "publishedAt",
        "pageSize": 10,
        "language": "en",
        "apiKey": os.getenv("NEWS_API_KEY"),
    },
    )
    data = response.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error [{data['code']}]: {data['message']}")
    articles = []
    for article in data["articles"]:
        articles.append({
            "title": article["title"],
            "source": article["source"]["name"],
            "published_at": article["publishedAt"],
            "summary": article["description"],
        })
    return articles


agent = Agent(
    name="news_agent",
    model="anthropic/claude-sonnet-4-6",
    tools=[search_news],
    instructions="""You are a news research assistant. You search for and summarize recent financial and political news.
    Always use the search_news tool when the user asks about a specific company, asset, market, or event — you don't have real-time knowledge of current events on your own.
    When responding, summarize the key facts from the articles you find and mention which sources reported what. Do NOT give direct investment advice (like "you should buy" or "you should sell"). Present the information neutrally and let the user draw their own conclusions.
    For the sentiment field, you MUST use exactly one of these four words and nothing else: bullish, bearish, neutral, or mixed. Do not write a descriptive phrase or sentence — pick only one of these exact words based on the overall tone of the news.
    """
    )

if __name__ == "__main__":
    with AgentRuntime() as runtime:
        while True:
            user_input = input("You: ")
            if user_input.lower() in ("exit", "quit"):
                break
            result = runtime.run(agent, user_input)
            report = result.output["result"]
            print("Agent:", report.summary)
            print("Sentiment:", report.sentiment)

