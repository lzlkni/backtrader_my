# FastMACD v3.4_ai2

基于 `fast_macd3.4.py` 增强版，新增 ATR 动态止损、ADX 趋势过滤、自适应 MACD 参数。

## 新增功能

### 1. ATR 动态止损
- **初始止损**: `入场价 - N × ATR`（做多）
- **追踪止损**: 持仓期间最高价 - N × ATR，只升不降
- **吊灯止盈 (Chandelier Exit)**: 持仓最高价 - 3 × ATR，回落触发止盈

### 2. ADX 趋势过滤
- ADX < 25 连续 3 天以上 → 不开仓（震荡市减少假信号）
- ADX 25-40: 弱趋势 | ADX > 40: 强趋势

### 3. 自适应 MACD 参数

| Preset | Fast | Slow | Signal | 适用场景 |
|--------|------|------|--------|----------|
| `intraday` | 6 | 13 | 5 | 日内/超短线 |
| `swing` | 8 | 17 | 6 | 波段/中线 |
| `long_term` | 24 | 52 | 18 | 中长线/蓝筹 |
| `choppy` | 6 | 13 | 4 | 震荡市 |

### 4. 参数扫描对比
`--sweep` 模式遍历所有 preset，输出对比表并追加到 `parameter_comparison.log`。

## 快速开始

```bash
# 单个 preset 回测（默认全股票列表）
python fast_macd3.4_ai2.py --preset swing

# 指定股票文件 + 日期范围
python fast_macd3.4_ai2.py -f stocks.csv -s 20240101 -e 20250610 --preset swing

# 自定义 MACD 参数
python fast_macd3.4_ai2.py --fast 8 --slow 17 --signal 6

# 参数扫描对比（跑 4 个 preset，输出表格）
python fast_macd3.4_ai2.py --sweep -s 20240101 -e 20250610

# 调整 ATR 参数
python fast_macd3.4_ai2.py --atr-period 14 --atr-mult 2.5 --atr-chandelier-mult 3.0

# 调整 ADX 参数
python fast_macd3.4_ai2.py --adx-threshold 30

# 关闭某个功能
python fast_macd3.4_ai2.py --no-atr-stop        # 关闭 ATR 止损
python fast_macd3.4_ai2.py --no-chandelier      # 关闭吊灯止盈
python fast_macd3.4_ai2.py --no-adx-filter      # 关闭 ADX 过滤
```

## 股票文件格式

```
sz300568,星源材质
sh600580,卧龙电驱
```

UTF-8 with BOM 自动处理。不指定 `-f` 时使用内置默认列表。

## 输出

- 每只股票输出：收益率、Sharpe、最大回撤、交易次数、胜率
- `--sweep` 额外输出对比表 + 追加到 `parameter_comparison.log`
- 触发交易信号时发送邮件（仅限当天）

## 依赖

```bash
conda activate backtrader
pip install backtrader akshare pandas
```

## 架构

```
fast_macd3.4_ai2.py
├── InOutLine, MACD, FastMACD, UpCrossSignal   ← 指标定义（同 3.4）
├── fast_macd_strtgy                            ← 策略（新增 ATR/ADX 逻辑）
├── run_backtest()                              ← 单次回测
├── run_single_stock()                          ← 单只股票
├── run_sweep()                                 ← 参数扫描对比
└── main()                                      ← 命令行入口
```
