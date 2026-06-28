# AGENTS.md

## 工作规则

- **先计划后动手。** 任何非平凡修改，先探索相关代码、制定计划并等待用户批准，再写代码。
- **策略改动必须完整回测。** 每次修改指标、止盈止损、过滤器、参数逻辑后，用默认股票列表跑完整一轮回测并记录结果。
- **对比历史版本。** 新版本必须与基线版本用相同股票列表和日期范围做对比，结果记录到 `results/version_comparison.html`。

## 项目简介

A 股（少量港股）回测项目。`backtrader` + `akshare`。无测试框架、无 CI、无 linter / formatter。每个策略文件自包含（指标类内联复制，不共享导入）。注释和日志均为中文。

## Python 环境

```
conda env: backtrader（主要）
python:    D:\Users\lzl_k\anaconda3\envs\backtrader\python.exe
备用 python: D:\Users\lzl_k\AppData\Local\Programs\Python\Python312\venvs\backtrader\python.exe
           （scripts/screen_stocks*.py 通过 PYTHON_EXE 使用）
覆盖:  env var BACKTEST_PYTHON
```

## 目录结构

```
strategies/                — 主线策略族系（base → 3.1 → 3.5）
  fast_macd_base.py           最早版本（全局变量，pre-3.x）
  fast_macd3.1.py … 3.5.py    3.4.py 是权威版本
  fast_macd3.5.py             WIP

versions/                  — 退出管理迭代（v2 → v11 + v12）
  fast_macd3.4_v5.py          **推荐版本**（+42.22%, 81%胜率, Sharpe 1.03）
  fast_macd3.4_v5_etf.py      ETF 变体
  fast_macd3.4_v12.py         主线最优实验（+25.06%, 73.5%胜率）
                              新增 20/60 EMA 趋势过滤 + 成交量过滤 + 冷却期
  fast_macd3.4_v_exp*.py      v5 基线实验（exp1 ~ exp9）
    v_exp1: +ATR 追踪止损 3.5x        +34.37% / 75.0%
    v_exp2: +时间止损（20日亏损平仓）   +42.33% / 83.3% ← 最佳实验
    v_exp3: +ADX 趋势过滤 (ADX>25)      +30.44% / 69.4%
    v_exp4: +自适应 MACD（ATR 比率）     +9.20% / 52.8%
    v_exp5: +风险收益比 >1.5 过滤        +35.61% / 80.6%
    v_exp6: +时间止损 + RR 过滤          +34.33% / 83.3%
    v_exp8: +ADX 动态 ATR 倍数           +29.43% / 83.3%
    v_exp9: +上证指数择时                +42.22% / 80.6%

variants/                  — AI 变体 + 一次性实验
  fast_macd3.4_ai.py          AI 变体（热门板块、JSON 标准输出、懒导入）
  fast_macd3.4_ai2.py         +ATR 止损 + ADX 过滤 + 自适应 MACD
  fast_macd3.4_ai3.py         ai2 + ADX 动态 ATR 倍数
  fast_macd3.4_ai*_so.py      ai2/ai3 + 分批止盈
  fast_macd3.4_all_stock.py   批量回测器（10s 间隔 — akshare 限速）
  fast_macd3.4_one.py         单股快速回测
  fast_macd3.4_hk.py          港股版本
  fast_macd3.4_so.py       分批止盈（止盈 10%, 卖出 50%）
  fast_macd3.4_rr.py       风险收益比 >1.2 过滤
  fast_macd3.4_atr.py      ATR 下限保护止损
  fast_macd3.4_dyatr.py    ADX 动态 ATR 止损
  fast_macd3.4_va.py       波动率自适应 MACD（4 组预设）

scripts/                   — 辅助脚本（选股、报告、数据获取）
  screen_stocks_for_v5.py     V5 全市场选股流水线：全 A 股 → 4 维评分 →
                             Top-N v5 回测 → HTML 报告（使用 PYTHON_EXE）
  screen_stocks_105factors.py 105 维因子选股器（动量/波动/量能/技术等）
                             输出到 data/screened_stocks_full.csv，断点续跑
  step1_fetch_list.py        通过 akshare stock_zh_a_spot_em 获取筛选后的 A 股列表
  daily_hot_stocks.py        每日热门板块龙头股系统（hot_stock_fetcher + stock_scorer）
  _gen_report.py             V5 选股 HTML 报告独立生成器
  _gen_stockfile.py          股票文件生成器
  _fix_akshare.py            akshare 兼容性修复
  _test_eastmoney.py         EastMoney API 测试
  _test_warning.py           警告过滤测试

common/                    — 共享工具（通过 sys.path.insert 导入）
  PrintAnalyzer.py           交易分析格式化输出（`from PrintAnalyzer import *`）
  send_email.py              邮件通知（SMTP 密码硬编码 — ylnclfzmrzjpbbbi）
  helpper.py                 akshare 概念板块爬虫
  stock_list*.py             A 股 / 港股 / 板块股票列表加载器
  eastmoney_boards.py        EastMoney 板块爬虫
  hot_stock_fetcher.py       基于 akshare 的概念板块 + 资金流数据获取器
  stock_scorer.py            板块排名 + 龙头选取

results/                    — 生成的报告（CSV 和 HTML）
  version_comparison.html    v5 ~ v11 主线对比表
  v_all_comparison_2022.html 全版本排名（v1 ~ v12 + exp，2022-2025 测试）
  v_exp_comparison.html      v5 实验对比（exp1 ~ exp9）
  v5_best_fit_report.html    V5 选股报告
  v5_best_fit_results.csv    V5 选股回测结果
  batch_results_*.csv        每批运行输出（36 只 CSV）
  summary_report.html        Deepseek 股票池汇总
  hot_stocks_*.csv           每日热门股票输出

data/                      — 中间数据文件
  screened_stocks.csv        4263 只股票筛选指标（振幅/adx/涨幅/波动率）
  top200_candidates.csv      V5 Top-200 候选
  v5_best_fit_results.csv    V5 每只股票回测输出
  *.py                       分析/对比辅助脚本

v5_stock_profiler.py        17 维股票画像工具（通过 importlib 导入 v5）
analyze_profile.py        特征与收益的关联分析
instruction.txt             AI 开发指令 backlog

Input_stock_list/          — 股票输入文件（如 deepseek 121 只股票池）
screening/                 — 选股包（占位符）
docker_image/              — ARM64 Docker 定时运行（cron 9:35 + 15:30 周一至周五）
```

## 公共导入模式

每个策略文件顶部都需要将 `common/` 加入 `sys.path`：

```python
import os, sys

# 从子目录（strategies/, versions/, variants/, data/）:
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))

# 从根目录文件（v5_stock_profiler.py）:
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'common'))

# 从 scripts 目录（scripts/ → 项目根目录 → common）:
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, 'common'))
```

然后导入：
```python
from PrintAnalyzer import *
import send_email
```

新增的 **common 模块**（`hot_stock_fetcher.py`, `stock_scorer.py`）同样由需要它们的脚本通过上述方式导入。

## v5 的 importlib 导入模式

`v5_stock_profiler.py` 和 `scripts/screen_stocks_for_v5.py` 因为文件名含小数点，使用 `importlib` 导入策略模块：

```python
import importlib.util, os
_v5_path = os.path.join(PROJECT_DIR, 'versions', 'fast_macd3.4_v5.py')
_v5_spec = importlib.util.spec_from_file_location('fast_macd3_4_v5', _v5_path)
_v5_mod = importlib.util.module_from_spec(_v5_spec)
sys.modules['fast_macd3_4_v5'] = _v5_mod
_v5_spec.loader.exec_module(_v5_mod)
fast_macd_strtgy = _v5_mod.fast_macd_strtgy
```

注意路径指向 `versions/fast_macd3.4_v5.py`（不是 `strategies/`）。

## 运行命令

```bash
# === 主线回测 ===
# 单股，自定义日期
python strategies/fast_macd3.4.py --start_date 20240101 --end_date 20250101

# 从股票列表批量运行
python variants/fast_macd3.4_all_stock.py -f <stock_file> -s 20240101

# === AI 变体 ===
# ai 变体（JSON 标准输出）
python variants/fast_macd3.4_ai.py --start_date 20220101

# 参数扫描（ai2/ai3 内置）
python variants/fast_macd3.4_ai2.py --sweep -s 20240101 -e 20250610

# === 股票筛选 ===
# V5 全市场选股（需要 PYTHON_EXE 路径 — 见脚本顶部）
python scripts/screen_stocks_for_v5.py --top 200 -s 20240101 -e 20250610

# 105 维因子选股
python scripts/screen_stocks_105factors.py

# 仅获取股票列表
python scripts/step1_fetch_list.py

# 仅重新生成 HTML 报告（不跑回测）
python scripts/_gen_report.py

# === 每日热门股票（概念板块 + 资金流向）===
python scripts/daily_hot_stocks.py
python scripts/daily_hot_stocks.py --top_n_boards 5 --top_n_stocks 10

# === 股票画像 ===
python v5_stock_profiler.py -f Input_stock_list/deepseek_csv_20260621_3c2bb1.txt
```

股票文件格式：`code,name` 每行（如 `sz300568,星源材质`）。自动处理 UTF-8 BOM。

股票代码格式：`sz300568`, `sh600580`（akshare 前缀格式）。

## 开发流程

创建新版本：

1. 将前一版本复制到 `versions/fast_macd3.4_vN.py`（主线工作复制到 `strategies/fast_macd3.4_vN.py`）
2. 添加版本注释：`# vN: +改进说明`
3. 文件顶部包含 `sys.path.insert(..., '..', 'common')`
4. 运行完整回测：
   ```bash
   python versions/fast_macd3.4_vN.py -f Input_stock_list/deepseek_csv_20260621_3c2bb1.txt \
       -s 20240101 -e 20250610 2>&1 | tee vN_output.txt
   ```
5. 将结果记录到 `results/version_comparison.html` 或 `results/v_exp_comparison.html`（HTML 格式，不是 `.md`）
6. 更新本 AGENTS.md 的目录结构部分

### 对比指标

| 字段 | 来源 |
|------|------|
| 平均收益 | 所有股票收益率的算术平均 |
| 胜率 | `盈利股票数 / 总股票数` |
| 最高/最低 | 该批次中最佳和最差收益 |
| 夏普 | PrintAnalyzer 的年化 Sharpe |

## 数据流

```
# 回测
akshare.stock_zh_a_daily(symbol, adjust="qfq") → pd.DataFrame
  → bt.feeds.PandasData → bt.Cerebro → strategy → analyzers
  → PrintAnalyzer.printTradeAnalysis()

# 选股流水线
akshare stock_info_a_code_name() → 筛选 → 每只股票获取 120 天数据
  → 计算 4 维或 105 维因子 → 打分/筛选 → 导出 CSV
  → 子进程 → 每只股票 v5 回测 → HTML 报告

# 每日热门股票
hot_stock_fetcher.get_hot_concept_boards() + get_fund_flow_rank()
  → stock_scorer.rank_boards() + pick_leaders()
  → 输出 CSV + send_email
```

## 关键注意事项

- **无 linter / formatter / typecheck / pre-commit hooks。** 无 CI。
- **`time.sleep(10)`** 在 `variants/fast_macd3.4_all_stock.py` 中 — akshare 故意限速，不要删除。
- **`send_email.py`** 包含硬编码 SMTP 密码 `ylnclfzmrzjpbbbi`。切勿提交额外密钥。
- **`openclaw.json`**（如存在）包含 Moonshot / ModelScope / Google / LongCat API 密钥。切勿泄露或提交。
- 所有股票数据实时从 akshare 获取 — 无网络则失败。`data/` 和 `Input_stock_list/` 中的 CSV 是缓存/范围限定文件，非策略输入。
- **v5 是推荐的最佳版本**（`versions/fast_macd3.4_v5.py`）。新实验的基线。
- **v_exp2（时间止损 20 日）是 v5 基线的最佳实验**（+42.33% 平均收益, 83.3% 胜率）。
- **`scripts/` 使用不同的 Python 路径**（`Python312\venvs\backtrader\`）与 conda 环境不同。两者均可工作。
- **`fast_macd3.4_ai.py`** 使用懒导入（backtrader/pandas 在函数内 import）以加快子进程启动速度。
- **`v5_stock_profiler.py`** 因为文件名含小数点，通过 `importlib` 导入策略。
- **`daily_hot_stocks.py`** 依赖 `common/hot_stock_fetcher.py` 和 `common/stock_scorer.py`，这些模块基于 akshare — 每次运行都需要网络。
