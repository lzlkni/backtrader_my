# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Rules

- **Plan before acting.** For any non-trivial change, explore the relevant code, lay out a plan covering what needs to change and why, and wait for user approval before writing code. Do not jump straight to implementation.

## Project Overview

Personal stock backtesting project for Chinese A-shares (and some HK). Flat directory, no packaging, no CI, no formal test suite. Scripts are run directly with `python`. Comments and log messages are in Chinese (Mandarin).

## Python Environment

Conda env `backtrader`:
```
D:\Users\lzl_k\anaconda3\envs\backtrader\python.exe
```
Override with env var `BACKTEST_PYTHON`.

## Common Commands
./
```bash
# Single stock with custom date range
python fast_macd3.4.py --start_date 20240101 --end_date 20250101

# Batch from file
python fast_macd3.4_all_stock.py -f stocks.csv -s 20240101

# Start the backtest server (spawns fast_macd3.4_ai.py as subprocess)
python backtest_server.py
# GET http://localhost:18765/run?start_date=20220101

# AI-variant strategy (outputs JSON to stdout)
python fast_macd3.4_ai.py --start_date 20220101

# Single stock runner
python fast_macd3.4_one.py
```

Stock file format: `code,name` per line (e.g. `sz300568,星源材质`). UTF-8 with BOM is handled.

## Architecture

### Strategy Pattern

All strategies follow the same structure — custom `bt.Indicator` subclasses composed into a `bt.Strategy`:

- **`FastMACD`** — Double-smoothed MACD (EMA-of-EMA fast/slow, double-smoothed signal). Adds `macd_highest` line (120-period Highest) used for threshold comparison.
- **`InOutLine`** — Tracks `lowest` (12-period Lowest of close) and `upper` (lowest × 1.5). Used for dynamic stop-loss / take-profit calculation.
- **`UpCrossSignal`** — Wraps `bt.indicators.CrossOver(FastMACD.macd, FastMACD.signal)`. Outputs +1 on bullish cross (buy signal).
- **`fast_macd_strtgy`** — Main strategy: buys on bullish MACD cross when signal > 0; sells when close hits upper (profit target) or lower (stop-loss) band. Stop/target are dynamic — recalculated at buy time using `calculate_stop_loss_target()`, which scales the band width by `std_scale = (price - lowest) * 1.5` and selects multiplier based on where current MACD sits relative to its 120-day high.

Strategy files share a common layout: indicator classes → strategy class with `next()`/`notify_order()`/`notify_trade()` → `load_stocks_from_file()` → `main()` argparse entrypoint.

### Strategy Variants

- **`fast_macd_base.py`** — Earliest version (pre-3.x naming). Uses global `stock`/`stock_name` variables. Imported by early scripts.
- **`fast_macd3.4.py`** — Authoritative main strategy. Passes `stock_code`/`stock_name` as strategy params (not globals). Includes `calculate_stop_loss_target()` method.
- **`fast_macd3.4_ai.py`** — AI-variant. Adds hot-concept board scraping via EastMoney HTTP API (avoids akshare SSL issues). Outputs JSON to stdout — designed for programmatic consumption.
- **`fast_macd3.4_all_stock.py`** — Batch runner. Loads stocks from CSV, iterates with 10s sleep between each (rate-limit for akshare).
- **`fast_macd3.4_one.py`** — Single-stock runner.
- **`fast_macd3.4_hk.py`** — HK market variant.
- **`fast_macd3.5.py`** — Newest version (work in progress).

All variants copy the indicator classes inline — each file is self-contained, not imported from a shared module.

### Analyzer Setup

Standard analyzer stack added in `main()`:
```python
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02, annualize=True, timeframe=bt.TimeFrame.Days)
cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
cerebro.addanalyzer(bt.analyzers.Transactions, _name='txn')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual_return')
cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='time_return')
```

Results are printed via `PrintAnalyzer.printTradeAnalysis()` (imported with `from PrintAnalyzer import *`).

### Data Flow

```
akshare.stock_zh_a_daily(symbol=code, adjust="qfq")  →  pandas DataFrame (6 cols: date/open/high/low/close/volume)
    → bt.feeds.PandasData
    → bt.Cerebro.adddata + addstrategy
    → cerebro.run()
    → analyzers → printTradeAnalysis()
```

### Server Mode

`backtest_server.py` is an HTTP server (port 18765) that spawns `fast_macd3.4_ai.py` as a subprocess per request. It injects `conda/Library/bin` into PATH to fix SSL DLL loading. Logs go to `server.log`.

## Key Gotchas

- **No linter, formatter, or typecheck.** No pre-commit hooks.
- **`time.sleep(10)`** in batch loops — intentional rate-limiting for akshare API calls. Don't remove.
- **`send_email.py`** contains a hardcoded SMTP password (`ylnclfzmrzjpbbbi`). Do not commit additional secrets.
- **`openclaw.json`** (if present) has API keys for Moonshot, ModelScope, Google, LongCat. Do not expose.
- Stock data is fetched live from akshare — scripts fail without internet. CSV files in root are cached stock lists, not strategy inputs.
- Strategy versions (3.1→3.5) are separate files, not branches. Changes to `fast_macd3.4.py` are the live version.
- `PrintAnalyzer.py` is imported via `from PrintAnalyzer import *` in strategy files.
- Stock codes use akshare prefix format: `sz300568`, `sh600580`. The `load_stocks_from_file()` function expects this format.
- `InOutLine.upper` calculation differs between files: `fast_macd_base.py` and `fast_macd3.4_all_stock.py` use `lowest * 1.5`; `fast_macd3.4.py` uses `bt.ind.Highest(period=12)`. This is intentional divergence between versions.
- `fast_macd3.4_ai.py` uses lazy imports (heavy libs imported inside functions) for faster startup when called as subprocess.

## Directory Map

```
fast_macd3.*.py           — Strategy versions (3.1–3.5, variants)
backtest_server.py        — HTTP API server
common/                   — Shared utilities imported by strategy files
  ├── send_email.py           — Email notification helper (SMTP)
  ├── PrintAnalyzer.py        — Trade analysis output formatting
  ├── helpper.py              — akshare concept board scraper
  ├── stock_list*.py          — Stock list utilities (A-shares, HK, BK)
  └── eastmoney_boards.py     — EastMoney board scraper
stock_data_gethoring.py   — Data gathering
testing/                  — Experimental/scratch scripts (not tests)
docker_image/             — ARM64 Docker setup for scheduled runs
```
