# AGENTS.md

## 项目简介

个人 A 股（少量港股）回测项目。基于 `backtrader` + `akshare`，扁平目录，无测试框架。每个策略文件是自包含的（指标类内联复制，不共享导入）。

## 文件族谱

三条主要分支 + 单改进实验 + 参数扫描：

```
原始主线
  fast_macd_base.py → 3.1 → 3.2 → 3.3 → 3.4.py (权威版本)
                    └→ 3.5.py (WIP)

退出管理优化 (基于 3.4)
  3.4.py → _v2 → _v3 → _v4 → _v5 → _v6 → _v7
  v3: +分批止盈 (10%卖50%)
  v8: +宽松ATR移动止损 (3.5×ATR)
  v4: +放宽 macd_low_factor 0.5→0.6
  v5: +可配置分批止盈 (8%/30%)
  v6: +ATR 移动止损 (2.0x)
  v7: +硬性百分比止损 (-15%)
| **v8** | ast_macd3.4_v8.py | v5 + ATR移动止损 3.5×ATR | +32.78% | 75% | 0.72 |

AI 系列 (服务器运行)
  3.4_ai.py → _ai2 → _ai3
  ai2: ATR动态止损 + ADX趋势过滤 + 自适应MACD参数
  ai3: ai2 + ADX动态ATR倍数

单改进实验 (独立文件)
  3.4_so.py     — 分批止盈 (10%卖50%)
  3.4_rr.py     — 风险收益比 >1.2 过滤
  3.4_atr.py    — ATR下限保护止损
  3.4_dyatr.py  — ADX动态ATR止损
  3.4_va.py     — 波动率自适应MACD (4组预设)

参数扫描 (sweep)
  3.4_sweep.py → _v2 → _v3 → _v4
  输出 → sweep_v*_results.csv
```

## 基准结果

### 推荐版本

| 版本 | 文件 | 核心改进 | 平均收益 | 胜率 | 夏普 |
|------|------|----------|----------|------|------|
| **v5** | `fast_macd3.4_v5.py` | 五参数 + 分批止盈 8%/30% | **+42.22%** | 81% | **1.03** |
| v2 | `fast_macd3.4_v2.py` | 最优五参数 (2.5/0.8/0.4/0.3/0.6) | +43.56% | 75% | 0.96 |
| v6 | `fast_macd3.4_v6.py` | v5 + ATR止损 (3×ATR) | +27.06% | 78% | 0.83 |
| 原始 | `fast_macd3.4.py` | 原始版本 (1.5/0.6/0.3) | +30.16% | 78% | 1.03 |

### v5 最优参数

```python
upper_mult = 2.5          # 止盈宽度
macd_high_thresh = 0.8    # 强趋势阈值
macd_low_thresh = 0.4     # 中趋势阈值
macd_high_factor = 0.3    # 强趋势止盈倍数
macd_low_factor = 0.6     # 中趋势止盈倍数
profit_threshold = 8.0    # 分批止盈阈值
sell_pct = 30.0           # 分批止盈比例
```

### 指标定义

- **夏普** = 平均收益 / 收益标准差（越高越好）
- **胜率** = 盈利交易数 / 总交易数
- **最大损失** = 单只股票最大回撤

详见 `ai3_vs_ai2_comparison.md` 和各 `sweep_v*_results.csv`。

## 关键文件

- **`fast_macd3.4.py`** — 原始权威版本，使用 `calculate_stop_loss_target()` 动态止盈止损
- **`fast_macd3.4_ai.py`** — AI 变体，`backtest_server.py` 以子进程方式调用
- **`backtest_server.py`** — HTTP 服务 (端口 18765)，子进程运行 `3.4_ai.py`
- **`fast_macd3.4_all_stock.py`** — 批量回测，每只股票间隔 10s（akshare 限速）
- **`fast_macd3.4_one.py`** — 单股快速回测
- **`fast_macd3.4_hk.py`** — 港股版本
- **`fast_macd3.4_sweep*.py`** — 参数暴力扫描（sweep），输出 CSV
- **`instruction.txt`** — AI 开发指令 backlog，记录每个版本的需求来源

## 开发流程

每次生成新版本后必须执行以下步骤，**不可跳过**：

1. **创建版本文件**：基于上一版本，加上版本注释（`# vN: +改进内容`）
2. **更新 AGENTS.md**：在文件族谱中添加新版本条目
3. **运行完整回测**：用默认 36 只股票、统一日期范围（如 `20240101-20250610`）执行：
   ```bash
   python fast_macd3.4_vN.py -s 20240101 -e 20250610 2>&1 | tee vN_output.txt
   ```
4. **记录结果到 `version_comparison.md`**：将 vN 的数据填入汇总对比表（格式见该文件）
5. **写分析**：在 `version_comparison.md` 的"关键发现"和"结论"中添加 vN 的对比分析

### 对比表字段说明

| 字段 | 来源 |
|------|------|
| 平均收益 | 36 只股票收益率的算术平均 |
| 盈利数/胜率 | `盈利股票数/总股票数` 及百分比 |
| 最高/最低收益 | 36 只中的最大值和最小值 |
| 夏普 | PrintAnalyzer 输出的年均化 Sharpe |

## 运行命令

```bash
# 单股自定义日期
python fast_macd3.4.py --start_date 20240101 --end_date 20250101

# 批量回测
python fast_macd3.4_all_stock.py -f stocks.csv -s 20240101

# HTTP 服务
python backtest_server.py
# GET http://localhost:18765/run?start_date=20220101

# AI 变体（输出 JSON 到 stdout）
python fast_macd3.4_ai.py --start_date 20220101

# 参数扫描 (ai2 内置)
python fast_macd3.4_ai2.py --sweep -s 20240101 -e 20250610
```

股票文件格式：`code,name`（如 `sz300568,星源材质`），UTF-8 with BOM 自动处理。

## 环境

```bash
conda env: backtrader
python: D:\Users\lzl_k\anaconda3\envs\backtrader\python.exe
覆盖: env var BACKTEST_PYTHON
```

`.vscode/launch.json` 有预置的 ai2 调试配置（单股 + sweep + 全量）。

## 数据流

```
akshare.stock_zh_a_daily(symbol, adjust="qfq") → pd.DataFrame
  → bt.feeds.PandasData → bt.Cerebro → strategy → analyzers → PrintAnalyzer.printTradeAnalysis()
```

## 目录结构

```
fast_macd3.*.py            — 策略版本 (原始/ai/so/rr/va/atr/dyatr/v2-v7/hk/sweep)
fast_macd_base.py          — 最早期版本
backtest_server.py         — HTTP API 服务
common/                    — 共享工具 (策略文件通过 sys.path.insert 导入)
├── send_email.py          — 邮件通知 (硬编码 SMTP 密码 ylnclfzmrzjpbbbi)
├── PrintAnalyzer.py       — 回测结果格式化输出
├── helpper.py             — akshare 概念板块爬虫
├── stock_list*.py         — 股票列表工具 (A股/港股/板块)
└── eastmoney_boards.py    — 东方财富板块爬虫
stock_data_gethoring.py    — 数据采集
docker_image/              — ARM64 Docker 定时运行配置
  ├── Dockerfile
  └── start.sh
vectorbt/                  — vectorbt 替代方案
testing/                   — 实验脚本 (非测试)
data/                      — 股票 CSV 缓存数据
learn_backtrader-master/   — 教程参考代码
```

## 关键注意事项

- **无 linter/formatter/typecheck**，无 pre-commit hooks
- 批量回测中 `time.sleep(10)` 是故意的 akshare 限速，不要删除
- `send_email.py` 硬编码 SMTP 密码 `ylnclfzmrzjpbbbi`，勿提交额外密钥
- `openclaw.json`（如存在）包含 Moonshot/ModelScope/Google/LongCat API 密钥，勿泄露或提交
- 所有股票数据实时从 akshare 拉取，无网络则失败。根目录 CSV 是缓存的股票列表，非策略输入
- 每个策略文件顶部都有 `sys.path.insert(0, ...)` 加入 `common/` 目录。新策略文件必须包含此代码
- PrintAnalyzer 通过 `from PrintAnalyzer import *` 导入
- 股票代码格式：`sz300568`、`sh600580`（akshare 前缀格式）
- 注释和日志均为中文
- `fast_macd3.4_ai.py` 使用懒导入（重型库在函数内 import），加快子进程启动速度
