# AGENTS.md

## What This Is

Personal stock backtesting project for Chinese A-shares (and some HK). Flat directory, no packaging, no CI, no formal test suite. Scripts are run directly.

## Core Scripts

- **`fast_macd3.4.py`** — Main MACD strategy (backtrader + akshare). The authoritative version of the strategy.
- **`fast_macd3.4_ai.py`** — AI-variant strategy. This is what `backtest_server.py` runs.
- **`fast_macd3.4_all_stock.py`** — Batch runner across multiple stocks.
- **`fast_macd3.4_one.py`** — Single-stock runner.
- **`backtest_server.py`** — HTTP server (port 18765) that spawns `fast_macd3.4_ai.py` as subprocess.

## Dependencies

Core: `backtrader`, `akshare`, `pandas`, `matplotlib`. Email alerts via `send_email.py`.

## Python Environment

Conda env `backtrader` at:
```
D:\Users\lzl_k\anaconda3\envs\backtrader\python.exe
```
Override with env var `BACKTEST_PYTHON`.

## How to Run

```bash
# Single stock with custom date range
python fast_macd3.4.py --start_date 20240101 --end_date 20250101

# Batch from file
python fast_macd3.4_all_stock.py -f stocks.csv -s 20240101

# Start the backtest server
python backtest_server.py
# GET http://localhost:18765/run?start_date=20220101
```

Stock file format: `code,name` per line (e.g. `sz300568,星源材质`). UTF-8 with BOM is handled.

## Key Gotchas

- **No linter, formatter, or typecheck.** No pre-commit hooks.
- **`time.sleep(10)`** in the main loop of `fast_macd3.4.py` — intentional rate-limiting for akshare API calls. Don't remove.
- **`send_email.py`** contains a hardcoded SMTP password (`ylnclfzmrzjpbbbi`). Do not commit additional secrets.
- **`openclaw.json`** has API keys for Moonshot, ModelScope, Google, LongCat. Do not expose or commit changes to these values.
- Stock data is fetched live from akshare — scripts fail without internet. CSV files in root are cached stock lists, not strategy inputs.
- Strategy versions (3.1→3.5) are separate files, not branches. Changes to `fast_macd3.4.py` are the live version.
- `PrintAnalyzer.py` is imported via `from PrintAnalyzer import *` in strategy files.

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
vectorbt/                 — Alternative vectorbt-based strategies
testing/                  — Experimental/scratch scripts (not tests)
data/                     — Stock CSV data
learn_backtrader-master/  — Tutorial reference (not production code)
```

## Conventions

- Comments and log messages are in Chinese (Mandarin).
- Stock codes use akshare prefix format: `sz300568`, `sh600580`.
- All output goes to stdout; logs are to `server.log` (for the server).
