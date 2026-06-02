"""
Technical Indicators Module
Calculates RSI, MACD, Moving Averages using the `ta` library.
"""
import pandas as pd
import numpy as np

try:
    from ta.momentum import RSIIndicator
    from ta.trend import MACD, SMAIndicator, EMAIndicator
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False


# ── Manual fallbacks (used if `ta` is missing) ──────────────────────────────

def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def _ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ── Main calculation function ────────────────────────────────────────────────

def calculate_all_indicators(
    df: pd.DataFrame,
    sma_short: int = 20,
    sma_long: int = 50,
    ema_short: int = 20,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
) -> pd.DataFrame:
    """
    Compute all technical indicators and attach them to a copy of df.
    Handles both `ta` library and manual fallback implementations.
    """
    df = df.copy()
    close = df["close"]

    # Moving averages
    if TA_AVAILABLE:
        df[f"sma_{sma_short}"] = SMAIndicator(close, window=sma_short).sma_indicator()
        df[f"sma_{sma_long}"]  = SMAIndicator(close, window=sma_long).sma_indicator()
        df[f"ema_{ema_short}"] = EMAIndicator(close, window=ema_short).ema_indicator()
    else:
        df[f"sma_{sma_short}"] = _sma(close, sma_short)
        df[f"sma_{sma_long}"]  = _sma(close, sma_long)
        df[f"ema_{ema_short}"] = _ema(close, ema_short)

    # RSI
    if TA_AVAILABLE:
        df["rsi"] = RSIIndicator(close, window=rsi_period).rsi()
    else:
        df["rsi"] = _rsi(close, rsi_period)

    # MACD
    if TA_AVAILABLE:
        m = MACD(close, window_fast=macd_fast, window_slow=macd_slow, window_sign=macd_signal)
        df["macd"]        = m.macd()
        df["macd_signal"] = m.macd_signal()
        df["macd_diff"]   = m.macd_diff()
    else:
        df["macd"], df["macd_signal"], df["macd_diff"] = _macd(
            close, macd_fast, macd_slow, macd_signal
        )

    return df
