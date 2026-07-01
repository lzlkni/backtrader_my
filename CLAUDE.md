# CLAUDE.md

本文件为 Claude Code 提供仓库操作指引。

## 工作规则

- **先计划后动手。** 任何非平凡修改，先探索相关代码、制定计划并等待用户批准，再写代码。
- **计划必须保存。** 每次计划写入 `C:\Users\lzl_k\.claude\plans\<name>.md`，完成后标记完成。计划是变更的永久记录。
- **策略改动必须完整回测。** 每次修改指标、止盈止损、过滤器、参数逻辑后，用默认股票列表跑完整一轮回测并记录结果。
- **对比历史版本。** 新版本必须与之前所有版本对比，用相同股票列表和日期范围。结果记录到 `results/version_comparison.html` 或其他对比文件。

## 项目简介

个人 A 股（少量港股）回测项目。使用 `backtrader` + `akshare`。子目录结构：strategies/versions/variants/scripts/common。无测试框架、无 CI。每个策略文件自包含（指标类内联复制）。注释和日志均为中文。

## Python 环境

Conda env `backtrader`：
```
D:\Users\lzl_k\anaconda3\envs\backtrader\python.exe
```
覆盖：`BACKTEST_PYTHON` 环境变量。
注意 `scripts/screen_stocks_for_v5.py` 在文件顶部通过 `PYTHON_EXE` 使用不同的 Python 路径（`Python312\venvs\backtrader\`）。

## 常用命令

```bash
# 单股自定义日期
python strategies/fast_macd3.4.py --start_date 20240101 --end_date 20250101

# 从股票列表批量运行
python variants/fast_macd3.4_all_stock.py -f Input_stock_list/deepseek_csv_20260621_3c2bb1.txt -s 20240101

# AI 变体（JSON 标准输出）
python variants/fast_macd3.4_ai.py --start_date 20220101

# 单股快速回测
python variants/fast_macd3.4_one.py

# V5 全市场选股（见脚本顶部的 PYTHON_EXE 路径）
python scripts/screen_stocks_for_v5.py --top 200 -s 20240101 -e 20250610
```

股票文件格式：`code,name` 每行（如 `sz300568,星源材质`）。自动处理 UTF-8 with BOM。

## 架构

### 策略模式

所有策略遵循相同结构 — 自定义 `bt.Indicator` 子类组合成 `bt.Strategy`：

- **`FastMACD`** — 双平滑 MACD（EMA of EMA 快/慢线，双平滑信号线）。增加 `macd_highest` 线（120 周期最高值）用于阈值比较。
- **`InOutLine`** — 追踪 `lowest`（12 周期最低价）和 `upper`（lowest × 1.5）。用于动态止损/止盈。
- **`UpCrossSignal`** — 包装 `bt.indicators.CrossOver(FastMACD.macd, FastMACD.signal)`。金叉输出 +1（买入信号）。
- **`fast_macd_strtgy`** — 主力策略：MACD 金叉且 signal > 0 时买入；收盘价触 upper（止盈）或 lower（止损）时卖出。止损/止盈在买入时用 `calculate_stop_loss_target()` 动态计算。

策略文件通用布局：指标类 → 策略类（`next()`/`notify_order()`/`notify_trade()`）→ `load_stocks_from_file()` → `main()` argparse 入口。

### 策略变体

- **`fast_macd_base.py`** — 最早版本（pre-3.x 命名，使用全局变量）
- **`fast_macd3.4.py`** — 权威版本（`strategies/` 目录）
- **`fast_macd3.4_ai.py`** — AI 变体（热门板块、JSON 标准输出、懒导入）
- **`fast_macd3.4_all_stock.py`** — 批量回测器（每只股票间隔 10s，akshare 限速）
- **`fast_macd3.4_one.py`** — 单股快速回测
- **`fast_macd3.4_hk.py`** — 港股版本
- **`fast_macd3.5.py`** — 最新主线版本（WIP）
- **`fast_macd3.4_v5.py`** — **推荐版本**（`versions/` 目录）

所有变体内联复制指标类 — 每个文件自包含，不从共享模块导入。

### 分析器设置

`main()` 中的标准分析器栈：
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

结果通过 `PrintAnalyzer.printTradeAnalysis()` 输出（`from PrintAnalyzer import *` 导入）。

### 数据流

```
akshare.stock_zh_a_daily(symbol=code, adjust="qfq")  →  pandas DataFrame
    → bt.feeds.PandasData
    → bt.Cerebro.adddata + addstrategy
    → cerebro.run()
    → analyzers → printTradeAnalysis()
```

## 关键注意事项

- **无 linter / formatter / typecheck。** 无 pre-commit hooks。
- **`time.sleep(10)`** 在 `variants/fast_macd3.4_all_stock.py` 中 — akshare 故意限速，切勿删除或改短。
- **`send_email.py`** 包含硬编码 SMTP 密码 `ylnclfzmrzjpbbbi`。切勿提交额外密钥。
- **`openclaw.json`**（如存在）包含 Moonshot / ModelScope / Google / LongCat API 密钥。切勿暴露。
- 所有股票数据实时从 akshare 获取 — 无网络则失败。`data/` 和 `Input_stock_list/` 中的 CSV 是缓存/限定文件，非策略输入。
- 策略版本（3.1→3.5）是独立的 `.py` 文件（在 `strategies/` 目录），不是 git 分支。
- **v5（`versions/fast_macd3.4_v5.py`）是推荐版本**：参数 `upper_mult=2.5, macd_high_thresh=0.8, macd_low_thresh=0.4, macd_high_factor=0.3, macd_low_factor=0.6, profit_threshold=8.0, sell_pct=30.0`。平均收益 +42.22%，胜率 81%，Sharpe 1.03。
- `PrintAnalyzer.py` 通过 `from PrintAnalyzer import *` 导入。
- 股票代码格式：`sz300568`、`sh600580`（akshare 前缀格式）。
- `InOutLine.upper` 计算在不同文件中不同：`fast_macd_base.py` 和 `fast_macd3.4_all_stock.py` 使用 `lowest * 1.5`；`fast_macd3.4.py` 使用 `bt.ind.Highest(period=12)`。这是版本间的有意差异。
- `fast_macd3.4_ai.py` 使用懒导入（重型库在函数内 import），加快作为子进程的启动速度。
- **所有策略文件顶部都要添加 `common/` 到 `sys.path`**。子目录文件用 `os.path.join(..., '..', 'common')`；根目录文件用 `os.path.join(..., 'common')`。新增策略文件必须包含此代码。
- **`scripts/screen_stocks_for_v5.py` 使用不同的 Python 路径**：文件顶部通过 `PYTHON_EXE` 常量指定 `Python312\venvs\backtrader\python.exe`。

## 目录结构

```
strategies/               — 主线策略（base, 3.1–3.5）
versions/                 — 退出管理迭代（v2–v12, v_exp*, v5_etf）
variants/                 — AI 变体 + 一次性实验
scripts/                  — 选股、报告生成、辅助脚本
common/                   — 共享工具（策略文件通过 sys.path.insert 导入）
data/                     — 筛选 CSV 和分析辅助脚本
results/                  — HTML 报告和批量 CSV
Input_stock_list/         — 股票输入文件
screening/                — 选股包（占位符）
docker_image/             — ARM64 Docker 定时运行
```
