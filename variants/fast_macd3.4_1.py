#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastMACD Strategy v3.4.1 — Refactored from 3.4.

Changes from 3.4:
- Removed dead code (unused MACD class, unused SMA, commented-out blocks).
- Extracted magic numbers to module-level constants.
- Renamed cryptic variables (cat→signal_tier, std_scale→band_width,
  out_point_up→take_profit, out_point_down→stop_loss).
- Simplified next(): removed redundant pre-trade estimation block.
- Split main() into parse_args(), load_or_default_stocks(),
  run_single_backtest(), main().
"""

from datetime import datetime, date, timedelta
import time
import argparse
import os

import backtrader as bt
import akshare as ak
import pandas as pd

from backtrader.indicators import EMA, Lowest

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import send_email
from PrintAnalyzer import *


# ══════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════
MIN_DATA_ROWS = 30
INITIAL_CASH = 100_000
COMMISSION = 0.002
SLIPPAGE = 0.0001
SIZER_PERCENT = 95
RATE_LIMIT_SLEEP_SECONDS = 10

# Signal-tier thresholds (fraction of 120-day MACD high)
MACD_HIGH_THRESHOLD_STRONG = 0.6
MACD_HIGH_THRESHOLD_WEAK = 0.3
PROFIT_MULTIPLIER_STRONG = 0.3
PROFIT_MULTIPLIER_WEAK = 0.5

# Trailing-stop trigger: when high reaches this fraction of take_profit,
# ratchet stop_loss up to the higher of (close, low, buy_price).
TRAILING_STOP_TRIGGER = 0.985


# ══════════════════════════════════════════════
#  Indicators
# ══════════════════════════════════════════════

class InOutLine(bt.Indicator):
    """12-period lowest-low and highest-high channel."""
    lines = ('lowest', 'upper')
    params = (('low_period', 12),)

    plotinfo = dict(subplot=False, plot=True)

    def __init__(self):
        self.l.lowest = bt.ind.Lowest(self.data, period=self.p.low_period)
        self.l.upper = bt.ind.Highest(self.data, period=self.p.low_period)


class FastMACD(bt.Indicator):
    """Double-smoothed MACD with 120-day highest-MACD reference line."""
    lines = ('macd', 'signal', 'histo', 'macd_highest')
    params = (
        ('period_fast', 12),
        ('period_slow', 26),
        ('period_signal', 9),
        ('high_period', 12),
    )

    plotlines = dict(
        histo=dict(_method='bar', alpha=0.50, width=1.0),
        macd=dict(color='yellow'),
        signal=dict(color='grey'),
    )

    def __init__(self):
        # Fast EMA (double-smoothed)
        fastma1 = EMA(self.data, period=self.p.period_fast)
        fastma2 = EMA(fastma1, period=self.p.period_fast)
        fastma = fastma1 * 2 - fastma2

        # Slow EMA (double-smoothed)
        slowma1 = EMA(self.data, period=self.p.period_slow)
        slowma2 = EMA(slowma1, period=self.p.period_slow)
        slowma = slowma1 * 2 - slowma2

        self.l.macd = fastma - slowma

        # Signal (double-smoothed)
        signal1 = EMA(self.l.macd, period=self.p.period_signal)
        signal2 = EMA(signal1, period=self.p.period_signal)
        self.l.signal = signal1 * 2 - signal2

        self.l.histo = self.l.macd - self.l.signal
        self.l.macd_highest = bt.ind.Highest(self.l.macd, period=120)


class UpCrossSignal(bt.Indicator):
    """+1 when FastMACD.macd crosses above signal, -1 when below."""
    lines = ('crossOver',)

    def __init__(self):
        fastmacd = FastMACD(self.datas[0])
        self.lines.crossOver = bt.indicators.CrossOver(
            fastmacd.l.macd, fastmacd.l.signal
        )

    plotinfo = dict(plot=False)


# ══════════════════════════════════════════════
#  Strategy
# ══════════════════════════════════════════════

class fast_macd_strtgy(bt.Strategy):
    params = (('stock_code', ''), ('stock_name', ''))

    def __init__(self):
        self.fastMacd = FastMACD()
        self.upCrossSignal = UpCrossSignal()
        self.inOutLine = InOutLine()

        self.data_close = self.datas[0].close
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low

        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.take_profit = None
        self.stop_loss = None

        self.stock_code = self.params.stock_code
        self.stock_name = self.params.stock_name

    # ── Entry / Exit logic ─────────────────────

    def next(self):
        if self.order:
            return

        if not self.position:
            self._try_buy()
        else:
            self._try_sell()

    def _try_buy(self):
        buy_signal = (
            self.upCrossSignal.crossOver == 1
            and self.fastMacd.l.signal[0] > 0
        )
        if not buy_signal:
            return

        current_price = self.data_close[0]
        tp, sl, est_ret, est_sl, tier, bw = self.calculate_stop_loss_target(current_price)

        self.log(
            f"Buy tomorrow! Price: {current_price:.2f}, "
            f"Target: {tp:.2f}, Stop: {sl:.2f}, "
            f"Return: {est_ret:.2f}%, StopLoss: {est_sl:.2f}%, Tier: {tier}"
        )
        self.email_notify(
            f"Buy tomorrow! Price: {current_price:.2f}, "
            f"Target: {tp:.2f}, Stop: {sl:.2f}"
        )
        self.order = self.buy()

    def _try_sell(self):
        # Trailing stop: if price near take_profit, ratchet stop_loss up.
        if self.data_high[0] >= self.take_profit * TRAILING_STOP_TRIGGER:
            candidate = min(self.data_close[0], self.data_low[0], self.buy_price)
            if candidate > self.stop_loss:
                self.stop_loss = candidate
                self.log(f"Stop revised to {self.stop_loss}")
                self.email_notify(f"Stop revised to {self.stop_loss}")

        if self.data_close[0] >= self.take_profit or self.data_close[0] <= self.stop_loss:
            self.log("Sell tomorrow!")
            self.email_notify("Sell tomorrow!")
            self.order = self.close()

    # ── Order / Trade callbacks ────────────────

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self._on_buy_filled(order)
            else:
                self._on_sell_filled(order)
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order {order.status}')

        self.order = None

    def _on_buy_filled(self, order):
        self.buy_price = order.executed.price
        self.buy_comm = order.executed.comm

        tp, sl, exp_ret, sl_ret, tier, bw = self.calculate_stop_loss_target(self.buy_price)
        self.take_profit = tp
        self.stop_loss = sl

        msg = (
            f"{self.stock_code} Buy executed, Price: {order.executed.price:.2f}, "
            f"Cost: {order.executed.value}, "
            f"Target: {tp:.2f}, Stop: {sl:.2f}, "
            f"Return: {exp_ret:.2f}%, StopLoss: {sl_ret:.2f}%, "
            f"Tier: {tier}, BandWidth: {bw:.2f}"
        )
        self.log(msg)
        self.email_notify(msg)

    def _on_sell_filled(self, order):
        msg = (
            f"{self.stock_code} Sell executed, "
            f"Price: {order.executed.price:.2f}, Cost: {order.executed.value}"
        )
        self.log(msg)
        self.email_notify(msg)

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        if trade.pnl and trade.value:
            return_rate = (trade.pnl / trade.value) * 100
            self.log(
                f"Trade closed, Gross: {trade.pnl:.2f}, "
                f"Net: {trade.pnlcomm:.2f}, Return: {return_rate:.2f}%"
            )
        else:
            self.log(f"Trade closed, Gross: {trade.pnl}, Net: {trade.pnlcomm}")

    # ── Stop / Target calculation ──────────────

    def calculate_stop_loss_target(self, current_price):
        """
        Compute dynamic take-profit and stop-loss.

        Returns: (take_profit, stop_loss, expected_return, stop_loss_return,
                  signal_tier, band_width)
        """
        if self.inOutLine.lowest[0] <= current_price:
            stop_loss = self.inOutLine.lowest[0]
        else:
            stop_loss = current_price

        band_width = (current_price - self.inOutLine.lowest[0]) * 1.5
        signal_tier = 0

        if band_width < 0:
            take_profit = self.inOutLine.upper[0]
        elif self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * MACD_HIGH_THRESHOLD_STRONG:
            take_profit = current_price + band_width * PROFIT_MULTIPLIER_STRONG
        elif self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * MACD_HIGH_THRESHOLD_WEAK:
            take_profit = current_price + band_width * PROFIT_MULTIPLIER_WEAK
            signal_tier = 2
        else:
            take_profit = current_price + band_width
            signal_tier = 3

        expected_return = (
            (take_profit - current_price) / current_price * 100
            if current_price else 0.0
        )
        stop_loss_return = (
            (stop_loss - current_price) / current_price * 100
            if current_price else 0.0
        )

        return (take_profit, stop_loss, expected_return,
                stop_loss_return, signal_tier, band_width)

    # ── Notifications ──────────────────────────

    def email_notify(self, txt):
        if self.datas[0].datetime.date(0) == date.today():
            self.log("sending email")
            dt = self.datas[0].datetime.date(0)
            sender = send_email.SendEmail()
            user_list = ['lzl_kni@qq.com']
            subject = "fmacd_execut"
            content = f"{dt.isoformat()} {self.stock_code} {self.stock_name} {txt}"
            sender.send_mail(user_list, subject, content)

    def log(self, txt, dt=None, doprint=True):
        if doprint:
            dt = dt or self.datas[0].datetime.date(0)
            if dt > (datetime.today() - timedelta(days=90)).date():
                print(f"{datetime.today().strftime('%Y-%m-%d')} {dt.isoformat()} {txt}")


# ══════════════════════════════════════════════
#  Stock list loading
# ══════════════════════════════════════════════

def load_stocks_from_file(filename):
    """
    Load stock list from file.

    Format: one stock per line, "code,name" or just "code".
    Example: sz300568,星源材质
    """
    stocks_map = {}

    if not os.path.exists(filename):
        print(f"文件 {filename} 不存在")
        return stocks_map

    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip().replace('﻿', '')
                if not line or line.startswith('#'):
                    continue

                parts = line.split(',')
                if len(parts) >= 2:
                    code, name = parts[0].strip(), parts[1].strip()
                    if code and not code.startswith('#'):
                        stocks_map[code] = name
                elif len(parts) == 1:
                    code = parts[0].strip()
                    if code and not code.startswith('#'):
                        stocks_map[code] = code
                else:
                    print(f"第{line_num}行格式不正确，跳过：{line}")

        print(f"成功从 {filename} 加载了 {len(stocks_map)} 只股票")
        return stocks_map

    except Exception as e:
        print(f"读取文件 {filename} 时出错：{e}")
        return {}


DEFAULT_STOCKS = {
    'sz301209': '联合化学', 'sh688143': '长盈通', 'sz300255': '常山药业',
    'sz002364': '中恒电气', 'sz300607': '拓斯达', 'sz002131': '利欧股份',
    'sh688521': '芯原股份', 'sh600580': '卧龙电驱', 'sz301377': '鼎泰高科',
    'sz002779': '中坚科技', 'sz002460': '赣锋锂业', 'sz000858': '五粮液',
    'sz000333': '美的', 'sh603259': '药明', 'sz300638': '广和',
    'sz002881': '美格', 'sh603118': '共进', 'sh600507': '方大特钢',
    'sh601088': '中国神华', 'sz300654': '世纪天鸿', 'sh603011': '合锻智能',
    'sh688095': '福昕软件', 'sh600895': '张江高科', 'sh600119': '长江投资',
    'sz301308': '江波龙', 'sz002466': '天齐锂业', 'sh688168': '安博通',
    'sh688195': '腾景科技', 'sz002413': '雷科防务', 'sz002813': '路畅科技',
    'sz300007': '汉威科技', 'sz300502': '新易盛', 'sz000962': '东方钽业',
    'sz002050': '三花智控', 'sz300842': '帝科股份', 'sh600198': '大唐电信',
}


def load_or_default_stocks(filepath):
    """Load stocks from file; fall back to DEFAULT_STOCKS if file missing/empty."""
    stocks = load_stocks_from_file(filepath) if filepath else {}
    if not stocks:
        print("使用默认股票列表")
        stocks = DEFAULT_STOCKS
    return stocks


# ══════════════════════════════════════════════
#  Per-stock backtest runner
# ══════════════════════════════════════════════

COLUMN_NAMES = ['date', 'open', 'high', 'low', 'close', 'volume']


def run_single_backtest(stock_code, stock_name, start_date, end_date):
    """Run backtest for one stock. Prints results to stdout."""
    df = ak.stock_zh_a_daily(
        symbol=stock_code, adjust="qfq",
        start_date=start_date, end_date=end_date,
    ).iloc[:, :6]

    if len(df) < MIN_DATA_ROWS:
        print(f"{stock_code} {stock_name} 行数少于{MIN_DATA_ROWS}，跳过。")
        return

    df.columns = COLUMN_NAMES
    df.index = pd.to_datetime(df['date'])

    cerebro = bt.Cerebro()
    cerebro.adddata(bt.feeds.PandasData(dataname=df))
    cerebro.addstrategy(fast_macd_strtgy, stock_code=stock_code, stock_name=stock_name)
    cerebro.broker.setcash(INITIAL_CASH)
    cerebro.broker.setcommission(commission=COMMISSION)
    cerebro.broker.set_slippage_perc(SLIPPAGE)
    cerebro.addsizer(bt.sizers.AllInSizer, percents=SIZER_PERCENT)

    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe',
                        riskfreerate=0.02, annualize=True,
                        timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
    cerebro.addanalyzer(bt.analyzers.Transactions, _name='txn')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual_return')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='time_return')

    result = cerebro.run()
    port_value = cerebro.broker.getvalue()
    pnl = port_value - INITIAL_CASH

    print(f"Stock: {stock_name}")
    print(f"初始资金: {INITIAL_CASH}")
    print(f"总资金: {round(port_value, 2)}")
    print(f"净收益: {round(pnl, 2)}")

    printTradeAnalysis(cerebro, result[0].analyzers)

    dd = result[0].analyzers.drawdown.get_analysis()
    print(f"最大回撤: {dd['max']['drawdown']:.2f}%")
    print(f"最大回撤持续时间: {dd['max']['len']} 天")


# ══════════════════════════════════════════════
#  CLI entry point
# ══════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(description='股票回测系统')
    parser.add_argument('--stocks_file', '-f', type=str, default='',
                        help='股票列表文件路径')
    parser.add_argument('--start_date', '-s', type=str, default='20240101',
                        help='回测开始日期 (YYYYMMDD)')
    parser.add_argument('--end_date', '-e', type=str,
                        default=datetime.today().strftime('%Y%m%d'),
                        help='回测结束日期 (YYYYMMDD)')
    return parser.parse_args()


def main():
    args = parse_args()
    stocks = load_or_default_stocks(args.stocks_file)

    for stock_code, stock_name in stocks.items():
        run_single_backtest(stock_code, stock_name, args.start_date, args.end_date)
        time.sleep(RATE_LIMIT_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
