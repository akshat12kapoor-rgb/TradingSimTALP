"""
Chart Renderer Module
Builds Plotly figures for the main candlestick chart and equity curve.
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, List

# Colour constants
C_GREEN       = "#00FF88"
C_RED         = "#FF4444"
C_GOLD        = "#FFD700"
C_ORANGE      = "#FF8C00"
C_BLUE        = "#00BFFF"
C_PURPLE      = "#9B59B6"
C_BG          = "#0E1117"
C_PANEL       = "#161B22"
C_GRID        = "#1E2329"
C_FVG_BULL    = "rgba(0, 255, 136, 0.10)"
C_FVG_BEAR    = "rgba(255, 68, 68, 0.10)"
C_FVG_BULL_BD = "rgba(0, 255, 136, 0.35)"
C_FVG_BEAR_BD = "rgba(255, 68, 68, 0.35)"

# Display caps to keep the chart readable
MAX_FVG_DISPLAY    = 6     # only the N most-recent unfilled FVGs
FVG_EXTEND_CANDLES = 20    # how many candles to extend each FVG rect to the right
MAX_SWEEP_DISPLAY  = 15    # only the N most-recent sweep markers


# ── Helpers ───────────────────────────────────────────────────────────────────

def _axis_style() -> dict:
    return dict(gridcolor=C_GRID, zerolinecolor="#333333", showgrid=True)


def _select_active_fvgs(
    fvg_df: pd.DataFrame, df: pd.DataFrame, limit: int
) -> pd.DataFrame:
    """Return up to `limit` most-recent FVGs whose zone hasn't been filled.

    An FVG is considered 'filled' when a later candle's range overlaps the gap,
    making it no longer actionable. Filtering these out prevents the chart from
    being buried in dozens of historical zones.
    """
    if fvg_df is None or fvg_df.empty:
        return fvg_df

    highs = df["high"].values
    lows  = df["low"].values

    active = []
    for _, fvg in fvg_df.iterrows():
        start = int(fvg["start_idx"])
        # candles after the gap's middle candle
        after_high = highs[start + 2 :] if start + 2 < len(df) else []
        after_low  = lows[start + 2 :]  if start + 2 < len(df) else []
        filled = False
        for h, l in zip(after_high, after_low):
            if l <= fvg["top"] and h >= fvg["bottom"]:
                filled = True
                break
        if not filled:
            active.append(fvg)

    if not active:
        # fall back to most recent few so the user still sees something
        return fvg_df.tail(limit)
    return pd.DataFrame(active).tail(limit)


# ── Main chart ────────────────────────────────────────────────────────────────

def render_chart(
    df: pd.DataFrame,
    signals:       Optional[pd.Series] = None,
    fvg_df:        Optional[pd.DataFrame] = None,
    sweeps_df:     Optional[pd.DataFrame] = None,
    trade_history: Optional[list] = None,
    show_ma:       bool = True,
    show_rsi:      bool = True,
    show_macd:     bool = True,
    show_fvg:      bool = True,
    show_sweeps:   bool = True,
    show_signals:  bool = False,   # small strategy-signal triangles (noisy)
    show_trades:   bool = True,    # executed BUY/SELL markers
    title:         str  = "Chart",
    current_idx:   Optional[int] = None,  # highlight candle during replay
) -> go.Figure:
    """Build and return the complete multi-panel Plotly figure."""

    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=C_BG, plot_bgcolor=C_BG,
            font=dict(color="#FAFAFA"),
            annotations=[dict(text="No data", showarrow=False,
                              font=dict(size=20, color="#888888"))],
        )
        return fig

    # ── Subplot layout ────────────────────────────────────────────────────────
    n_rows      = 1
    row_heights = [0.70]

    if show_rsi:
        n_rows      += 1
        row_heights.append(0.18)
    if show_macd:
        n_rows      += 1
        row_heights.append(0.18)

    rsi_row  = 2 if show_rsi else None
    macd_row = (2 if not show_rsi else 3) if show_macd else None

    sub_titles = [title]
    if show_rsi:
        sub_titles.append("RSI (14)")
    if show_macd:
        sub_titles.append("MACD")

    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=sub_titles,
        row_heights=row_heights,
    )

    # ── Candlestick ───────────────────────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"],
            low=df["low"],   close=df["close"],
            name="Price",
            increasing_line_color=C_GREEN,   increasing_fillcolor=C_GREEN,
            decreasing_line_color=C_RED,     decreasing_fillcolor=C_RED,
            line=dict(width=1),
        ),
        row=1, col=1,
    )

    # Replay cursor line
    if current_idx is not None and 0 <= current_idx < len(df):
        fig.add_vline(
            x=df.index[current_idx],
            line_dash="dot",
            line_color="rgba(255,255,255,0.3)",
            line_width=1,
            row=1, col=1,
        )

    # ── Moving Averages ───────────────────────────────────────────────────────
    if show_ma:
        ma_cfg = [
            ("sma_20", C_GOLD,   "SMA 20",  "solid"),
            ("sma_50", C_ORANGE, "SMA 50",  "solid"),
            ("ema_20", C_BLUE,   "EMA 20",  "dash"),
        ]
        for col, color, name, dash in ma_cfg:
            if col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index, y=df[col],
                        name=name,
                        line=dict(color=color, width=1.5, dash=dash),
                        opacity=0.85,
                    ),
                    row=1, col=1,
                )

    # ── Fair Value Gap shaded rectangles ─────────────────────────────────────
    # Only show the N most-recent FVGs that have NOT yet been filled by price,
    # and extend each rect a fixed number of candles right (not to chart end).
    if show_fvg and fvg_df is not None and not fvg_df.empty:
        recent_fvgs = _select_active_fvgs(fvg_df, df, MAX_FVG_DISPLAY)
        idx_pos = {ts: i for i, ts in enumerate(df.index)}
        last_pos = len(df) - 1
        for _, fvg in recent_fvgs.iterrows():
            is_bull = fvg["type"] == "bullish"
            start_pos = idx_pos.get(fvg["index"], 0)
            end_pos   = min(start_pos + FVG_EXTEND_CANDLES, last_pos)
            fig.add_shape(
                type="rect",
                x0=fvg["index"], x1=df.index[end_pos],
                y0=fvg["bottom"], y1=fvg["top"],
                fillcolor=C_FVG_BULL if is_bull else C_FVG_BEAR,
                line=dict(
                    color=C_FVG_BULL_BD if is_bull else C_FVG_BEAR_BD,
                    width=0.6,
                ),
                row=1, col=1,
            )

    # ── Liquidity Sweep markers ───────────────────────────────────────────────
    if show_sweeps and sweeps_df is not None and not sweeps_df.empty:
        recent_sweeps = sweeps_df.tail(MAX_SWEEP_DISPLAY)
        for _, sw in recent_sweeps.iterrows():
            is_buy = sw["type"] == "buy_side"
            y_pos  = sw["wick_price"] * (1.003 if is_buy else 0.997)
            fig.add_trace(
                go.Scatter(
                    x=[sw["index"]], y=[y_pos],
                    mode="markers",
                    marker=dict(
                        symbol="triangle-down" if is_buy else "triangle-up",
                        size=11,
                        color=C_ORANGE if is_buy else C_PURPLE,
                        line=dict(color="white", width=0.5),
                    ),
                    name="Buy-Side Sweep" if is_buy else "Sell-Side Sweep",
                    showlegend=False,
                    hovertemplate=(
                        f"{'Buy-Side' if is_buy else 'Sell-Side'} Sweep<br>"
                        f"Wick: ₹{sw['wick_price']:.2f}<br>"
                        f"Level: ₹{sw['swept_level']:.2f}<extra></extra>"
                    ),
                ),
                row=1, col=1,
            )

    # ── Strategy BUY/SELL signal markers (off by default — adds noise) ───────
    if show_signals and signals is not None:
        buys  = df[signals == "BUY"]
        sells = df[signals == "SELL"]

        if not buys.empty:
            fig.add_trace(
                go.Scatter(
                    x=buys.index, y=buys["low"],
                    mode="markers",
                    marker=dict(symbol="triangle-up-open", size=7,
                                color=C_GREEN, line=dict(color=C_GREEN, width=1),
                                opacity=0.65),
                    name="Signal BUY",
                    hovertemplate="BUY Signal @ ₹%{y:.2f}<extra></extra>",
                ),
                row=1, col=1,
            )

        if not sells.empty:
            fig.add_trace(
                go.Scatter(
                    x=sells.index, y=sells["high"],
                    mode="markers",
                    marker=dict(symbol="triangle-down-open", size=7,
                                color=C_RED, line=dict(color=C_RED, width=1),
                                opacity=0.65),
                    name="Signal SELL",
                    hovertemplate="SELL Signal @ ₹%{y:.2f}<extra></extra>",
                ),
                row=1, col=1,
            )

    # ── Executed trade markers (anchored to candle close, no offset) ─────────
    # BUY + COVER share a green dot (both buy shares).
    # SELL + SHORT share a red dot (both sell shares).
    # Per-point action label appears on hover.
    if show_trades and trade_history:
        buy_like  = [t for t in trade_history if t.action in ("BUY", "COVER")]
        sell_like = [t for t in trade_history if t.action in ("SELL", "SHORT")]

        if buy_like:
            fig.add_trace(
                go.Scatter(
                    x=[t.timestamp for t in buy_like],
                    y=[t.price for t in buy_like],
                    mode="markers",
                    marker=dict(symbol="circle", size=10,
                                color=C_GREEN,
                                line=dict(color="white", width=1.4)),
                    name="BUY / COVER",
                    customdata=[t.action for t in buy_like],
                    hovertemplate=(
                        "<b>%{customdata}</b> @ ₹%{y:.2f}<br>"
                        "%{x|%d %b %Y}<extra></extra>"
                    ),
                ),
                row=1, col=1,
            )

        if sell_like:
            fig.add_trace(
                go.Scatter(
                    x=[t.timestamp for t in sell_like],
                    y=[t.price for t in sell_like],
                    mode="markers",
                    marker=dict(symbol="circle", size=10,
                                color=C_RED,
                                line=dict(color="white", width=1.4)),
                    name="SELL / SHORT",
                    customdata=[t.action for t in sell_like],
                    hovertemplate=(
                        "<b>%{customdata}</b> @ ₹%{y:.2f}<br>"
                        "%{x|%d %b %Y}<extra></extra>"
                    ),
                ),
                row=1, col=1,
            )

    # ── RSI panel ─────────────────────────────────────────────────────────────
    if show_rsi and rsi_row and "rsi" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["rsi"],
                name="RSI",
                line=dict(color=C_PURPLE, width=1.5),
                fill="tozeroy",
                fillcolor="rgba(155, 89, 182, 0.05)",
            ),
            row=rsi_row, col=1,
        )
        for level, color in [(70, C_RED), (50, "#555555"), (30, C_GREEN)]:
            fig.add_hline(
                y=level, line_dash="dash", line_color=color,
                line_width=0.7, opacity=0.6,
                row=rsi_row, col=1,
            )
        fig.add_hrect(
            y0=70, y1=100,
            fillcolor="rgba(255,68,68,0.05)", line_width=0,
            row=rsi_row, col=1,
        )
        fig.add_hrect(
            y0=0, y1=30,
            fillcolor="rgba(0,255,136,0.05)", line_width=0,
            row=rsi_row, col=1,
        )
        fig.update_yaxes(range=[0, 100], row=rsi_row, col=1)

    # ── MACD panel ────────────────────────────────────────────────────────────
    if show_macd and macd_row and "macd" in df.columns:
        hist_colors = [
            C_GREEN if v >= 0 else C_RED
            for v in df["macd_diff"].fillna(0)
        ]
        fig.add_trace(
            go.Bar(
                x=df.index, y=df["macd_diff"],
                name="Histogram",
                marker_color=hist_colors,
                opacity=0.65,
            ),
            row=macd_row, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["macd"],
                name="MACD",
                line=dict(color=C_BLUE, width=1.5),
            ),
            row=macd_row, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["macd_signal"],
                name="Signal",
                line=dict(color=C_ORANGE, width=1.5),
            ),
            row=macd_row, col=1,
        )
        fig.add_hline(
            y=0, line_dash="dash", line_color="#555555",
            line_width=0.7, opacity=0.5,
            row=macd_row, col=1,
        )

    # ── Global layout ─────────────────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
        font=dict(color="#FAFAFA", family="Inter, Arial"),
        xaxis_rangeslider_visible=False,
        height=620,
        margin=dict(l=50, r=40, t=40, b=24),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right",  x=1,
            bgcolor="rgba(14,17,23,0.6)",
            bordercolor="rgba(255,255,255,0.06)", borderwidth=1,
            font=dict(size=10.5),
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=C_PANEL, font_size=12),
    )

    # Apply axis styles to every subplot row
    for r in range(1, n_rows + 1):
        fig.update_xaxes(**_axis_style(), row=r, col=1)
        fig.update_yaxes(**_axis_style(), row=r, col=1)

    # Subplot title colour
    for ann in fig.layout.annotations:
        ann.font.color = "#AAAAAA"
        ann.font.size  = 11

    return fig


# ── Signal / Event focused chart (Learning Mode) ─────────────────────────────

def render_signal_chart(
    df: pd.DataFrame,
    event: dict,
    window: int = 30,
    show_ma: bool = True,
) -> go.Figure:
    """
    Compact zoomed-in chart for the Learning Mode panel.
    Shows `window` candles of context ending at event['idx'],
    with the trigger candle prominently annotated.
    """
    idx      = min(event.get("idx", len(df) - 1), len(df) - 1)
    start    = max(0, idx - window + 1)
    focus_df = df.iloc[start : idx + 1]
    kind     = event.get("kind", "signal")

    if focus_df.empty:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor=C_BG, plot_bgcolor=C_BG, height=280)
        return fig

    # ── Candlestick ───────────────────────────────────────────────────────────
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=focus_df.index,
            open=focus_df["open"], high=focus_df["high"],
            low=focus_df["low"],   close=focus_df["close"],
            name="Price",
            increasing_line_color=C_GREEN, increasing_fillcolor=C_GREEN,
            decreasing_line_color=C_RED,   decreasing_fillcolor=C_RED,
            line=dict(width=1),
        )
    )

    # ── Moving averages ───────────────────────────────────────────────────────
    if show_ma:
        for col, color, name in [
            ("sma_20", C_GOLD,   "SMA 20"),
            ("sma_50", C_ORANGE, "SMA 50"),
        ]:
            if col in focus_df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=focus_df.index, y=focus_df[col],
                        name=name, line=dict(color=color, width=1.2),
                        opacity=0.85,
                    )
                )

    signal_ts    = focus_df.index[-1]
    signal_price = float(event.get("price", focus_df.iloc[-1]["close"]))

    # ── Soft highlight band on signal candle ──────────────────────────────────
    fig.add_vline(
        x=signal_ts,
        line=dict(color="rgba(255,255,255,0.25)", width=1.5, dash="dot"),
    )

    # ── Event-type specific overlays ──────────────────────────────────────────
    if kind == "signal":
        sig         = event["signal"]
        arrow_color = C_GREEN if sig == "BUY" else C_RED
        candle      = focus_df.iloc[-1]
        y_marker    = candle["low"] * 0.991 if sig == "BUY" else candle["high"] * 1.009
        sym         = "triangle-up" if sig == "BUY" else "triangle-down"
        txt_pos     = "bottom center" if sig == "BUY" else "top center"
        ax_offset   = 55 if sig == "BUY" else -55

        # Big signal arrow
        fig.add_trace(
            go.Scatter(
                x=[signal_ts], y=[y_marker],
                mode="markers+text",
                marker=dict(symbol=sym, size=20, color=arrow_color,
                            line=dict(color="white", width=1.5)),
                text=[f" {sig}"], textposition=txt_pos,
                textfont=dict(color=arrow_color, size=13, family="Arial Black"),
                showlegend=False,
            )
        )
        # Callout annotation
        fig.add_annotation(
            x=signal_ts, y=signal_price,
            text=f"<b>{sig} Signal</b><br>₹{signal_price:.2f}",
            showarrow=True, arrowhead=2,
            arrowcolor=arrow_color, arrowwidth=2,
            ax=ax_offset, ay=-60 if sig == "BUY" else 60,
            bgcolor=arrow_color, opacity=0.9,
            font=dict(color="#0E1117", size=11, family="Arial Black"),
            bordercolor=arrow_color, borderwidth=1, borderpad=5,
        )

    elif kind == "fvg":
        is_bull = event["fvg_type"] == "bullish"
        fill    = C_FVG_BULL if is_bull else C_FVG_BEAR
        border  = C_FVG_BULL_BD if is_bull else C_FVG_BEAR_BD
        label   = "Bullish FVG" if is_bull else "Bearish FVG"
        lcolor  = C_GREEN if is_bull else C_RED

        fig.add_hrect(
            y0=event["bottom"], y1=event["top"],
            fillcolor=fill, line=dict(color=border, width=1),
        )
        # Zone boundary lines with labels
        for y_val, lbl in [(event["top"], "Zone Top"), (event["bottom"], "Zone Bottom")]:
            fig.add_hline(
                y=y_val, line_dash="dot", line_color=border, line_width=1,
                annotation_text=f"  {lbl} ₹{y_val:.2f}",
                annotation_font_color=lcolor, annotation_font_size=10,
                annotation_position="right",
            )

        # Spotlight the 3 candles that form the FVG (C1, C2, C3).
        # mid_idx is the middle candle; pattern spans [mid-1, mid, mid+1].
        mid_idx = int(event.get("mid_idx", idx - 1))
        for offset, lbl in [(-1, "C1"), (0, "C2"), (+1, "C3")]:
            cidx = mid_idx + offset
            if 0 <= cidx < len(df):
                ts = df.index[cidx]
                fig.add_vline(
                    x=ts,
                    line=dict(color=border, width=1.2, dash="solid"),
                    opacity=0.55,
                )
                fig.add_annotation(
                    x=ts, y=df.iloc[cidx]["high"],
                    text=f"<b>{lbl}</b>",
                    showarrow=False, yshift=14,
                    font=dict(color=lcolor, size=10, family="Arial Black"),
                    bgcolor="rgba(14,17,23,0.85)",
                    bordercolor=border, borderwidth=1, borderpad=2,
                )

        fig.add_annotation(
            x=signal_ts, y=(event["top"] + event["bottom"]) / 2,
            text=f"<b>{label}</b><br>Look at C1→C3",
            showarrow=False,
            bgcolor=fill, font=dict(color=lcolor, size=11, family="Arial Black"),
            bordercolor=border, borderwidth=1, borderpad=4,
        )

    elif kind == "sweep":
        st_type = event["sweep_type"]
        level   = event["swept_level"]
        color   = C_ORANGE if st_type == "buy_side" else C_PURPLE
        label   = "Buy-Side Sweep" if st_type == "buy_side" else "Sell-Side Sweep"
        candle  = focus_df.iloc[-1]

        # Swept level line
        fig.add_hline(
            y=level, line_dash="dash", line_color=color, line_width=1.5,
            annotation_text=f"  Swept Level ₹{level:.2f}",
            annotation_font_color=color, annotation_font_size=10,
            annotation_position="right",
        )
        # Wick extent shading
        wick_y = candle["high"] if st_type == "buy_side" else candle["low"]
        if st_type == "buy_side":
            fig.add_hrect(
                y0=level, y1=wick_y,
                fillcolor=f"rgba(255,140,0,0.10)", line_width=0,
            )
        else:
            fig.add_hrect(
                y0=wick_y, y1=level,
                fillcolor=f"rgba(155,89,182,0.10)", line_width=0,
            )

        sym    = "triangle-down" if st_type == "buy_side" else "triangle-up"
        y_mkr  = wick_y * (1.004 if st_type == "buy_side" else 0.996)
        fig.add_trace(
            go.Scatter(
                x=[signal_ts], y=[y_mkr],
                mode="markers",
                marker=dict(symbol=sym, size=16, color=color,
                            line=dict(color="white", width=1.2)),
                showlegend=False,
            )
        )
        fig.add_annotation(
            x=signal_ts, y=wick_y,
            text=f"<b>{label}</b><br>₹{float(event.get('price', wick_y)):.2f}",
            showarrow=True, arrowhead=2,
            arrowcolor=color, arrowwidth=2,
            ax=60, ay=-50,
            bgcolor=f"rgba(30,35,41,0.9)",
            font=dict(color=color, size=11, family="Arial Black"),
            bordercolor=color, borderwidth=1, borderpad=4,
        )

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
        font=dict(color="#FAFAFA", family="Inter, Arial"),
        xaxis_rangeslider_visible=False,
        height=295,
        margin=dict(l=50, r=16, t=28, b=24),
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(bgcolor=C_PANEL, font_size=11),
        xaxis=_axis_style(),
        yaxis=_axis_style(),
    )
    return fig


# ── Equity Curve ─────────────────────────────────────────────────────────────

def render_equity_curve(
    portfolio_history: list,
    initial_capital: float = 100_000.0,
) -> go.Figure:
    """Build an equity-curve chart from (timestamp, value) pairs."""
    if not portfolio_history:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=C_BG, plot_bgcolor=C_BG,
            font=dict(color="#FAFAFA"),
            title="Equity Curve — no data yet",
        )
        return fig

    xs = [p[0] for p in portfolio_history]
    ys = [p[1] for p in portfolio_history]

    color_line = C_GREEN if ys[-1] >= ys[0] else C_RED
    color_fill = "rgba(0,255,136,0.08)" if ys[-1] >= ys[0] else "rgba(255,68,68,0.08)"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=xs, y=ys,
            mode="lines",
            fill="tozeroy",
            fillcolor=color_fill,
            line=dict(color=color_line, width=2),
            name="Portfolio Value",
            hovertemplate="₹%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_hline(
        y=initial_capital,
        line_dash="dash", line_color="#555555",
        annotation_text="Initial Capital",
        annotation_font_color="#888888",
    )

    fig.update_layout(
        title="📈 Equity Curve",
        paper_bgcolor=C_BG,
        plot_bgcolor=C_BG,
        font=dict(color="#FAFAFA"),
        xaxis=_axis_style(),
        yaxis=_axis_style(),
        height=310,
        margin=dict(l=55, r=55, t=45, b=30),
    )
    return fig
