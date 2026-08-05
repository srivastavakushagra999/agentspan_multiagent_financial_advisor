from agentspan.agents import Agent, tool, AgentRuntime
from agentspan.agents.testing import mock_run, MockEvent, expect
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Literal
import json
import re 

load_dotenv()
@tool
def get_stock_price(symbol: str):
    """Fetches recent historical daily stock prices (open, high, low, close, volume) for a given stock ticker symbol like AAPL or MSFT."""
    response = requests.get(
    "https://data.alpaca.markets/v2/stocks/bars",
    headers={
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
    },
    params={
        "symbols": symbol,
        "timeframe": "1Day",
        "limit": 30,
        "sort": "desc",  # recent pehle
    },
    )
    data = response.json()


