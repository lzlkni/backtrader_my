# AGENTS.md

## 工作规则

- **先计划后动手。** 所有改动必须有 plan，包含目标、范围、步骤，经确认后才执行。临时程序或非回测的小脚本例外，无需 plan。
- **记录执行情况。** 完成后回填结果（成功/失败、关键输出、偏差说明），plan 作为永久记录保留。临时程序无需记录。
- **策略改动必须回测。** 修改后用默认股票列表跑一轮，结果记入 `results/version_comparison.html`。
- **对比历史版本。** 相同股票列表和日期范围做对比。

## 项目简介

A 股回测项目，`backtrader` + `akshare`。无 CI/linter/测试框架，策略文件自包含。注释和日志为中文。

## Python 环境

- **主要**: conda `backtrader` — `D:\Users\lzl_k\anaconda3\envs\backtrader\python.exe`
- **备用**: `D:\Users\lzl_k\AppData\Local\Programs\Python\Python312\venvs\backtrader\python.exe`
- 覆盖: env var `BACKTEST_PYTHON`

## 目录结构（精简）

- `strategies/` — 主线策略族 (base → 3.5)
- `versions/` — 退出管理迭代（v5 为推荐版本: +42.22%, 81%胜率, Sharpe 1.03）
- `variants/` — AI 变体 + 一次性实验
- `scripts/` — 选股（screen_stocks_for_v5.py）、报告生成、辅助脚本
- `common/` — PrintAnalyzer、send_email
- `results/` — HTML/CSV 报告和对比表
- `data/` — 数据文件、筛选结果
- `Input_stock_list/` — 输入股票列表

## 公共导入模式

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
from PrintAnalyzer import *
```

## v5 importlib 模式（文件名含小数点时使用）

```python
import importlib.util
_v5_path = os.path.join(PROJECT_DIR, 'versions', 'fast_macd3.4_v5.py')
_v5_spec = importlib.util.spec_from_file_location('fast_macd3_4_v5', _v5_path)
_v5_mod = importlib.util.module_from_spec(_v5_spec)
sys.modules['fast_macd3_4_v5'] = _v5_mod
_v5_spec.loader.exec_module(_v5_mod)
fast_macd_strtgy = _v5_mod.fast_macd_strtgy
```

## 常用命令

```bash
# 回测
python strategies/fast_macd3.4.py --start_date 20240101 --end_date 20250101
python variants/fast_macd3.4_all_stock.py -f <stock_file> -s 20240101

# AI 变体
python variants/fast_macd3.4_ai.py --start_date 20220101
python variants/fast_macd3.4_ai2.py --sweep -s 20240101 -e 20250610

# 选股（screen_stocks_for_v5.py 使用备用 Python 路径，见脚本顶部 PYTHON_EXE）
python scripts/screen_stocks_for_v5.py --top 200 -s 20240101 -e 20250610

# 股票画像
python v5_stock_profiler.py -f Input_stock_list/<file>.txt
```

股票文件格式: `code,name`（如 `sz300568,星源材质`），akshare 前缀格式。

## 关键注意事项

- 无 linter / CI。`time.sleep(10)` 在 `fast_macd3.4_all_stock.py` 中 — 勿删（akshare 限速）。
- `send_email.py` 和 `openclaw.json` 含敏感密钥，切勿泄露/提交。
- 所有数据实时从 akshare 获取，无网络则失败。
- **v5 为推荐基线**（`versions/fast_macd3.4_v5.py`）。
- `scripts/screen_stocks_for_v5.py` 使用备用 Python 环境（见脚本顶部 `PYTHON_EXE`）。
