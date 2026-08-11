from agentspan.agents import Agent, tool, AgentRuntime
from agentspan.agents.testing import mock_run, MockEvent, expect
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Literal
import json
import re 
from datetime import datetime,timedelta
import pandas as pd
import pandas_ta_classic as ta
from agents.utils import parse_structured_output

load_dotenv()



class HorizonTrend(BaseModel):
    horizon: Literal["short", "medium", "long"]
    trend: Literal["bullish", "bearish", "neutral", "mixed"]
    pct_change: float
    sma: float
    rsi: float | None

class ChartReport(BaseModel):
    symbol: str
    current_price: float
    summary: str
    trends: list[HorizonTrend]



def calculate_metrics(bars_list):
    df = pd.DataFrame(bars_list).iloc[::-1].reset_index(drop=True)

    pct_change = (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0] * 100
    sma = df["close"].mean()

    if len(df) >= 15:
        df.ta.rsi(close="close", length=14, append=True)
        rsi = df["RSI_14"].iloc[-1]
    else:
        rsi = None

    return {
        "bars": bars_list,
        "pct_change": round(pct_change, 2),
        "sma": round(sma, 2),
        "rsi": round(rsi, 2) if rsi is not None else None,
    }


@tool(timeout_seconds=15, retry_count=2, max_calls=3)
def get_stock_price(symbol: str, horizons: list[Literal["short", "medium", "long"]] = ["short"]):
    """Fetches historical stock price data (open, high, low, close, volume) for a given stock ticker symbol like AAPL or MSFT.
        horizon='short' returns daily candles (~30 days) — good for recent/short-term momentum.
        horizon='medium' returns weekly candles (~20 weeks) — good for medium-term trend.
        horizon='long' returns monthly candles (~15 months) — good for long-term investment perspective.
        For a complete picture (e.g. long-term investment questions), pass a list of multiple horizons (e.g. ["short", "long"]) in a single call to compare trends across timeframes.
        Each horizon's result includes calculated indicators: percentage change, simple moving average (SMA), and RSI (when enough data is available).
        """

    trade_response = requests.get(
        "https://data.alpaca.markets/v2/stocks/trades/latest",
        headers={
            "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
            "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
        },
        params={"symbols": symbol},
        timeout=10,
    )
    trade_data = trade_response.json()
    current_price = trade_data.get("trades", {}).get(symbol, {}).get("p")

    horizon_config = {
        "short": {"timeframe": "1Day", "limit": 20, "days_back": 20},
        "medium": {"timeframe": "1Week", "limit": 20, "days_back": 20 * 7},
        "long": {"timeframe": "1Month", "limit": 15, "days_back": 456},
        }

    results = {"current_price": current_price}
    for horizon in horizons:
        config= horizon_config[horizon]
        start_date = (datetime.now() - timedelta(days=config["days_back"])).strftime("%Y-%m-%d")
        response = requests.get(
        "https://data.alpaca.markets/v2/stocks/bars",
        headers={
            "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
            "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
        },
        params={
            "symbols": symbol,
            "timeframe": config["timeframe"],
            "limit": config["limit"],
            "sort": "desc",
            "start": start_date,
        },
        timeout=10,
        )
        data = response.json()
        if response.status_code != 200:
            raise RuntimeError(f"Alpaca API error [{response.status_code}]: {data.get('message', response.text)}")
        bars = data.get("bars", {}).get(symbol, [])

        bars_list = [
            {"date": b["t"], "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"], "volume": b["v"]}
            for b in bars
        ]
        if not bars_list:
            results[horizon] = {"error": f"No price data found for symbol '{symbol}' in this horizon"}
            continue
        results[horizon] = calculate_metrics(bars_list)
    return results


@tool(timeout_seconds=15, retry_count=2, max_calls=3)
def get_crypto_price(symbol: str, horizons: list[Literal["short", "medium", "long"]] = ["short"]):
    """Fetches historical crypto price data (open, high, low, close, volume) for a given crypto trading pair like BTC/USD or ETH/USD.
        horizon='short' returns daily candles (~30 days) — good for recent/short-term momentum.
        horizon='medium' returns weekly candles (~20 weeks) — good for medium-term trend.
        horizon='long' returns monthly candles (~15 months) — good for long-term investment perspective.
        For a complete picture (e.g. long-term investment questions), pass a list of multiple horizons (e.g. ["short", "long"]) in a single call to compare trends across timeframes.
        Each horizon's result includes calculated indicators: percentage change, simple moving average (SMA), and RSI (when enough data is available).
        """

    trade_response = requests.get(
        "https://data.alpaca.markets/v1beta3/crypto/us/latest/trades",
        headers={
            "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
            "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
        },
        params={"symbols": symbol},
        timeout=10,
    )
    trade_data = trade_response.json()
    current_price = trade_data.get("trades", {}).get(symbol, {}).get("p")

    horizon_config = {
        "short": {"timeframe": "1Day", "limit": 20, "days_back": 20},
        "medium": {"timeframe": "1Week", "limit": 20, "days_back": 20 * 7},
        "long": {"timeframe": "1Month", "limit": 15, "days_back": 456},
        }

    results = {"current_price": current_price}
    for horizon in horizons:
        config= horizon_config[horizon]
        start_date = (datetime.now() - timedelta(days=config["days_back"])).strftime("%Y-%m-%d")
        response = requests.get(
        "https://data.alpaca.markets/v1beta3/crypto/us/bars",
        headers={
            "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
            "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
        },
        params={
            "symbols": symbol,
            "timeframe": config["timeframe"],
            "limit": config["limit"],
            "sort": "desc",
            "start": start_date,
        },
        timeout=10,
        )
        data = response.json()
        if response.status_code != 200:
            raise RuntimeError(f"Alpaca API error [{response.status_code}]: {data.get('message', response.text)}")
        bars = data.get("bars", {}).get(symbol, [])

        bars_list = [
            {"date": b["t"], "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"], "volume": b["v"]}
            for b in bars
        ]
        if not bars_list:
            results[horizon] = {"error": f"No price data found for symbol '{symbol}' in this horizon"}
            continue
        results[horizon] = calculate_metrics(bars_list)
    return results

agent = Agent(
    name="chart_agent",
    model="anthropic/claude-sonnet-4-6",
    tools=[get_stock_price, get_crypto_price],
    instructions="""You are the chart agent, part of a multi-agent financial advisory system that also includes a news agent. Your job is to fetch and analyze price/technical chart data for stocks and crypto.
                    You have two tools: get_stock_price and get_crypto_price. Each accepts a symbol and a list of horizons (short, medium, long), and returns a current_price plus, for each horizon, historical bars and calculated indicators (percentage change, SMA, RSI).
                    For each horizon requested, classify the trend as bullish, bearish, neutral, or mixed based on the indicators — e.g. price above SMA with positive percentage change suggests bullish; RSI above 70 suggests overbought, below 30 suggests oversold.
                    Do NOT give direct buy/sell/hold recommendations — that is the job of a separate orchestrator agent that combines your analysis with news sentiment. Simply report the current price, the trend, and key indicator values for each timeframe requested, neutrally.
                    If get_stock_price or get_crypto_price returns no data (empty current_price, or "No price data found" for a horizon) for a symbol, do NOT retry the same asset with different spellings or formats (e.g. "SUIUSD" vs "SUI/USD" vs "SUI"). One attempt is enough to know the data isn't available. Immediately report to the user that price data for this asset isn't available from your data provider, and stop — do not keep calling the tool.""",
    )



if __name__ == "__main__":
    with AgentRuntime() as runtime:
        while True:
            user_input = input("You: ")
            if user_input.lower() in ("exit", "quit"):
                break
            result = runtime.run(agent, user_input)
            try:
                report = parse_structured_output(result.output["result"], ChartReport)
                print("Agent:", report.summary)
                print("Current price:", report.current_price)
                for trend in report.trends:
                    print(f"  [{trend.horizon}] trend={trend.trend} pct_change={trend.pct_change}% sma={trend.sma} rsi={trend.rsi}")
            except Exception:
                print("Agent:", result.output.get("result", result.output))
