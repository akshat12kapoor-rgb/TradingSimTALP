"""
Performance Analytics Module
Derives statistics from trade history and portfolio equity curve.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List


def calculate_performance_metrics(
    trade_history:     list,
    portfolio_history: list,
    initial_capital:   float = 100_000.0,
) -> dict:
    """
    Compute comprehensive performance statistics.

    Returns a dict with:
        total_return, total_pnl, num_trades, num_wins, num_losses,
        win_rate, avg_win, avg_loss, profit_factor,
        max_drawdown, sharpe_ratio, calmar_ratio, best_trade, worst_trade
    """
    # Default empty state
    empty = dict(
        total_return=0.0,
        total_pnl=0.0,
        num_trades=0,
        num_wins=0,
        num_losses=0,
        win_rate=0.0,
        avg_win=0.0,
        avg_loss=0.0,
        profit_factor=0.0,
        max_drawdown=0.0,
        sharpe_ratio=0.0,
        calmar_ratio=0.0,
        best_trade=0.0,
        worst_trade=0.0,
    )

    if not trade_history:
        return empty

    # ── Trade stats ───────────────────────────────────────────────────────────
    # Closing trades = SELL (close long) + COVER (close short).
    closes  = [t for t in trade_history if t.action in ("SELL", "COVER")]
    wins    = [t for t in closes if t.pnl > 0]
    losses  = [t for t in closes if t.pnl <= 0]

    total_pnl     = sum(t.pnl for t in closes)
    win_rate      = len(wins) / len(closes) * 100 if closes else 0.0
    avg_win       = float(np.mean([t.pnl for t in wins]))   if wins   else 0.0
    avg_loss      = float(np.mean([t.pnl for t in losses])) if losses else 0.0
    best_trade    = max((t.pnl for t in closes), default=0.0)
    worst_trade   = min((t.pnl for t in closes), default=0.0)

    gross_wins    = sum(t.pnl for t in wins)
    gross_losses  = abs(sum(t.pnl for t in losses))
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else float("inf")

    # ── Portfolio stats ───────────────────────────────────────────────────────
    if portfolio_history:
        values       = pd.Series([p[1] for p in portfolio_history], dtype=float)
        final_value  = values.iloc[-1]
        total_return = (final_value - initial_capital) / initial_capital * 100

        # Max drawdown
        running_max = values.cummax()
        drawdowns   = (running_max - values) / running_max * 100
        max_dd      = float(drawdowns.max())

        # Sharpe ratio (annualised, assume daily observations)
        rets = values.pct_change().dropna()
        if len(rets) > 1 and rets.std() > 0:
            sharpe = float(rets.mean() / rets.std() * np.sqrt(252))
        else:
            sharpe = 0.0

        # Calmar ratio
        calmar = (total_return / max_dd) if max_dd > 0 else 0.0
    else:
        total_return = total_pnl / initial_capital * 100
        max_dd       = 0.0
        sharpe       = 0.0
        calmar       = 0.0

    return dict(
        total_return  = total_return,
        total_pnl     = total_pnl,
        num_trades    = len(trade_history),
        num_wins      = len(wins),
        num_losses    = len(losses),
        win_rate      = win_rate,
        avg_win       = avg_win,
        avg_loss      = avg_loss,
        profit_factor = profit_factor,
        max_drawdown  = max_dd,
        sharpe_ratio  = sharpe,
        calmar_ratio  = calmar,
        best_trade    = best_trade,
        worst_trade   = worst_trade,
    )


def summarise_by_strategy(trade_history: list) -> pd.DataFrame:
    """Group closed-trade P&L by strategy name."""
    rows = [
        {"Strategy": t.strategy, "P&L": t.pnl, "Win": t.pnl > 0}
        for t in trade_history if t.action in ("SELL", "COVER")
    ]
    if not rows:
        return pd.DataFrame(columns=["Strategy", "Trades", "Total P&L", "Win Rate %"])

    df = pd.DataFrame(rows)
    summary = (
        df.groupby("Strategy")
          .agg(
              Trades    =("P&L", "count"),
              total_pnl =("P&L", "sum"),
              win_rate  =("Win", "mean"),
          )
          .rename(columns={"total_pnl": "Total P&L", "win_rate": "Win Rate %"})
          .reset_index()
    )
    summary["Win Rate %"] = (summary["Win Rate %"] * 100).round(1)
    summary["Total P&L"]  = summary["Total P&L"].round(2)
    return summary
