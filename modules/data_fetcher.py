"""
Data Fetcher Module
Handles all yfinance data retrieval and preprocessing.
"""
import yfinance as yf
import pandas as pd
from typing import Optional


PERIOD_MAP = {
    "1m":  ["1d", "5d", "7d"],
    "5m":  ["5d", "1mo"],
    "15m": ["5d", "1mo"],
    "30m": ["5d", "1mo"],
    "1h":  ["1mo", "3mo", "6mo", "1y", "2y"],
    "1d":  ["3mo", "6mo", "1y", "2y", "5y"],
    "1wk": ["1y", "2y", "5y", "10y"],
}

INTRADAY_LIMIT_DAYS = {
    "1m": 7,
    "5m": 60, "15m": 60, "30m": 60,
    "1h": 730,
}


def fetch_data(ticker: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV data from yfinance.
    Returns a clean DataFrame with lowercase column names.
    """
    try:
        stock = yf.Ticker(ticker.upper().strip())
        df = stock.history(period=period, interval=interval, auto_adjust=True)

        if df.empty:
            limit = INTRADAY_LIMIT_DAYS.get(interval)
            if limit is not None:
                raise ValueError(
                    f"No data returned for '{ticker}' at interval={interval}, period={period}. "
                    f"Yahoo Finance only serves {interval} bars for the last {limit} days — "
                    f"pick a shorter period or a larger interval."
                )
            raise ValueError(f"No data returned for '{ticker}'. Check the symbol.")

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]

        # Ensure DatetimeIndex and drop NaN rows
        df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_localize(None)  # strip timezone for plotly compatibility
        df.dropna(inplace=True)
        df.sort_index(inplace=True)

        # Remove zero-volume candles (market closures)
        df = df[df["volume"] > 0]

        return df

    except Exception as e:
        raise RuntimeError(f"Failed to fetch data for '{ticker}': {e}")


def get_available_periods(interval: str) -> list:
    """Return valid period options for a given interval."""
    return PERIOD_MAP.get(interval, ["3mo", "6mo", "1y"])


def get_ticker_info(ticker: str) -> dict:
    """Fetch basic ticker metadata."""
    try:
        info = yf.Ticker(ticker.upper().strip()).info
        return {
            "name": info.get("shortName", ticker),
            "sector": info.get("sector", "N/A"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", "N/A"),
            "market_cap": info.get("marketCap", 0),
        }
    except Exception:
        return {"name": ticker, "sector": "N/A", "currency": "USD", "exchange": "N/A", "market_cap": 0}
