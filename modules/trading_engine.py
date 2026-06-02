"""
Trading Engine Module
Manages virtual capital, position tracking, trade execution, and P&L.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Trade:
    timestamp: object          # pd.Timestamp or datetime
    action:    str             # "BUY" or "SELL"
    price:     float
    quantity:  int
    total_value: float
    pnl:       float = 0.0
    strategy:  str   = "Manual"
    balance_after: float = 0.0


# ── Engine ────────────────────────────────────────────────────────────────────

class TradingEngine:
    """
    Paper-trading engine with:
    - Signed position management (positive = long, negative = short)
    - Average cost basis (per active side)
    - Realized + unrealized P&L (works for both sides via a single formula)
    - Portfolio history for equity curve
    - Win-rate and trade-log statistics

    Position model:
        holdings > 0  → long  position, avg_entry_price = avg buy price
        holdings < 0  → short position, avg_entry_price = avg short price
        holdings == 0 → flat

    A BUY first covers any existing short, then opens/adds to long with leftover.
    A SELL first closes any existing long, then opens/adds to short with leftover.
    Margin for shorting is proxied by `balance` (≈ 100% cash collateral).
    """

    def __init__(self, initial_capital: float = 100_000.0):
        self.initial_capital = initial_capital
        self.reset()

    # ── Core state ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        self.balance:          float       = self.initial_capital
        self.holdings:         int         = 0
        self.avg_entry_price:  float       = 0.0
        self.realized_pnl:     float       = 0.0
        self.trade_history:    List[Trade] = []
        self.portfolio_history: list       = []   # list of (timestamp, value)

    # ── Execution ─────────────────────────────────────────────────────────────

    def buy(
        self,
        price:     float,
        timestamp: object,
        quantity:  Optional[int] = None,
        strategy:  str = "Manual",
        pct:       float = 0.10,   # fraction of balance to deploy when qty=None
    ) -> dict:
        """BUY: covers any short first, then opens/adds to a long position.
        Returns a result dict. Capped by available cash (no over-leverage)."""
        if quantity is None:
            quantity = max(1, int((self.balance * pct) / price))

        max_affordable = int(self.balance / price) if price > 0 else 0
        quantity = min(quantity, max_affordable)
        if quantity <= 0:
            return {"success": False, "message": "Insufficient balance to buy."}

        total_qty = quantity
        msgs:   list[str] = []
        actions: list[str] = []
        total_pnl_this_call = 0.0

        # ── 1) Cover any open short first ─────────────────────────────────
        if self.holdings < 0:
            cover_qty = min(quantity, -self.holdings)
            cover_cost = cover_qty * price
            cover_pnl  = (self.avg_entry_price - price) * cover_qty
            self.realized_pnl += cover_pnl
            self.balance  -= cover_cost
            self.holdings += cover_qty
            if self.holdings == 0:
                self.avg_entry_price = 0.0

            self.trade_history.append(Trade(
                timestamp=timestamp, action="COVER", price=price,
                quantity=cover_qty, total_value=cover_cost,
                pnl=cover_pnl, strategy=strategy,
                balance_after=self.balance,
            ))
            total_pnl_this_call += cover_pnl
            pnl_str = (f"+₹{cover_pnl:,.0f}" if cover_pnl >= 0
                       else f"−₹{abs(cover_pnl):,.0f}")
            msgs.append(f"Covered {cover_qty} short @ ₹{price:,.2f} ({pnl_str})")
            actions.append("COVER")
            quantity -= cover_qty

        # ── 2) Open / add to long with the remainder ──────────────────────
        if quantity > 0:
            cost = quantity * price
            if self.holdings > 0:
                self.avg_entry_price = (
                    (self.avg_entry_price * self.holdings) + cost
                ) / (self.holdings + quantity)
            else:
                self.avg_entry_price = price
            self.balance  -= cost
            self.holdings += quantity

            self.trade_history.append(Trade(
                timestamp=timestamp, action="BUY", price=price,
                quantity=quantity, total_value=cost,
                strategy=strategy, balance_after=self.balance,
            ))
            msgs.append(f"Bought {quantity} @ ₹{price:,.2f}")
            actions.append("BUY")

        return {
            "success":  True,
            "message":  " · ".join(msgs),
            "quantity": total_qty,
            "price":    price,
            "pnl":      total_pnl_this_call,
            "actions":  actions,
        }

    def sell(
        self,
        price:     float,
        timestamp: object,
        quantity:  Optional[int] = None,
        strategy:  str = "Manual",
        pct:       float = 0.10,
    ) -> dict:
        """SELL: closes any long first, then opens/adds to a short with the
        remainder. Margin for new shorts is proxied by available cash."""
        if quantity is None:
            quantity = (
                self.holdings if self.holdings > 0
                else max(1, int((self.balance * pct) / price))
            )

        total_qty = quantity
        msgs:   list[str] = []
        actions: list[str] = []
        total_pnl_this_call = 0.0

        # ── 1) Close existing long ────────────────────────────────────────
        if self.holdings > 0 and quantity > 0:
            close_qty = min(quantity, self.holdings)
            proceeds  = close_qty * price
            pnl       = (price - self.avg_entry_price) * close_qty
            self.realized_pnl += pnl
            self.balance  += proceeds
            self.holdings -= close_qty
            if self.holdings == 0:
                self.avg_entry_price = 0.0

            self.trade_history.append(Trade(
                timestamp=timestamp, action="SELL", price=price,
                quantity=close_qty, total_value=proceeds,
                pnl=pnl, strategy=strategy,
                balance_after=self.balance,
            ))
            total_pnl_this_call += pnl
            pnl_str = (f"+₹{pnl:,.0f}" if pnl >= 0
                       else f"−₹{abs(pnl):,.0f}")
            msgs.append(f"Sold {close_qty} @ ₹{price:,.2f} ({pnl_str})")
            actions.append("SELL")
            quantity -= close_qty

        # ── 2) Open / add to short with the remainder ─────────────────────
        if quantity > 0:
            max_short = int(self.balance / price) if price > 0 else 0
            short_qty = min(quantity, max_short)
            if short_qty <= 0:
                if not msgs:
                    return {
                        "success": False,
                        "message": "Insufficient margin to open a short.",
                    }
            else:
                proceeds = short_qty * price
                if self.holdings < 0:
                    self.avg_entry_price = (
                        (self.avg_entry_price * (-self.holdings)) + proceeds
                    ) / ((-self.holdings) + short_qty)
                else:
                    self.avg_entry_price = price
                self.balance  += proceeds
                self.holdings -= short_qty

                self.trade_history.append(Trade(
                    timestamp=timestamp, action="SHORT", price=price,
                    quantity=short_qty, total_value=proceeds,
                    strategy=strategy, balance_after=self.balance,
                ))
                msgs.append(f"Shorted {short_qty} @ ₹{price:,.2f}")
                actions.append("SHORT")

        return {
            "success":  True,
            "message":  " · ".join(msgs),
            "quantity": total_qty,
            "price":    price,
            "pnl":      total_pnl_this_call,
            "actions":  actions,
        }

    # ── Snapshot helpers ──────────────────────────────────────────────────────

    def record_portfolio_value(self, timestamp: object, current_price: float) -> None:
        """Append (timestamp, portfolio_value) to the history list."""
        self.portfolio_history.append((timestamp, self.get_portfolio_value(current_price)))

    def get_portfolio_value(self, current_price: float) -> float:
        return self.balance + self.holdings * current_price

    def get_unrealized_pnl(self, current_price: float) -> float:
        if self.holdings == 0:
            return 0.0
        return (current_price - self.avg_entry_price) * self.holdings

    # ── Aggregate metrics ─────────────────────────────────────────────────────

    def get_metrics(self, current_price: float) -> dict:
        portfolio_value  = self.get_portfolio_value(current_price)
        unrealized_pnl   = self.get_unrealized_pnl(current_price)
        total_pnl        = self.realized_pnl + unrealized_pnl
        total_return_pct = (
            (portfolio_value - self.initial_capital) / self.initial_capital * 100
        )

        closes        = [t for t in self.trade_history
                         if t.action in ("SELL", "COVER")]
        winning       = [t for t in closes if t.pnl > 0]
        losing        = [t for t in closes if t.pnl <= 0]
        win_rate      = len(winning) / len(closes) * 100 if closes else 0.0

        return {
            "balance":          self.balance,
            "holdings":         self.holdings,
            "avg_entry_price":  self.avg_entry_price,
            "portfolio_value":  portfolio_value,
            "realized_pnl":     self.realized_pnl,
            "unrealized_pnl":   unrealized_pnl,
            "total_pnl":        total_pnl,
            "total_return":     total_return_pct,
            "num_trades":       len(self.trade_history),
            "num_buys":         len([t for t in self.trade_history if t.action == "BUY"]),
            "num_sells":        len([t for t in self.trade_history if t.action == "SELL"]),
            "num_shorts":       len([t for t in self.trade_history if t.action == "SHORT"]),
            "num_covers":       len([t for t in self.trade_history if t.action == "COVER"]),
            "win_rate":         win_rate,
            "num_wins":         len(winning),
            "num_losses":       len(losing),
        }
