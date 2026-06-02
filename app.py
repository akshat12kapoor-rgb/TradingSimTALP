"""
Stock Market Simulator + Technical Analysis Learning Platform
Main Streamlit application entry point.
"""
import pandas as pd
import streamlit as st

from modules.data_fetcher   import fetch_data, get_available_periods
from modules.indicators     import calculate_all_indicators
from modules.strategies     import get_signals, STRATEGY_NAMES, get_strategy_description
from modules.smc_detector   import (
    detect_fvg, detect_liquidity_sweeps,
    FVG_EXPLANATION, SWEEP_EXPLANATION,
)
from modules.trading_engine import TradingEngine
from modules.chart_renderer import render_chart, render_equity_curve, render_signal_chart
from modules.performance    import calculate_performance_metrics, summarise_by_strategy

# ════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Stock Simulator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Base ── */
.main, [data-testid="stAppViewContainer"] { background:#0E1117; }
[data-testid="stSidebar"]                 { background:#12161E; border-right:1px solid #1E2329; }
[data-testid="stSidebar"] section         { padding-top:0.5rem; }
#MainMenu, footer, header                 { visibility:hidden; }

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background:#1A1F2E;
    border:1px solid #252D3D;
    border-radius:10px;
    padding:12px 14px;
}
[data-testid="stMetricValue"]  { font-size:1.25rem !important; font-weight:700 !important; }
[data-testid="stMetricLabel"]  { font-size:0.72rem !important; color:#8892A4 !important; letter-spacing:.04em; text-transform:uppercase; }
[data-testid="stMetricDelta"]  { font-size:0.75rem !important; }

/* ── Buttons ── */
.stButton > button {
    border-radius:7px; font-weight:600;
    transition:all .15s ease;
    border:1px solid transparent;
}
.stButton > button:hover { opacity:.88; transform:translateY(-1px); }

/* ── Sidebar section headers ── */
.sidebar-section {
    font-size:.68rem; font-weight:700; letter-spacing:.1em;
    text-transform:uppercase; color:#4A90E2;
    margin:14px 0 6px; padding:0;
}

/* ── Ticker badge ── */
.ticker-badge {
    display:inline-flex; align-items:center; gap:6px;
    background:#1A2744; border:1px solid #2A4080;
    border-radius:20px; padding:4px 12px;
    font-size:.78rem; color:#7EB3FF; font-weight:600;
}

/* ── Replay status bar ── */
.status-pill {
    background:#1A1F2E; border:1px solid #252D3D;
    border-radius:20px; padding:5px 14px;
    font-size:.78rem; color:#8892A4;
    display:inline-flex; align-items:center; gap:8px;
}
.status-pill b { color:#FAFAFA; }

/* ── Replay controls row ── */
.replay-bar {
    background:#12161E; border:1px solid #1E2329;
    border-radius:10px; padding:10px 16px; margin-bottom:8px;
}

/* ── Learning panel ── */
.lp-outer {
    background:#0A1628;
    border:2px solid #2A4A8A;
    border-radius:14px;
    padding:20px 22px 16px;
    margin-bottom:10px;
}
.lp-header {
    display:flex; align-items:center; gap:10px;
    margin-bottom:12px;
}
.lp-badge {
    padding:3px 10px; border-radius:20px;
    font-size:.72rem; font-weight:700; letter-spacing:.05em;
}
.badge-buy    { background:#0D3320; color:#00FF88; border:1px solid #00FF88; }
.badge-sell   { background:#330D0D; color:#FF4444; border:1px solid #FF4444; }
.badge-fvg    { background:#1A2A0A; color:#AAEE44; border:1px solid #AAEE44; }
.badge-sweep  { background:#1A0D2E; color:#BB88FF; border:1px solid #BB88FF; }
.badge-hold   { background:#1A1A1A; color:#AAAAAA; border:1px solid #555555; }

/* ── Outcome card ── */
.outcome-card {
    background:#131A27; border:1px solid #252D3D;
    border-radius:10px; padding:14px 16px; margin-top:10px;
}

/* ── Tab bar ── */
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-weight:600; font-size:.82rem;
}
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background:#12161E; border-radius:8px; padding:2px 4px;
}

/* ── Dividers ── */
hr { border-color:#1E2329 !important; margin:10px 0 !important; }

/* ── Info/success/error overrides ── */
[data-testid="stAlert"] { border-radius:8px; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TICKER CATALOGUE  (combobox data)
# ════════════════════════════════════════════════════════════════════════════
TICKER_OPTIONS = [
    # US Large-Cap
    "AAPL  —  Apple Inc.",
    "MSFT  —  Microsoft",
    "GOOGL —  Alphabet (Google)",
    "AMZN  —  Amazon",
    "NVDA  —  NVIDIA",
    "TSLA  —  Tesla",
    "META  —  Meta Platforms",
    "BRK-B —  Berkshire Hathaway",
    "JPM   —  JPMorgan Chase",
    "V     —  Visa",
    # Indian Stocks
    "RELIANCE.NS  —  Reliance Industries",
    "TCS.NS       —  Tata Consultancy",
    "INFY.NS      —  Infosys",
    "HDFCBANK.NS  —  HDFC Bank",
    "ICICIBANK.NS —  ICICI Bank",
    "WIPRO.NS     —  Wipro",
    "BAJFINANCE.NS—  Bajaj Finance",
    # Crypto
    "BTC-USD  —  Bitcoin",
    "ETH-USD  —  Ethereum",
    "BNB-USD  —  BNB",
    # ETFs
    "SPY  —  S&P 500 ETF",
    "QQQ  —  NASDAQ-100 ETF",
    "GLD  —  Gold ETF",
    # Custom
    "✏️  Custom ticker...",
]

def _parse_ticker(option: str) -> str:
    """Extract ticker symbol from 'AAPL  —  Apple Inc.' style string."""
    if option.startswith("✏️"):
        return ""
    return option.split("—")[0].strip().replace(" ", "")


# ════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ════════════════════════════════════════════════════════════════════════════
def _init() -> None:
    defaults = {
        "df":              None,
        "ticker":          "AAPL",
        "interval":        "1d",
        "period":          "1y",
        "data_loaded":     False,
        "fvg_df":          None,
        "sweeps_df":       None,
        "strategy":        "Manual Trading",
        "signals":         None,
        "engine":          TradingEngine(),
        "replay_idx":      0,
        "replaying":       False,
        "learning_mode":   False,
        "learning_pause":  False,
        "learning_event":  None,
        "show_outcome":    False,
        "user_decision":   None,
        "last_msg":        "",
        "last_msg_type":   "info",
        "last_action_text": "",
        "last_action_idx":  None,
        # combobox state
        "ticker_option":   "AAPL  —  Apple Inc.",
        "custom_ticker":   "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════
def _current_price() -> float:
    df  = st.session_state.df
    idx = min(st.session_state.replay_idx, len(df) - 1)
    return float(df.iloc[idx]["close"])


def _show_msg() -> None:
    msg, kind = st.session_state.last_msg, st.session_state.last_msg_type
    if msg:
        {"success": st.success, "error": st.error}.get(kind, st.info)(msg)


def _set_msg(text: str, kind: str = "info") -> None:
    st.session_state.last_msg      = text
    st.session_state.last_msg_type = kind


def _clear_pause() -> None:
    """Exit a Learning Mode pause so static/replay branches can take over.
    Returns the idx the user was paused on (or None if no pause was active)."""
    if not st.session_state.get("learning_pause"):
        return None
    paused_idx = (st.session_state.learning_event or {}).get("idx")
    st.session_state.learning_pause = False
    st.session_state.learning_event = None
    st.session_state.show_outcome   = False
    return paused_idx


def _auto_trade(engine, sig: str, price: float, ts, strategy: str):
    """Execute a strategy signal with short-selling enabled.

    BUY  signal → ensure we are long  (cover any short, then open a long).
    SELL signal → ensure we are short (close any long, then open a short).
    Already on the right side? Skip — don't pyramid the position.

    Returns (acted: bool, status_text: str) for the replay pill.
    """
    if sig == "BUY" and engine.holdings <= 0:
        if engine.holdings < 0:
            engine.buy(price, ts, quantity=-engine.holdings, strategy=strategy)
        if engine.balance > price:
            engine.buy(price, ts, strategy=strategy)
        return True, f"🟢 BUY @ ₹{price:,.2f}"
    if sig == "SELL" and engine.holdings >= 0:
        if engine.holdings > 0:
            engine.sell(price, ts, quantity=engine.holdings, strategy=strategy)
        if engine.balance > price:
            engine.sell(price, ts, strategy=strategy)
        return True, f"🔴 SELL @ ₹{price:,.2f}"
    return False, ""


def _on_slider_change() -> None:
    """Fires when the user drags the replay slider. Programmatic changes
    to candle_slider DON'T fire this — that's the whole point: we use it
    to distinguish a real user move from a stale-widget re-render."""
    st.session_state.replay_idx = st.session_state.candle_slider
    _clear_pause()
    st.session_state.replaying = False


def _load_data(ticker: str, period: str, interval: str) -> None:
    with st.spinner(f"Fetching **{ticker}** …"):
        try:
            df = fetch_data(ticker, period=period, interval=interval)
        except RuntimeError as e:
            _set_msg(str(e), "error")
            return

    if df.empty:
        _set_msg("No data returned — check ticker symbol.", "error")
        return

    df = calculate_all_indicators(df)
    fvg_df_local    = detect_fvg(df)
    sweeps_df_local = detect_liquidity_sweeps(df)
    st.session_state.update(
        df=df, ticker=ticker, interval=interval, period=period,
        data_loaded=True,
        replay_idx=min(50, len(df) - 1),
        fvg_df=fvg_df_local,
        sweeps_df=sweeps_df_local,
        signals=get_signals(
            df, st.session_state.strategy,
            fvg_df=fvg_df_local, sweeps_df=sweeps_df_local,
        ),
        engine=TradingEngine(),
        replaying=False, learning_pause=False, last_msg="",
        last_action_text="", last_action_idx=None,
    )
    n_fvg    = len(st.session_state.fvg_df)
    n_sweeps = len(st.session_state.sweeps_df)
    _set_msg(
        f"✅ Loaded **{len(df)}** candles for **{ticker}** &nbsp;·&nbsp; "
        f"{n_fvg} FVGs · {n_sweeps} Sweeps detected",
        "success",
    )


def _get_indicator_snapshot(idx: int) -> dict:
    """Return indicator values at a given candle index for the learning panel."""
    df = st.session_state.df
    row = df.iloc[idx]
    return {
        "rsi":         round(float(row.get("rsi",  float("nan"))), 1),
        "macd":        round(float(row.get("macd", float("nan"))), 4),
        "macd_signal": round(float(row.get("macd_signal", float("nan"))), 4),
        "sma_20":      round(float(row.get("sma_20", float("nan"))), 2),
        "sma_50":      round(float(row.get("sma_50", float("nan"))), 2),
        "close":       round(float(row["close"]), 2),
    }


# ════════════════════════════════════════════════════════════════════════════
# REPLAY FRAGMENT
# Module-level so it has a stable identity across script reruns — required by
# st.fragment. It reads all state from st.session_state (no closure capture).
# Ticks once every 0.4s; the fragment-scoped rerun is what keeps the page
# scroll position from jumping when the chart updates.
# ════════════════════════════════════════════════════════════════════════════

@st.fragment(run_every=0.25)
def _replay_tick() -> None:
    ss = st.session_state
    if not ss.get("replaying"):
        return

    df = ss.get("df")
    if df is None:
        ss.replaying = False
        return

    idx = ss.replay_idx

    # End of data — exit replay branch via full app rerun
    if idx >= len(df) - 1:
        ss.replaying = False
        ss.last_msg = "✅ Replay complete. Review your performance below."
        ss.last_msg_type = "success"
        st.rerun(scope="app")

    engine     = ss.engine
    signals    = ss.signals
    fvg_df     = ss.fvg_df
    sweeps_df  = ss.sweeps_df
    strategy   = ss.strategy
    price_now  = float(df.iloc[idx]["close"])
    ts_now     = df.index[idx]

    # Strategy / Learning-pause checks
    if strategy != "Manual Trading" and signals is not None:
        sig = signals.iloc[idx]
        if ss.learning_mode and sig in ("BUY", "SELL"):
            ss.replaying      = False
            ss.learning_pause = True
            ss.learning_event = dict(
                kind="signal", signal=sig,
                price=price_now, timestamp=ts_now, idx=idx,
            )
            st.rerun(scope="app")
        acted, action_text = _auto_trade(engine, sig, price_now, ts_now, strategy)
        if acted:
            ss.last_action_text = action_text
            ss.last_action_idx  = idx

    # FVG completes at start_idx + 1 (the third candle of the 3-bar pattern).
    # Pause one tick after so all three forming candles are visible.
    if ss.learning_mode and fvg_df is not None and not fvg_df.empty:
        hit = fvg_df[fvg_df["start_idx"] == idx - 1]
        if not hit.empty:
            row = hit.iloc[0]
            ss.replaying      = False
            ss.learning_pause = True
            ss.learning_event = dict(
                kind="fvg", fvg_type=row["type"],
                price=price_now, timestamp=ts_now, idx=idx,
                mid_idx=int(row["start_idx"]),
                top=row["top"], bottom=row["bottom"],
            )
            st.rerun(scope="app")

    if ss.learning_mode and sweeps_df is not None and not sweeps_df.empty:
        hit = sweeps_df[sweeps_df["index"] == ts_now]
        if not hit.empty:
            row = hit.iloc[0]
            ss.replaying      = False
            ss.learning_pause = True
            ss.learning_event = dict(
                kind="sweep", sweep_type=row["type"],
                price=price_now, timestamp=ts_now, idx=idx,
                swept_level=row["swept_level"],
            )
            st.rerun(scope="app")

    engine.record_portfolio_value(ts_now, price_now)

    # Build slices honouring current overlay toggles (read from widget keys)
    show_fvg     = ss.get("ov_fvg", False)
    show_sweeps  = ss.get("ov_sweeps", False)
    show_signals = ss.get("ov_signals", False)
    show_trades  = ss.get("ov_trades", True)
    vis_df     = df.iloc[: idx + 1]
    vis_sig    = signals.iloc[: idx + 1] if signals is not None else None
    vis_fvg    = (
        fvg_df[fvg_df["start_idx"] <= idx]
        if show_fvg and fvg_df is not None and not fvg_df.empty else None
    )
    vis_sweeps = (
        sweeps_df[sweeps_df["index"] <= ts_now]
        if show_sweeps and sweeps_df is not None and not sweeps_df.empty else None
    )

    fig = render_chart(
        vis_df, signals=vis_sig, fvg_df=vis_fvg, sweeps_df=vis_sweeps,
        trade_history=engine.trade_history,
        show_ma=ss.get("ov_ma", True),
        show_rsi=ss.get("ov_rsi", True),
        show_macd=ss.get("ov_macd", False),
        show_fvg=show_fvg,
        show_sweeps=show_sweeps,
        show_signals=show_signals,
        show_trades=show_trades,
        title=f"{ss.ticker}  —  Replay",
        current_idx=idx,
    )
    st.plotly_chart(fig, width="stretch", key="replay_chart")

    m = engine.get_metrics(price_now)
    pnl_col = "#00FF88" if m["total_pnl"] >= 0 else "#FF4444"

    # Show last execution for ~10 candles so the user sees what just happened.
    action_html = ""
    if ss.last_action_idx is not None and idx - ss.last_action_idx < 10:
        action_html = (
            f" &nbsp;·&nbsp; <b style='color:#FFD700'>{ss.last_action_text}</b>"
        )

    st.markdown(
        f"<div class='status-pill'>"
        f"🎬 Candle <b>{idx + 1}/{len(df)}</b> &nbsp;·&nbsp; "
        f"Portfolio <b>₹{m['portfolio_value']:,.0f}</b> &nbsp;·&nbsp; "
        f"P&L <b style='color:{pnl_col}'>₹{m['total_pnl']:+,.0f}</b>"
        f"{action_html}"
        f"</div>",
        unsafe_allow_html=True,
    )

    ss.replay_idx = idx + 1


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # ── Brand ─────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='padding:10px 0 4px'>"
        "<span style='font-size:1.5rem;font-weight:800;color:#FAFAFA;letter-spacing:-.02em'>"
        "📈 StockSim</span><br>"
        "<span style='font-size:.72rem;color:#4A90E2;letter-spacing:.08em;"
        "text-transform:uppercase;font-weight:600'>"
        "Technical Analysis Platform</span></div>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Market & Timeframe ─────────────────────────────────────────────────
    st.markdown("<p class='sidebar-section'>Market Data</p>", unsafe_allow_html=True)

    ticker_option = st.selectbox(
        "Ticker",
        TICKER_OPTIONS,
        index=TICKER_OPTIONS.index(st.session_state.ticker_option)
               if st.session_state.ticker_option in TICKER_OPTIONS else 0,
        key="ticker_select",
        help="Choose a popular ticker or select 'Custom' to type your own.",
    )
    st.session_state.ticker_option = ticker_option

    # Show text box only for custom entry
    if ticker_option.startswith("✏️"):
        custom = st.text_input(
            "Enter ticker symbol",
            value=st.session_state.custom_ticker,
            placeholder="e.g. HDFCBANK.NS · COIN · EURUSD=X",
            key="custom_ticker_input",
        )
        st.session_state.custom_ticker = custom
        resolved_ticker = custom.strip().upper()
    else:
        resolved_ticker = _parse_ticker(ticker_option)
        st.session_state.custom_ticker = ""

    c_tf, c_per = st.columns(2)
    with c_tf:
        interval_opts = ["1d", "1h", "15m", "5m"]
        # Sync widget state BEFORE the widget renders. Otherwise the persisted
        # key value can fall out of the valid options list when defaults change
        # across releases, and Streamlit silently resets the dropdown.
        if st.session_state.get("interval_select") not in interval_opts:
            st.session_state["interval_select"] = st.session_state.interval
        interval_in = st.selectbox(
            "Timeframe",
            interval_opts,
            key="interval_select",
        )
    with c_per:
        period_opts = get_available_periods(interval_in)
        # Same sync trick: if the previously-chosen period isn't valid for the
        # new interval (e.g. "3mo" doesn't apply to "5m"), pick a sensible
        # default from the new list BEFORE the widget renders.
        if st.session_state.get("period_select") not in period_opts:
            st.session_state["period_select"] = period_opts[
                min(1, len(period_opts) - 1)
            ]
        period_in = st.selectbox(
            "Period",
            period_opts,
            key="period_select",
        )

    fetch_disabled = not resolved_ticker
    if st.button(
        "🔄  Fetch Data",
        width="stretch",
        type="primary",
        disabled=fetch_disabled,
    ):
        _load_data(resolved_ticker, period_in, interval_in)
        st.rerun()

    st.divider()

    # ── Strategy ───────────────────────────────────────────────────────────
    st.markdown("<p class='sidebar-section'>Strategy</p>", unsafe_allow_html=True)

    current_idx = STRATEGY_NAMES.index(st.session_state.strategy)
    strategy_in = st.radio(
        "Strategy",
        STRATEGY_NAMES,
        index=current_idx,
        label_visibility="collapsed",
    )

    if strategy_in != st.session_state.strategy:
        st.session_state.strategy = strategy_in
        if st.session_state.df is not None:
            st.session_state.signals = get_signals(
                st.session_state.df, strategy_in,
                fvg_df=st.session_state.fvg_df,
                sweeps_df=st.session_state.sweeps_df,
            )

    if strategy_in != "Manual Trading":
        with st.expander("How this strategy works"):
            st.markdown(get_strategy_description(strategy_in))

    st.divider()

    # ── Overlays ───────────────────────────────────────────────────────────
    st.markdown("<p class='sidebar-section'>Chart Overlays</p>", unsafe_allow_html=True)

    ov1, ov2 = st.columns(2)
    with ov1:
        show_ma     = st.toggle("MAs",     value=True,  help="SMA 20/50, EMA 20", key="ov_ma")
        show_fvg    = st.toggle("FVG",     value=False, help="Fair Value Gaps (advanced)", key="ov_fvg")
        show_signals = st.toggle(
            "Signals", value=False,
            help="Show every strategy BUY/SELL flag. Off by default — can be noisy.",
            key="ov_signals",
        )
    with ov2:
        show_rsi    = st.toggle("RSI",     value=True, key="ov_rsi")
        show_sweeps = st.toggle("Sweeps",  value=False, help="Liquidity Sweeps (advanced)", key="ov_sweeps")
        show_trades = st.toggle(
            "Trades",  value=True,
            help="Show executed BUY/SELL dots on the price chart.",
            key="ov_trades",
        )
    show_macd = st.toggle("MACD", value=False, key="ov_macd")

    st.divider()

    # ── Replay ─────────────────────────────────────────────────────────────
    st.markdown("<p class='sidebar-section'>Replay</p>", unsafe_allow_html=True)

    learning_mode = st.toggle(
        "Learning Mode",
        value=st.session_state.learning_mode,
        help="Pause at key events and quiz your trading instincts.",
    )
    st.session_state.learning_mode = learning_mode
    if learning_mode:
        st.caption("Replay pauses at signals, FVGs & sweeps to ask your decision.")

    st.divider()

    # ── Manual trade ───────────────────────────────────────────────────────
    if strategy_in == "Manual Trading" and st.session_state.data_loaded:
        st.markdown("<p class='sidebar-section'>Execute Trade</p>", unsafe_allow_html=True)
        qty = st.number_input("Shares", min_value=1, value=10, step=1)

        # Context hint so the user knows whether SELL will close a long or
        # open a short (and same for BUY covering vs opening).
        cur_h = st.session_state.engine.holdings
        if cur_h > 0:
            st.caption(f"Long **{cur_h}** sh · BUY adds to long · SELL closes/flips to short")
        elif cur_h < 0:
            st.caption(f"Short **{abs(cur_h)}** sh · BUY covers/flips to long · SELL adds to short")
        else:
            st.caption("Flat · BUY opens long · **SELL opens short**")

        t1, t2 = st.columns(2)
        with t1:
            if st.button(
                "BUY", width="stretch", type="primary",
                help="Covers any open short first, then opens/adds to long.",
            ):
                df  = st.session_state.df
                idx = min(st.session_state.replay_idx, len(df) - 1)
                res = st.session_state.engine.buy(
                    price=float(df.iloc[idx]["close"]),
                    timestamp=df.index[idx], quantity=qty, strategy="Manual",
                )
                _set_msg(res["message"], "success" if res["success"] else "error")
                st.rerun()
        with t2:
            if st.button(
                "SELL", width="stretch",
                help="Closes any open long first, then opens/adds to short.",
            ):
                df  = st.session_state.df
                idx = min(st.session_state.replay_idx, len(df) - 1)
                res = st.session_state.engine.sell(
                    price=float(df.iloc[idx]["close"]),
                    timestamp=df.index[idx], quantity=qty, strategy="Manual",
                )
                _set_msg(res["message"], "success" if res["success"] else "error")
                st.rerun()

    # ── Reset ──────────────────────────────────────────────────────────────
    if st.session_state.data_loaded:
        st.divider()
        if st.button("Reset Portfolio", width="stretch"):
            st.session_state.engine         = TradingEngine()
            st.session_state.replaying      = False
            st.session_state.learning_pause = False
            st.session_state.last_msg       = ""
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# MAIN — WELCOME SCREEN
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.data_loaded:
    _show_msg()
    st.markdown(
        """<div style='text-align:center;padding:52px 24px 32px'>
            <div style='font-size:2.8rem;margin-bottom:8px'>📈</div>
            <h1 style='color:#FAFAFA;font-weight:800;margin:0 0 8px'>
                Stock Market Simulator</h1>
            <p style='color:#6B7280;font-size:1rem;max-width:500px;margin:0 auto 32px'>
                Replay real market data candle-by-candle, test strategies, detect Smart Money
                patterns, and sharpen your trading intuition with Learning Mode.
            </p>
        </div>""",
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    for col, icon, title, sub, accent in [
        (c1, "🕯️", "Candlestick Charts",     "RSI · MACD · Moving Averages",     "#4A90E2"),
        (c2, "🧠", "Smart Money Concepts",   "Fair Value Gaps · Liquidity Sweeps","#00FF88"),
        (c3, "🤖", "Strategy Auto-Trading",  "RSI · MACD · MA · FVG · Sweep",     "#FF8C00"),
        (c4, "🎓", "Learning Mode",          "Pause · Reflect · Improve",         "#BB88FF"),
    ]:
        with col:
            st.markdown(
                f"""<div style='background:#1A1F2E;border:1px solid #252D3D;
                    border-top:3px solid {accent};border-radius:10px;
                    padding:20px 16px;text-align:center;min-height:130px;'>
                    <div style='font-size:2rem;margin-bottom:6px'>{icon}</div>
                    <div style='font-weight:700;color:#FAFAFA;font-size:.9rem;
                         margin-bottom:4px'>{title}</div>
                    <div style='font-size:.75rem;color:#6B7280'>{sub}</div>
                </div>""",
                unsafe_allow_html=True,
            )
    st.markdown(
        "<p style='text-align:center;color:#4B5563;font-size:.8rem;margin-top:20px'>"
        "← Choose a ticker in the sidebar and click <b>Fetch Data</b> to begin"
        "</p>",
        unsafe_allow_html=True,
    )
    st.stop()


# ════════════════════════════════════════════════════════════════════════════
# DATA IS LOADED — main references
# ════════════════════════════════════════════════════════════════════════════
df        = st.session_state.df
engine    = st.session_state.engine
signals   = st.session_state.signals
fvg_df    = st.session_state.fvg_df
sweeps_df = st.session_state.sweeps_df

current_price = _current_price()
metrics       = engine.get_metrics(current_price)

# ── Page header with ticker badge ─────────────────────────────────────────
h_left, h_right = st.columns([3, 1])
with h_left:
    st.markdown(
        f"<h2 style='margin:0;font-weight:700;color:#FAFAFA;letter-spacing:-.01em'>"
        f"<span style='color:#4A90E2'>{st.session_state.ticker}</span>"
        f"<span style='color:#6B7280;font-weight:500'>  ·  {st.session_state.strategy}</span>"
        f"</h2>",
        unsafe_allow_html=True,
    )
with h_right:
    idx_show  = min(st.session_state.replay_idx, len(df) - 1)
    ts_str    = df.index[idx_show].strftime("%d %b %Y")
    candle_n  = f"{idx_show + 1} / {len(df)}"
    st.markdown(
        f"<div style='text-align:right;padding-top:8px'>"
        f"<span class='ticker-badge'>{ts_str}  ·  {candle_n}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

_show_msg()

# ── Metrics row ───────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
ret_sign = "+" if metrics["total_return"] >= 0 else ""

m1.metric("Portfolio", f"₹{metrics['portfolio_value']:,.0f}",
          f"{ret_sign}{metrics['total_return']:.2f}%")
m2.metric("P&L",       f"₹{metrics['total_pnl']:+,.0f}",
          f"Unreal ₹{metrics['unrealized_pnl']:+,.0f}")
m3.metric("Win Rate",  f"{metrics['win_rate']:.1f}%",
          f"{metrics['num_trades']} trades")
if metrics["holdings"] > 0:
    holdings_label = f"+{metrics['holdings']} long"
    holdings_delta = f"Avg ₹{metrics['avg_entry_price']:.2f}"
elif metrics["holdings"] < 0:
    holdings_label = f"−{abs(metrics['holdings'])} short"
    holdings_delta = f"Avg ₹{metrics['avg_entry_price']:.2f}"
else:
    holdings_label = "0 flat"
    holdings_delta = "—"
m4.metric("Holdings", holdings_label, holdings_delta)

st.caption(
    f"Cash ₹{metrics['balance']:,.0f}  ·  "
    f"Realised ₹{metrics['total_pnl'] - metrics['unrealized_pnl']:+,.0f}  ·  "
    f"Unrealised ₹{metrics['unrealized_pnl']:+,.0f}"
)

st.divider()

# ── Replay control bar ────────────────────────────────────────────────────
# Sync the slider widget's session-state value with replay_idx BEFORE the
# widget is rendered. Without this, the fragment's idx increments don't
# reach the slider, and on the next full app rerun the stale slider value
# overwrites replay_idx — yanking the user back to the last user-set point.
desired_idx = min(st.session_state.replay_idx, len(df) - 1)
if st.session_state.get("candle_slider") != desired_idx:
    st.session_state["candle_slider"] = desired_idx

rc_slider, rc_rw, rc_play, rc_step = st.columns([4, 1, 1, 1])

with rc_slider:
    st.slider(
        "Candle position",
        min_value=10, max_value=len(df) - 1,
        key="candle_slider",
        on_change=_on_slider_change,
        label_visibility="collapsed",
    )

with rc_rw:
    if st.button("⏮", width="stretch", help="Step back 1 candle"):
        _clear_pause()
        if st.session_state.replay_idx > 10:
            st.session_state.replay_idx -= 1
        st.session_state.replaying = False
        st.rerun()

with rc_play:
    if not st.session_state.replaying:
        if st.button(
            "▶", width="stretch", type="primary",
            help="Auto-play from current candle (no reset)",
        ):
            paused_idx = _clear_pause()
            # If we were paused on an event, step past it so the fragment
            # doesn't immediately re-pause on the same candle.
            if paused_idx is not None:
                st.session_state.replay_idx = min(
                    paused_idx + 1, len(df) - 1,
                )
            # If we're at the end of data, restart from the beginning.
            if st.session_state.replay_idx >= len(df) - 1:
                st.session_state.replay_idx = min(50, len(df) - 1)
                st.session_state.engine = TradingEngine()
            st.session_state.replaying = True
            st.rerun()
    else:
        if st.button("⏸", width="stretch", help="Pause — keeps position & portfolio"):
            st.session_state.replaying = False
            st.rerun()

with rc_step:
    if st.button("⏭+1", width="stretch", help="Step one candle forward"):
        _clear_pause()
        _idx = st.session_state.replay_idx
        if _idx < len(df) - 1:
            st.session_state.replay_idx = _idx + 1
            new_idx   = st.session_state.replay_idx
            price_now = float(df.iloc[new_idx]["close"])
            ts_now    = df.index[new_idx]
            if strategy_in != "Manual Trading" and signals is not None:
                sig = signals.iloc[new_idx]
                acted, action_text = _auto_trade(
                    engine, sig, price_now, ts_now, strategy_in,
                )
                if acted:
                    st.session_state.last_action_text = action_text
                    st.session_state.last_action_idx  = new_idx
                    _set_msg(action_text, "success")
            engine.record_portfolio_value(ts_now, price_now)
        st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# CHART SECTION  — three branches: replay loop | learning pause | static
# ════════════════════════════════════════════════════════════════════════════

def _build_vis_data(idx: int):
    """Return sliced DataFrames/series up to `idx` for chart rendering."""
    vis_df     = df.iloc[: idx + 1]
    vis_sig    = signals.iloc[: idx + 1] if signals is not None else None
    vis_fvg    = (
        fvg_df[fvg_df["start_idx"] <= idx]
        if show_fvg and fvg_df is not None and not fvg_df.empty else None
    )
    vis_sweeps = (
        sweeps_df[sweeps_df["index"] <= df.index[idx]]
        if show_sweeps and sweeps_df is not None and not sweeps_df.empty else None
    )
    return vis_df, vis_sig, vis_fvg, vis_sweeps


# ── BRANCH 1: Auto-replay (drives the module-level _replay_tick fragment) ─
if st.session_state.replaying:
    _replay_tick()


# ── BRANCH 2: Learning Mode pause ─────────────────────────────────────────
elif st.session_state.learning_pause and st.session_state.learning_event:
    event = st.session_state.learning_event
    kind  = event.get("kind", "signal")
    idx   = event.get("idx", 0)

    # ── Event badge & header ──────────────────────────────────────────────
    badge_map = {
        "signal": ("badge-buy" if event.get("signal") == "BUY" else "badge-sell",
                   f"{'🟢 BUY' if event.get('signal')=='BUY' else '🔴 SELL'} Signal — {st.session_state.strategy}"),
        "fvg":    ("badge-fvg",   f"{'🟩 Bullish' if event.get('fvg_type')=='bullish' else '🟥 Bearish'} Fair Value Gap"),
        "sweep":  ("badge-sweep", f"{'🔶 Buy-Side' if event.get('sweep_type')=='buy_side' else '🔷 Sell-Side'} Liquidity Sweep"),
    }
    badge_cls, badge_txt = badge_map.get(kind, ("badge-hold", "Event"))

    st.markdown(
        f"<div class='lp-outer'><div class='lp-header'>"
        f"<span style='font-size:1.1rem;font-weight:800;color:#FAFAFA'>🎓 Learning Moment</span>"
        f"<span class='lp-badge {badge_cls}'>{badge_txt}</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # ── Two-column layout: Chart (left) | Context + Interaction (right) ──
    lc, rc = st.columns([3, 2], gap="medium")

    with lc:
        st.markdown(
            "<p style='font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;"
            "color:#4A90E2;font-weight:700;margin-bottom:4px'>📍 Signal Chart</p>",
            unsafe_allow_html=True,
        )
        sig_fig = render_signal_chart(df, event, window=30, show_ma=show_ma)
        st.plotly_chart(sig_fig, width="stretch", config={"displayModeBar": False})

        # Indicator snapshot under the chart
        snap = _get_indicator_snapshot(idx)
        ic1, ic2, ic3 = st.columns(3)
        rsi_color = "#00FF88" if snap["rsi"] < 40 else "#FF4444" if snap["rsi"] > 60 else "#AAAAAA"
        macd_cross = "▲ Bullish" if snap["macd"] > snap["macd_signal"] else "▼ Bearish"
        mc_color   = "#00FF88" if snap["macd"] > snap["macd_signal"] else "#FF4444"
        price_vs_sma = "Above" if snap["close"] > snap["sma_20"] else "Below"
        pvsma_col    = "#00FF88" if price_vs_sma == "Above" else "#FF4444"

        ic1.markdown(
            f"<div style='text-align:center;background:#1A1F2E;border-radius:8px;padding:8px'>"
            f"<div style='font-size:.65rem;color:#6B7280;text-transform:uppercase'>RSI (14)</div>"
            f"<div style='font-size:1.1rem;font-weight:700;color:{rsi_color}'>{snap['rsi']}</div>"
            f"</div>", unsafe_allow_html=True,
        )
        ic2.markdown(
            f"<div style='text-align:center;background:#1A1F2E;border-radius:8px;padding:8px'>"
            f"<div style='font-size:.65rem;color:#6B7280;text-transform:uppercase'>MACD</div>"
            f"<div style='font-size:1.1rem;font-weight:700;color:{mc_color}'>{macd_cross}</div>"
            f"</div>", unsafe_allow_html=True,
        )
        ic3.markdown(
            f"<div style='text-align:center;background:#1A1F2E;border-radius:8px;padding:8px'>"
            f"<div style='font-size:.65rem;color:#6B7280;text-transform:uppercase'>vs SMA 20</div>"
            f"<div style='font-size:1.1rem;font-weight:700;color:{pvsma_col}'>{price_vs_sma}</div>"
            f"</div>", unsafe_allow_html=True,
        )

    with rc:
        # ── Context explanation ───────────────────────────────────────────
        st.markdown(
            "<p style='font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;"
            "color:#4A90E2;font-weight:700;margin-bottom:6px'>📖 Context</p>",
            unsafe_allow_html=True,
        )

        if kind == "signal":
            sig   = event["signal"]
            clr   = "#00FF88" if sig == "BUY" else "#FF4444"
            arrow = "↑" if sig == "BUY" else "↓"
            st.markdown(
                f"<div style='background:#1A1F2E;border-left:3px solid {clr};"
                f"border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px'>"
                f"<span style='color:{clr};font-weight:700;font-size:1rem'>{arrow} {sig} Signal</span><br>"
                f"<span style='color:#AAAAAA;font-size:.82rem'>"
                f"Strategy: <b style='color:#FAFAFA'>{st.session_state.strategy}</b><br>"
                f"Price: <b style='color:{clr}'>₹{event['price']:.2f}</b>"
                f"</span></div>",
                unsafe_allow_html=True,
            )
            st.markdown(get_strategy_description(st.session_state.strategy))

        elif kind == "fvg":
            ft  = event["fvg_type"]
            clr = "#00FF88" if ft == "bullish" else "#FF4444"
            st.markdown(
                f"<div style='background:#1A1F2E;border-left:3px solid {clr};"
                f"border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px'>"
                f"<span style='color:{clr};font-weight:700;font-size:.95rem'>"
                f"{'🟩 Bullish' if ft=='bullish' else '🟥 Bearish'} FVG</span><br>"
                f"<span style='color:#AAAAAA;font-size:.82rem'>"
                f"Zone: <b style='color:{clr}'>₹{event['bottom']:.2f} – ₹{event['top']:.2f}</b><br>"
                f"Price: <b>₹{event['price']:.2f}</b>"
                f"</span></div>",
                unsafe_allow_html=True,
            )
            st.info(FVG_EXPLANATION[ft])

        elif kind == "sweep":
            st_type = event["sweep_type"]
            clr     = "#FF8C00" if st_type == "buy_side" else "#BB88FF"
            label   = "Buy-Side Sweep" if st_type == "buy_side" else "Sell-Side Sweep"
            st.markdown(
                f"<div style='background:#1A1F2E;border-left:3px solid {clr};"
                f"border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px'>"
                f"<span style='color:{clr};font-weight:700;font-size:.95rem'>{label}</span><br>"
                f"<span style='color:#AAAAAA;font-size:.82rem'>"
                f"Wick: <b style='color:{clr}'>₹{event['price']:.2f}</b> · "
                f"Swept Level: <b>₹{event['swept_level']:.2f}</b>"
                f"</span></div>",
                unsafe_allow_html=True,
            )
            st.info(SWEEP_EXPLANATION[st_type])

        st.divider()

        # ── Decision widget ───────────────────────────────────────────────
        st.markdown(
            "<p style='font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;"
            "color:#4A90E2;font-weight:700;margin-bottom:6px'>🤔 Your Decision</p>",
            unsafe_allow_html=True,
        )
        decision = st.radio(
            "decision",
            ["🟢  BUY  — Enter long", "🔴  SELL — Exit / short", "🟡  HOLD — Wait & watch"],
            label_visibility="collapsed",
            key="learning_choice",
        )

        d1, d2 = st.columns(2)
        with d1:
            if st.button("🔍 Show Outcome", width="stretch"):
                st.session_state.show_outcome  = True
                st.session_state.user_decision = decision

        # ── Outcome ───────────────────────────────────────────────────────
        if st.session_state.show_outcome:
            future_n = min(5, len(df) - idx - 2)
            if future_n > 0:
                p0  = float(df.iloc[idx]["close"])
                p1  = float(df.iloc[idx + future_n]["close"])
                pct = (p1 - p0) / p0 * 100
                oc  = "#00FF88" if pct >= 0 else "#FF4444"

                best   = "BUY" if pct >= 0 else "SELL"
                chose  = ("BUY"  if "BUY"  in (st.session_state.user_decision or "") else
                          "SELL" if "SELL" in (st.session_state.user_decision or "") else "HOLD")
                correct = chose == best

                outcome_lines = [
                    f"Next {future_n} candles: "
                    f"<span style='color:{oc};font-weight:700'>{pct:+.2f}%</span> "
                    f"(₹{p0:.2f} → ₹{p1:.2f})",
                    f"Best action: <b>{best}</b>",
                    f"Your call: <b>{chose}</b> {'✅' if correct else '❌'}",
                ]
                if kind == "signal":
                    strat_sig = event["signal"]
                    outcome_lines.append(
                        f"Strategy: <b>{strat_sig}</b> "
                        f"{'✅' if strat_sig == best else '❌'}"
                    )

                st.markdown(
                    "<div class='outcome-card'>"
                    + "<br>".join(f"<span style='font-size:.83rem;color:#AAAAAA'>{l}</span>"
                                  for l in outcome_lines)
                    + "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Not enough future candles to evaluate.")

        with d2:
            if st.button("▶ Continue", width="stretch", type="primary"):
                pn = event["price"]
                ts = event["timestamp"]
                paused_idx = event.get("idx", st.session_state.replay_idx)

                # Translate the event into an inferred BUY/SELL for the
                # current strategy so the engine actually trades it.
                inferred = None
                if kind == "signal":
                    inferred = event["signal"]
                elif kind == "fvg":
                    inferred = "BUY" if event["fvg_type"] == "bullish" else "SELL"
                elif kind == "sweep":
                    inferred = "SELL" if event["sweep_type"] == "buy_side" else "BUY"

                if inferred is not None:
                    acted, action_text = _auto_trade(
                        engine, inferred, pn, ts, strategy_in,
                    )
                    if acted:
                        st.session_state.last_action_text = action_text
                        st.session_state.last_action_idx  = paused_idx

                engine.record_portfolio_value(ts, pn)
                # Advance past the paused candle so the fragment doesn't
                # immediately re-trigger on the same event.
                st.session_state.replay_idx = min(paused_idx + 1, len(df) - 1)
                st.session_state.update(
                    learning_pause=False, show_outcome=False,
                    learning_event=None, replaying=True,
                )
                st.rerun()


# ── BRANCH 3: Static chart ────────────────────────────────────────────────
else:
    idx = min(st.session_state.replay_idx, len(df) - 1)
    vis_df, vis_sig, vis_fvg, vis_sweeps = _build_vis_data(idx)
    fig = render_chart(
        vis_df, signals=vis_sig, fvg_df=vis_fvg, sweeps_df=vis_sweeps,
        trade_history=engine.trade_history,
        show_ma=show_ma, show_rsi=show_rsi, show_macd=show_macd,
        show_fvg=show_fvg, show_sweeps=show_sweeps,
        show_signals=show_signals, show_trades=show_trades,
        title=f"{st.session_state.ticker}  —  {st.session_state.strategy}",
    )
    st.plotly_chart(fig, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# BOTTOM TABS
# ════════════════════════════════════════════════════════════════════════════
st.divider()
tab_perf, tab_trades, tab_smc = st.tabs([
    "Performance",
    "Trade History",
    "SMC Analysis",
])

# ── Performance ───────────────────────────────────────────────────────────
with tab_perf:
    perf = calculate_performance_metrics(
        engine.trade_history, engine.portfolio_history, initial_capital=100_000.0,
    )
    pa, pb, pc, pd_ = st.columns(4)
    pa.metric("Total Return",   f"{perf['total_return']:+.2f}%")
    pb.metric("Net P&L",        f"₹{perf['total_pnl']:+,.0f}")
    pc.metric("Win Rate",       f"{perf['win_rate']:.1f}%")
    pd_.metric("Profit Factor",
               f"{perf['profit_factor']:.2f}" if perf["profit_factor"] != float("inf") else "∞")

    pf_str = (
        f"Max Drawdown {perf['max_drawdown']:.2f}%  ·  "
        f"Sharpe {perf['sharpe_ratio']:.2f}  ·  "
        f"Best ₹{perf['best_trade']:+,.0f}  ·  "
        f"Worst ₹{perf['worst_trade']:+,.0f}"
    )
    st.caption(pf_str)

    if engine.portfolio_history:
        st.plotly_chart(render_equity_curve(engine.portfolio_history),
                        width="stretch")
    else:
        st.info("Start Auto Play to build the equity curve.")

    strat_df = summarise_by_strategy(engine.trade_history)
    if not strat_df.empty:
        st.markdown("##### Per-strategy breakdown")
        st.dataframe(strat_df, hide_index=True, width="stretch")

# ── Trade History ─────────────────────────────────────────────────────────
with tab_trades:
    if engine.trade_history:
        rows = []
        for t in engine.trade_history:
            ts_str = (
                t.timestamp.strftime("%Y-%m-%d %H:%M")
                if hasattr(t.timestamp, "strftime") else str(t.timestamp)
            )
            rows.append({
                "Time":     ts_str,
                "Action":   t.action,
                "Price":    round(t.price, 2),
                "Qty":      t.quantity,
                "Value":    round(t.total_value, 2),
                "P&L":      round(t.pnl, 2) if t.action in ("SELL", "COVER") else None,
                "Strategy": t.strategy,
            })
        st.dataframe(
            pd.DataFrame(rows),
            width="stretch", hide_index=True,
            column_config={
                "Action": st.column_config.TextColumn("Action",    width="small"),
                "P&L":    st.column_config.NumberColumn("P&L (₹)", format="%.2f"),
                "Price":  st.column_config.NumberColumn("Price (₹)", format="%.2f"),
                "Value":  st.column_config.NumberColumn("Value (₹)", format="%.0f"),
            },
        )
        closed_pnl = sum(t.pnl for t in engine.trade_history if t.action in ("SELL", "COVER"))
        st.caption(
            f"Total trades: {len(engine.trade_history)}  ·  "
            f"Closed P&L: ₹{closed_pnl:+,.2f}"
        )
    else:
        st.info("No trades yet. Use the sidebar or start a strategy replay.")

# ── SMC Analysis ──────────────────────────────────────────────────────────
with tab_smc:
    idx_now   = min(st.session_state.replay_idx, len(df) - 1)
    sc1, sc2  = st.columns(2)

    with sc1:
        st.markdown("#### Fair Value Gaps")
        if fvg_df is not None and not fvg_df.empty:
            vis = fvg_df[fvg_df["start_idx"] <= idx_now].copy()
            if not vis.empty:
                vis["Zone"] = vis.apply(lambda r: f"₹{r['bottom']:.2f} – ₹{r['top']:.2f}", axis=1)
                vis["Type"] = vis["type"].str.capitalize()
                vis["Time"] = vis["index"].apply(
                    lambda x: x.strftime("%Y-%m-%d %H:%M") if hasattr(x, "strftime") else str(x)
                )
                st.dataframe(vis[["Time", "Type", "Zone"]],
                             width="stretch", hide_index=True)
                bull = (vis["type"] == "bullish").sum()
                bear = (vis["type"] == "bearish").sum()
                st.caption(f"🟢 Bullish: {bull}  ·  🔴 Bearish: {bear}")
            else:
                st.info("No FVGs in the visible range.")
        else:
            st.info("No FVGs detected.")

        with st.expander("What is a Fair Value Gap?"):
            st.markdown(FVG_EXPLANATION["bullish"])
            st.markdown("---")
            st.markdown(FVG_EXPLANATION["bearish"])

    with sc2:
        st.markdown("#### Liquidity Sweeps")
        if sweeps_df is not None and not sweeps_df.empty:
            vis = sweeps_df[sweeps_df["index"] <= df.index[idx_now]].copy()
            if not vis.empty:
                vis["Direction"]   = vis["type"].map({"buy_side": "Buy-Side", "sell_side": "Sell-Side"})
                vis["Wick"]        = vis["wick_price"].apply(lambda x: f"₹{x:.2f}")
                vis["Swept Level"] = vis["swept_level"].apply(lambda x: f"₹{x:.2f}")
                vis["Time"]        = vis["index"].apply(
                    lambda x: x.strftime("%Y-%m-%d %H:%M") if hasattr(x, "strftime") else str(x)
                )
                st.dataframe(vis[["Time", "Direction", "Wick", "Swept Level"]],
                             width="stretch", hide_index=True)
                bs = (vis["type"] == "buy_side").sum()
                ss = (vis["type"] == "sell_side").sum()
                st.caption(f"🔶 Buy-Side: {bs}  ·  🔷 Sell-Side: {ss}")
            else:
                st.info("No sweeps in the visible range.")
        else:
            st.info("No liquidity sweeps detected.")

        with st.expander("What is a Liquidity Sweep?"):
            st.markdown(SWEEP_EXPLANATION["buy_side"])
            st.markdown("---")
            st.markdown(SWEEP_EXPLANATION["sell_side"])
