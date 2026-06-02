# TradingSimTALP

A candle-by-candle stock market replay simulator and technical-analysis learning platform, built in Python with Streamlit and Plotly. Pull real OHLC data for any ticker, replay it tick-by-tick, paper-trade five different strategies, detect Smart Money Concepts (Fair Value Gaps and Liquidity Sweeps), and sharpen your intuition with a Learning Mode that pauses on every signal and asks you to call the next move before revealing the outcome.

![Streamlit](https://img.shields.io/badge/Streamlit-1.37+-FF4B4B?logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-5.18+-3F4F75?logo=plotly&logoColor=white)

---

## Features

### Replay engine
- Candle-by-candle playback of real market data fetched from Yahoo Finance.
- **Play / Pause / ⏮ Step back / ⏭ Step forward** controls plus a draggable candle slider — every control preserves your position and portfolio.
- Adjustable tick rate (~0.25 s/candle) tuned so Pause registers within a quarter-second.
- Works on stocks (US + Indian NSE), ETFs, and crypto.

### Trading
- **Long and short** paper trading with a single signed-holdings position model.
- BUY auto-covers any open short before opening a long; SELL auto-closes any open long before opening a short — flips are recorded as two separate trades for clarity.
- ₹100,000 starting capital, cash-collateral margin proxy (no over-leverage).
- Realized + unrealized P&L, win rate, profit factor, Sharpe, max drawdown, equity curve.

### Strategies (auto-trade or manual)
| Name | Logic |
|---|---|
| **Manual Trading** | You click BUY / SELL — long and short both supported. |
| **RSI Strategy** | BUY at oversold cross (<30), SELL at overbought cross (>70). |
| **MACD Strategy** | BUY on MACD/Signal bullish cross, SELL on bearish cross. |
| **MA Crossover** | Golden Cross (SMA20>SMA50) BUY, Death Cross SELL. |
| **FVG Strategy** | BUY one bar after a bullish Fair Value Gap completes; SELL after a bearish FVG. |
| **Liquidity Sweep** | BUY after a sell-side stop-hunt; SELL after a buy-side stop-hunt. |

Auto-strategies are **always in the market** — every signal flips you between long and short.

### Smart Money Concepts
- **Fair Value Gaps (FVG)** — 3-candle imbalance detection; bullish gaps acting as support, bearish gaps acting as resistance, with auto-fading of filled zones.
- **Liquidity Sweeps** — wicks beyond prior swing highs/lows that close back inside, surfacing stop-hunt reversals.

### Learning Mode
- Replay pauses at every BUY/SELL signal, FVG completion, and liquidity sweep.
- A zoomed event chart highlights the trigger candles (e.g. **C1 / C2 / C3** for FVGs) so you know exactly what to look at.
- You pick BUY / SELL / HOLD, click **Show Outcome** to see what the next 5 candles did, then **Continue** to resume — your call is graded against the strategy's call and the actual move.

### Chart
- Candlestick + SMA 20 / 50, EMA 20, RSI (14), MACD (12,26,9).
- Toggle every overlay independently: MAs, RSI, MACD, FVG zones, sweep markers, raw signal triangles, executed-trade dots.
- Executed trades render as inline green/red dots on the candle close, with hover tooltips showing the exact action (`BUY` / `SELL` / `SHORT` / `COVER`).

---

## Quick start

```bash
git clone <repo-url>
cd stock_simulator
pip install -r requirements.txt
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501), pick a ticker from the sidebar (or type your own), choose a timeframe + period, hit **Fetch Data**, and press ▶ to start the replay.

### Yahoo Finance timeframe limits

| Timeframe | Max history |
|---|---|
| `1m` | 7 days |
| `5m`, `15m`, `30m` | 60 days |
| `1h` | 730 days |
| `1d`, `1wk` | unlimited |

The Period dropdown only offers combinations Yahoo actually supports — pick a longer interval if you want more history.

---

## Project structure

```
stock_simulator/
├── app.py                       # Streamlit entry point — UI, sidebar, replay controls
├── requirements.txt
└── modules/
    ├── data_fetcher.py          # yfinance wrapper + period validation
    ├── indicators.py            # SMA / EMA / RSI / MACD via `ta`
    ├── strategies.py            # 5 BUY/SELL signal generators + dispatcher
    ├── smc_detector.py          # FVG + Liquidity Sweep detection
    ├── trading_engine.py        # Signed-holdings paper engine (long + short)
    ├── chart_renderer.py        # Plotly candlestick + overlays + event chart
    └── performance.py           # Win rate, drawdown, Sharpe, Calmar, profit factor
```

---

## How it works

1. **Fetch** — `data_fetcher.fetch_data()` pulls OHLCV from Yahoo, drops zero-volume candles, strips timezone for Plotly.
2. **Indicators** — `indicators.calculate_all_indicators()` annotates the dataframe with SMA/EMA/RSI/MACD columns.
3. **SMC detection** — `smc_detector` scans the bars and emits `fvg_df` and `sweeps_df` once, upfront.
4. **Signals** — `strategies.get_signals()` returns a per-bar `BUY`/`SELL`/`HOLD` series for the chosen strategy.
5. **Replay loop** — a Streamlit fragment ticks `replay_idx` forward every 250 ms, calls the auto-trader, records portfolio value, re-renders the chart slice up to the current candle.
6. **Pause / Continue** — the fragment yields whenever `replaying=False`, and the Learning Mode panel takes over with a focused chart + decision UI.

---

## Tech stack

- **[Streamlit](https://streamlit.io/)** — UI, session state, fragments for the replay loop.
- **[yfinance](https://pypi.org/project/yfinance/)** — market data.
- **[pandas](https://pandas.pydata.org/) / [numpy](https://numpy.org/)** — data wrangling and metrics.
- **[Plotly](https://plotly.com/python/)** — candlesticks, subplots, equity curves.
- **[ta](https://github.com/bukosabino/ta)** — technical indicator library.

---

## Notes & caveats

- This is a **paper-trading sandbox for learning**, not a live trading platform. No brokerage integration, no real money.
- Margin for shorts is a 100% cash-collateral proxy — real brokers use Reg-T / SPAN. Don't extrapolate position sizing to live markets.
- All prices display in ₹ for consistency with INR-denominated NSE tickers; USD tickers display the same symbol but values are in their native currency.
- Yahoo Finance occasionally rate-limits or returns stale data. If a fetch fails, retry after a few seconds.

---

## License

MIT — do whatever you want, no warranty.
