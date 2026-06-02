"""
Smart Money Concepts (SMC) Detector
Detects Fair Value Gaps (FVG) and Liquidity Sweeps in OHLC data.
"""
import pandas as pd
import numpy as np
from typing import Tuple


# ── Fair Value Gaps ──────────────────────────────────────────────────────────

def detect_fvg(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect Fair Value Gaps using a 3-candle structure.

    Bullish FVG:  candle[i+1].low  > candle[i-1].high  (gap above)
    Bearish FVG:  candle[i+1].high < candle[i-1].low   (gap below)

    Returns a DataFrame with columns:
        index, type, top, bottom, mid, start_idx
    """
    records = []

    highs  = df["high"].values
    lows   = df["low"].values
    times  = df.index

    for i in range(1, len(df) - 1):
        c1_high = highs[i - 1]
        c1_low  = lows[i - 1]
        c3_high = highs[i + 1]
        c3_low  = lows[i + 1]

        # Bullish FVG: gap between candle 1 high and candle 3 low
        if c3_low > c1_high:
            records.append({
                "index":     times[i],
                "type":      "bullish",
                "top":       c3_low,
                "bottom":    c1_high,
                "mid":       (c3_low + c1_high) / 2,
                "start_idx": i,
            })

        # Bearish FVG: gap between candle 3 high and candle 1 low
        elif c3_high < c1_low:
            records.append({
                "index":     times[i],
                "type":      "bearish",
                "top":       c1_low,
                "bottom":    c3_high,
                "mid":       (c1_low + c3_high) / 2,
                "start_idx": i,
            })

    if records:
        return pd.DataFrame(records)
    return pd.DataFrame(
        columns=["index", "type", "top", "bottom", "mid", "start_idx"]
    )


# ── Liquidity Sweeps ─────────────────────────────────────────────────────────

def detect_liquidity_sweeps(
    df: pd.DataFrame,
    lookback: int = 20,
) -> pd.DataFrame:
    """
    Detect liquidity sweeps:
    - Price wicks beyond a prior swing high/low …
    - … but candle CLOSES back inside the prior range.

    Buy-Side Sweep  : high > prior_high  AND  close < prior_high
    Sell-Side Sweep : low  < prior_low   AND  close > prior_low

    Returns a DataFrame with columns:
        index, type, wick_price, close_price, swept_level
    """
    records = []

    highs  = df["high"].values
    lows   = df["low"].values
    closes = df["close"].values
    times  = df.index

    for i in range(lookback, len(df)):
        window_h = highs[i - lookback : i]
        window_l = lows[i - lookback : i]
        prior_high = window_h.max()
        prior_low  = window_l.min()

        # Buy-side sweep (above prior high, close back inside)
        if highs[i] > prior_high and closes[i] < prior_high:
            records.append({
                "index":        times[i],
                "type":         "buy_side",
                "wick_price":   highs[i],
                "close_price":  closes[i],
                "swept_level":  prior_high,
            })

        # Sell-side sweep (below prior low, close back inside)
        elif lows[i] < prior_low and closes[i] > prior_low:
            records.append({
                "index":        times[i],
                "type":         "sell_side",
                "wick_price":   lows[i],
                "close_price":  closes[i],
                "swept_level":  prior_low,
            })

    if records:
        return pd.DataFrame(records)
    return pd.DataFrame(
        columns=["index", "type", "wick_price", "close_price", "swept_level"]
    )


# ── Convenience wrapper ──────────────────────────────────────────────────────

def get_smc_analysis(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return (fvg_df, sweeps_df) for a full dataset."""
    return detect_fvg(df), detect_liquidity_sweeps(df)


# ── Learning annotations ─────────────────────────────────────────────────────

FVG_EXPLANATION = {
    "bullish": (
        "**Bullish Fair Value Gap** — A price imbalance where buyers were so aggressive "
        "that no sellers participated. The gap (between candle 1 high and candle 3 low) "
        "often acts as **support** on a pullback. Smart money tends to re-enter here."
    ),
    "bearish": (
        "**Bearish Fair Value Gap** — A downside imbalance created by aggressive selling. "
        "The gap (between candle 3 high and candle 1 low) often acts as **resistance** "
        "on a retracement. Smart money may short from this zone."
    ),
}

SWEEP_EXPLANATION = {
    "buy_side": (
        "**Buy-Side Liquidity Sweep** — Price briefly spiked *above* a prior swing high "
        "(triggering stop-losses of short sellers), then closed back below. "
        "This traps late buyers and often precedes a **bearish reversal**."
    ),
    "sell_side": (
        "**Sell-Side Liquidity Sweep** — Price dipped *below* a prior swing low "
        "(triggering stop-losses of long holders), then closed back above. "
        "This traps late sellers and often precedes a **bullish reversal**."
    ),
}
