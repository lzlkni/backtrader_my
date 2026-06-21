# V5 全市场最佳适配股票筛选计划

## 目标

在 A 股全市场（~5000 只）中找到 V5 策略表现最好的股票，构建一个"V5 友好股票池"。

## 方法与步骤

### 第 1 步：获取全 A 股列表，快速筛选

- 来源：`akshare` 获取全 A 股
- 排除：ST、北交所（bj 开头）、上市不足 1 年
- 计算 4 个筛选指标（只算指标，不跑策略）

| 指标 | 计算方式 | V5 适配范围 |
|------|---------|-------------|
| 日均振幅 | `avg((high-low)/close) × 100` | 2% ~ 8% |
| ADX(14) > 20 的天数占比 | 过去 120 天中 ADX>20 的比例 | > 40% |
| 6 个月最大涨幅 | 半年内从低点到高点最大连续升幅 | > 15% |
| 年化波动率 | std(daily_return) × sqrt(252) | 25% ~ 60% |

- 预估耗时：~12 分钟（5000 只 × 0.15s/只）
- 产出：`data/screened_stocks.csv`

### 第 2 步：加权评分排序，截取 Top 200

| 维度 | 权重 | 评分说明 |
|------|------|---------|
| 日均振幅匹配度 | 30% | 目标 2-8%，范围内给满分，偏离线性衰减 |
| ADX>20 占比 | 30% | 线性映射：0% = 0分, 100% = 1分 |
| 6 月最大涨幅 | 25% | 超出 15% 即有分，越大越好（上限 100%） |
| 年化波动率匹配度 | 15% | 目标 25-60%，范围内给满分 |

综合评分公式：`score = Σ(维度分 × 权重)`

- 产出：`data/top200_candidates.csv`

### 第 3 步：对 Top 200 跑完整 v5 回测

- 使用 `fast_macd3.4_v5.py` 批量模式
- 回测参数：`-s 20240101 -e 20250610`
- 按实际收益率降序排列
- 产出：`data/v5_best_fit_results.csv`

## 脚本设计

### `scripts/screen_stocks_for_v5.py`

```bash
# 使用方式
python scripts/screen_stocks_for_v5.py --top 200 --start 20240101 --end 20250610
```

#### 功能模块

1. `fetch_all_stocks()` — 获取全 A 股列表，过滤 ST/BJ/次新股
2. `calculate_screening_metrics(stock_code)` — 对单只股票计算 4 维指标
3. `score_stock(metrics)` — 加权评分
4. `run_v5_backtest(stock_list)` — 调用 v5 批量回测
5. `save_report()` — 输出 HTML 报告

## 截止标准

1. `data/top200_candidates.csv` 已保存（第 1+2 步完成）
2. `data/v5_best_fit_results.csv` 已保存（第 3 步完成）
3. `results/v5_best_fit_report.html` 报告生成
