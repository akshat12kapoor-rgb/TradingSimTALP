"""
Strategy Module
Generates BUY / SELL / HOLD signals for each supported strategy.
"""
import pandas as pd


# ── Individual strategies ────────────────────────────────────────────────────

def rsi_strategy(
    df: pd.DataFrame,
    oversold: int = 30,
    overbought: int = 70,
) -> pd.Series:
    """
    RSI mean-reversion strategy.
    BUY  when RSI crosses below `oversold`.
    SELL when RSI crosses above `overbought`.
    """
    signals = pd.Series("HOLD", index=df.index, dtype=str)
    if "rsi" not in df.columns:
        return signals

    rsi = df["rsi"]
    # Crossover detection (edge-based, not level-based)
    crossed_oversold   = (rsi < oversold) & (rsi.shift(1) >= oversold)
    crossed_overbought = (rsi > overbought) & (rsi.shift(1) <= overbought)

    signals[crossed_oversold]   = "BUY"
    signals[crossed_overbought] = "SELL"
    return signals


def macd_strategy(df: pd.DataFrame) -> pd.Series:
    """
    MACD crossover strategy.
    BUY  when MACD line crosses above signal line.
    SELL when MACD line crosses below signal line.
    """
    signals = pd.Series("HOLD", index=df.index, dtype=str)
    if "macd" not in df.columns or "macd_signal" not in df.columns:
        return signals

    macd   = df["macd"]
    signal = df["macd_signal"]

    cross_up   = (macd > signal) & (macd.shift(1) <= signal.shift(1))
    cross_down = (macd < signal) & (macd.shift(1) >= signal.shift(1))

    signals[cross_up]   = "BUY"
    signals[cross_down] = "SELL"
    return signals


def fvg_strategy(
    df: pd.DataFrame,
    fvg_df: pd.DataFrame | None = None,
) -> pd.Series:
    """
    Fair Value Gap strategy.
    BUY  one candle after a bullish FVG completes (gap acts as support).
    SELL one candle after a bearish FVG completes (gap acts as resistance).
    """
    signals = pd.Series("HOLD", index=df.index, dtype=str)
    if fvg_df is None or fvg_df.empty:
        return signals

    last = len(df) - 1
    for _, row in fvg_df.iterrows():
        trigger = int(row["start_idx"]) + 1
        if trigger > last:
            continue
        signals.iloc[trigger] = "BUY" if row["type"] == "bullish" else "SELL"
    return signals


def sweep_strategy(
    df: pd.DataFrame,
    sweeps_df: pd.DataFrame | None = None,
) -> pd.Series:
    """
    Liquidity Sweep reversal strategy.
    BUY  on a sell-side sweep (stop-hunt below prior low → bullish reversal).
    SELL on a buy-side sweep  (stop-hunt above prior high → bearish reversal).
    """
    signals = pd.Series("HOLD", index=df.index, dtype=str)
    if sweeps_df is None or sweeps_df.empty:
        return signals

    pos = {ts: i for i, ts in enumerate(df.index)}
    for _, row in sweeps_df.iterrows():
        i = pos.get(row["index"])
        if i is None:
            continue
        signals.iloc[i] = "SELL" if row["type"] == "buy_side" else "BUY"
    return signals


def ma_crossover_strategy(
    df: pd.DataFrame,
    short_col: str = "sma_20",
    long_col: str  = "sma_50",
) -> pd.Series:
    """
    Moving Average crossover (Golden Cross / Death Cross).
    BUY  when short MA crosses above long MA.
    SELL when short MA crosses below long MA.
    """
    signals = pd.Series("HOLD", index=df.index, dtype=str)
    if short_col not in df.columns or long_col not in df.columns:
        return signals

    short = df[short_col]
    long  = df[long_col]

    golden_cross = (short > long) & (short.shift(1) <= long.shift(1))
    death_cross  = (short < long) & (short.shift(1) >= long.shift(1))

    signals[golden_cross] = "BUY"
    signals[death_cross]  = "SELL"
    return signals


# ── Dispatcher ───────────────────────────────────────────────────────────────

STRATEGY_NAMES = [
    "Manual Trading",
    "RSI Strategy",
    "MACD Strategy",
    "MA Crossover",
    "FVG Strategy",
    "Liquidity Sweep",
]


def get_signals(
    df: pd.DataFrame,
    strategy: str,
    fvg_df: pd.DataFrame | None = None,
    sweeps_df: pd.DataFrame | None = None,
) -> pd.Series:
    """Return a Series of BUY/SELL/HOLD for the chosen strategy."""
    if strategy == "RSI Strategy":
        return rsi_strategy(df)
    elif strategy == "MACD Strategy":
        return macd_strategy(df)
    elif strategy == "MA Crossover":
        return ma_crossover_strategy(df)
    elif strategy == "FVG Strategy":
        return fvg_strategy(df, fvg_df)
    elif strategy == "Liquidity Sweep":
        return sweep_strategy(df, sweeps_df)
    else:  # Manual Trading
        return pd.Series("HOLD", index=df.index, dtype=str)


def get_strategy_description(strategy: str) -> str:
    """Return a human-readable description of each strategy."""
    descriptions = {
        "RSI Strategy": (
            "Relative Strength Index (RSI) measures momentum. "
            "**BUY** when RSI dips below 30 (oversold). "
            "**SELL** when RSI rises above 70 (overbought)."
        ),
        "MACD Strategy": (
            "Moving Average Convergence Divergence tracks trend direction. "
            "**BUY** when MACD line crosses above the signal line. "
            "**SELL** when MACD line crosses below the signal line."
        ),
        "MA Crossover": (
            "Golden Cross / Death Cross using SMA-20 and SMA-50. "
            "**BUY** (Golden Cross) when SMA-20 crosses above SMA-50. "
            "**SELL** (Death Cross) when SMA-20 crosses below SMA-50."
        ),
        "FVG Strategy": (
            "Trades the candle that completes a 3-bar Fair Value Gap. "
            "**BUY** on a bullish FVG (gap = support). "
            "**SELL** on a bearish FVG (gap = resistance)."
        ),
        "Liquidity Sweep": (
            "Trades stop-hunt reversals. "
            "**BUY** after a sell-side sweep (wick below prior low, close back inside). "
            "**SELL** after a buy-side sweep (wick above prior high, close back inside)."
        ),
        "Manual Trading": "You decide when to BUY and SELL using the sidebar controls.",
    }
    return descriptions.get(strategy, "")
