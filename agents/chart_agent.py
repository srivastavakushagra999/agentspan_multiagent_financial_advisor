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

load_dotenv()

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


@tool
def get_stock_price(symbol: str, horizons: list[Literal["short", "medium", "long"]] = ["short"]):
    """Fetches historical stock price data (open, high, low, close, volume) for a given stock ticker symbol like AAPL or MSFT.
        horizon='short' returns daily candles (~30 days) — good for recent/short-term momentum.
        horizon='medium' returns weekly candles (~20 weeks) — good for medium-term trend.
        horizon='long' returns monthly candles (~12 months) — good for long-term investment perspective.
        For a complete picture (e.g. long-term investment questions), pass a list of multiple horizons (e.g. ["short", "long"]) in a single call to compare trends across timeframes.
        Each horizon's result includes calculated indicators: percentage change, simple moving average (SMA), and RSI (when enough data is available).
        """

    horizon_config = {
        "short": {"timeframe": "1Day", "limit": 20, "days_back": 20},
        "medium": {"timeframe": "1Week", "limit": 20, "days_back": 20 * 7},
        "long": {"timeframe": "1Month", "limit": 15, "days_back": 456},
        }

    results = {}
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


@tool
def get_crypto_price(symbol: str, horizons: list[Literal["short", "medium", "long"]] = ["short"]):
    """Fetches historical crypto price data (open, high, low, close, volume) for a given crypto trading pair like BTC/USD or ETH/USD.
        horizon='short' returns daily candles (~30 days) — good for recent/short-term momentum.
        horizon='medium' returns weekly candles (~20 weeks) — good for medium-term trend.
        horizon='long' returns monthly candles (~15 months) — good for long-term investment perspective.
        For a complete picture (e.g. long-term investment questions), pass a list of multiple horizons (e.g. ["short", "long"]) in a single call to compare trends across timeframes.
        Each horizon's result includes calculated indicators: percentage change, simple moving average (SMA), and RSI (when enough data is available).
        """


    horizon_config = {
        "short": {"timeframe": "1Day", "limit": 20, "days_back": 20},
        "medium": {"timeframe": "1Week", "limit": 20, "days_back": 20 * 7},
        "long": {"timeframe": "1Month", "limit": 15, "days_back": 456},
        }

    results = {}
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

