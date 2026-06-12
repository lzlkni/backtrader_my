#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import time
import argparse
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'common'))

import backtrader as bt
# import matplotlib.pyplot as plt
import akshare as ak
import pandas as pd

from backtrader.indicators import EMA, Lowest

import send_email
from PrintAnalyzer import *
from datetime import date

######
# FastMACD v3.4_ai2 — Enhanced with ATR/ADX/Adaptive MACD
#   1. ATR-based dynamic stop-loss (initial + trailing)
#   2. Chandelier Exit (take profit)
#   3. ADX trend strength filter
#   4. Market-adaptive MACD parameters with sweep comparison
#####

# ══════════════════════════════════════════════
#   MACD Parameter Presets
# ══════════════════════════════════════════════
MACD_PRESETS = {
    'intraday':  {'fast': 6,  'slow': 13, 'signal': 5},   # 日内/超短线
    'swing':     {'fast': 8,  'slow': 17, 'signal': 6},   # 波段/中线
    'long_term': {'fast': 24, 'slow': 52, 'signal': 18},  # 中长线
    'choppy':    {'fast': 6,  'slow': 13, 'signal': 4},   # 震荡市
}


class InOutLine(bt.Indicator):
    lines = ('lowest', 'upper',)
    params = (('low_period', 12),)

    plotinfo = dict(subplot=False, plot=True)

    def __init__(self):
        self.l.lowest = bt.ind.Lowest(self.data, period=self.p.low_period)
        self.l.upper = bt.ind.Highest(self.data, period=self.p.low_period)


class MACD(bt.Indicator):
    lines = ('macd', 'signal', 'histo')
    params = (('period_me1', 12), ('period_me2', 26), ('period_signal', 9),)

    def __init__(self):
        me1 = EMA(self.data, period=self.p.period_me1)
        me2 = EMA(self.data, period=self.p.period_me2)
        self.l.macd = me1 - me2
        self.l.signal = EMA(self.l.macd, period=self.p.period_signal)
        self.l.histo = self.l.macd - self.l.signal


class FastMACD(bt.Indicator):
    lines = ('macd', 'signal', 'histo', 'macd_highest')
    params = (('period_fast', 12), ('period_slow', 26), ('period_signal', 9), ('high_period', 12),)

    plotlines = dict(
        histo=dict(_method='bar', alpha=0.50, width=1.0),
        macd=dict(color='yellow'),
        signal=dict(color='grey')
    )

    def __init__(self):
        fastma1 = EMA(self.data, period=self.p.period_fast)
        fastma2 = EMA(fastma1, period=self.p.period_fast)
        fastma = fastma1 * 2 - fastma2

        slowma1 = EMA(self.data, period=self.p.period_slow)
        slowma2 = EMA(slowma1, period=self.p.period_slow)
        slowma = slowma1 * 2 - slowma2

        self.l.macd = fastma - slowma

        signal1 = EMA(self.l.macd, period=self.p.period_signal)
        signal2 = EMA(signal1, period=self.p.period_signal)
        self.l.signal = signal1 * 2 - signal2

        self.l.histo = self.l.macd - self.l.signal
        self.l.macd_highest = bt.ind.Highest(self.l.macd, period=120)


class UpCrossSignal(bt.Indicator):
    lines = ('crossOver',)

    def __init__(self):
        fastmacd = FastMACD(self.datas[0])
        self.lines.crossOver = bt.indicators.CrossOver(fastmacd.l.macd, fastmacd.l.signal)

    plotinfo = dict(plot=False)


class fast_macd_strtgy(bt.Strategy):
    params = (
        ('stock_code', ''),
        ('stock_name', ''),
        ('atr_period', 14),
        ('atr_mult', 2.0),
        ('atr_chandelier_mult', 3.0),
        ('adx_period', 14),
        ('adx_threshold', 25),
        ('use_atr_stop', True),
        ('use_chandelier', True),
        ('use_adx_filter', True),
        ('period_fast', 12),
        ('period_slow', 26),
        ('period_signal', 9),
    )

    def __init__(self):
        self.sma = bt.indicators.SimpleMovingAverage(self.datas[0], period=120)

        self.fastMacd = FastMACD(
            period_fast=self.p.period_fast,
            period_slow=self.p.period_slow,
            period_signal=self.p.period_signal,
        )
        self.upCrossSignal = UpCrossSignal()
        self.inOutLine = InOutLine()

        self.atr = bt.ind.ATR(self.datas[0], period=self.p.atr_period)
        self.adx = bt.ind.ADX(self.datas[0], period=self.p.adx_period)

        self.data_close = self.datas[0].close
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low

        self.order = None
        self.buy_price = None
        self.buy_comm = None

        # ATR trailing stop state
        self.entry_price = None
        self.highest_since_entry = None
        self.current_stop = None

        # ADX filter state
        self.adx_low_streak = 0

        # Legacy fixed target/stop (kept as fallback)
        self.out_point_up = None
        self.out_point_down = None

        self.stock_code = self.params.stock_code
        self.stock_name = self.params.stock_name

    def next(self):
        if self.order:
            return

        if not self.position:
            # ── Buy logic ──

            # ADX trend filter: skip if ADX < threshold for 3+ consecutive bars
            if self.p.use_adx_filter:
                if self.adx[0] < self.p.adx_threshold:
                    self.adx_low_streak += 1
                    if self.adx_low_streak >= 3:
                        return
                else:
                    self.adx_low_streak = 0

            # MACD gold cross + signal > 0
            if self.upCrossSignal.crossOver == 1 and self.fastMacd.l.signal[0] > 0:
                current_price = self.data_close[0]

                # Calculate initial ATR-based stop
                atr_stop = current_price - (self.p.atr_mult * self.atr[0]) if self.p.use_atr_stop else None
                _, estimated_out_point_down, _, _, _, _ = self.calculate_stop_loss_target(current_price)

                # Use the tighter of ATR stop and legacy stop
                if self.p.use_atr_stop and atr_stop is not None:
                    effective_stop = max(atr_stop, estimated_out_point_down)
                else:
                    effective_stop = estimated_out_point_down

                msg = (f"Buy tomorrow! Price: {current_price:.2f}, "
                       f"ATR_Stop: {atr_stop:.2f}, Legacy_Stop: {estimated_out_point_down:.2f}, "
                       f"ATR: {self.atr[0]:.2f}, ADX: {self.adx[0]:.1f}")
                self.log(msg)
                self.email_notify(msg)

                self.entry_price = current_price
                self.highest_since_entry = self.data_high[0]
                self.current_stop = effective_stop

                self.order = self.buy()

        else:
            # ── Sell logic ──
            sell_reason = None

            # 1) ATR Trailing Stop (ratchet up only)
            if self.p.use_atr_stop and self.entry_price is not None:
                self.highest_since_entry = max(self.highest_since_entry, self.data_high[0])
                new_stop = self.highest_since_entry - (self.p.atr_mult * self.atr[0])
                if new_stop > self.current_stop:
                    self.current_stop = new_stop
                    self.log(f"Trailing stop ratcheted to {self.current_stop:.2f}")
                if self.data_low[0] <= self.current_stop:
                    sell_reason = f"ATR trailing stop hit at {self.current_stop:.2f}"

            # 2) Chandelier Exit
            if sell_reason is None and self.p.use_chandelier and self.entry_price is not None:
                self.highest_since_entry = max(self.highest_since_entry, self.data_high[0])
                chandelier_line = self.highest_since_entry - (self.p.atr_chandelier_mult * self.atr[0])
                if self.data_close[0] < chandelier_line:
                    sell_reason = f"Chandelier exit at {chandelier_line:.2f}"

            # 3) Legacy fixed target / stop (fallback)
            if sell_reason is None:
                if self.data_high[0] >= self.out_point_up * 0.985:
                    out_point_down_chk = min(self.data_close[0], self.data_low[0], self.buy_price)
                    if out_point_down_chk > self.out_point_down:
                        self.out_point_down = out_point_down_chk
                        self.log(f"Out point down revised to {self.out_point_down}")
                        self.email_notify(f"Out point down revised to {self.out_point_down}")

                if self.data_close[0] >= self.out_point_up or self.data_close[0] <= self.out_point_down:
                    sell_reason = (f"Legacy target/stop hit "
                                   f"(up={self.out_point_up:.2f}, down={self.out_point_down:.2f})")

            if sell_reason is not None:
                self.log(f"Sell tomorrow! Reason: {sell_reason}")
                self.email_notify(f"Sell! Reason: {sell_reason}")
                self.entry_price = None
                self.highest_since_entry = None
                self.current_stop = None
                self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm

                self.out_point_up, self.out_point_down, expected_return, stop_loss_return, cat, std_scale = \
                    self.calculate_stop_loss_target(self.buy_price)

                if self.p.use_atr_stop:
                    self.entry_price = self.buy_price
                    self.highest_since_entry = self.buy_price
                    self.current_stop = self.buy_price - (self.p.atr_mult * self.atr[0])

                atr_stop_str = f"{self.current_stop:.2f}" if self.current_stop else "N/A"
                msg = (f"{self.stock_code} Buy executed, Price: {order.executed.price:.2f}, "
                       f"Cost: {order.executed.value}, "
                       f"target: {self.out_point_up:.2f}, stop: {self.out_point_down:.2f}, "
                       f"atr_stop: {atr_stop_str}, "
                       f"expected_return: {expected_return:.2f}%, stop_loss: {stop_loss_return:.2f}%, "
                       f"cat: {cat}, std_scale: {std_scale:.2f}")
                self.log(msg)
                self.email_notify(msg)

            else:
                self.log(f"{self.stock_code} Sell executed, Price: {order.executed.price:.2f}, "
                         f"Cost: {order.executed.value}")
                self.email_notify(f"Sell executed, Price: {order.executed.price:.2f}, "
                                  f"Cost: {order.executed.value}")
            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order {order.status}')

        self.order = None

    def email_notify(self, txt):
        if self.datas[0].datetime.date(0) == date.today():
            self.log("sending email")
            dt = self.datas[0].datetime.date(0)
            send = send_email.SendEmail()
            user_list = ['lzl_kni@qq.com']
            sub = "fmacd_ai2_execut"
            content = f"{dt.isoformat()} {self.stock_code} {self.stock_name} {txt}"
            send.send_mail(user_list, sub, content)

    def calculate_stop_loss_target(self, current_price):
        out_point_down = self.inOutLine.lowest[0] if self.inOutLine.lowest[0] <= current_price else current_price
        std_scale = (current_price - self.inOutLine.lowest[0]) * 1.5
        cat = 0

        if std_scale < 0:
            out_point_up = self.inOutLine.upper[0]
        elif self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * 0.6:
            out_point_up = current_price + std_scale * 0.3
        elif self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * 0.3:
            out_point_up = current_price + std_scale * 0.5
            cat = 2
        else:
            out_point_up = current_price + std_scale
            cat = 3

        expected_return = (out_point_up - current_price) / current_price * 100 if current_price else 0.0
        stop_loss_return = (out_point_down - current_price) / current_price * 100 if current_price else 0.0

        return out_point_up, out_point_down, expected_return, stop_loss_return, cat, std_scale

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        if trade.pnl and trade.value:
            return_rate = (trade.pnl / trade.value) * 100
            self.log(f"Operation profit, Gross {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}, "
                     f"Return Rate: {return_rate:.2f}%")
        else:
            self.log(f"Operation profit, Gross {trade.pnl}, Net: {trade.pnlcomm}")

    def log(self, txt, dt=None, doprint=True):
        if doprint:
            dt = dt or self.datas[0].datetime.date(0)
            if dt > (datetime.today() - timedelta(days=90)).date():
                print(f"{datetime.today().strftime('%Y-%m-%d')} {dt.isoformat()} {txt}")


def load_stocks_from_file(filename):
    """
    从文件读取股票列表
    文件格式：每行一个股票，格式为 "股票代码,股票名称" 或 "股票代码"
    """
    stocks_map = {}
    if not os.path.exists(filename):
        print(f"错误：文件 {filename} 不存在")
        return stocks_map

    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                line = line.replace('﻿', '')
                parts = line.split(',')
                if len(parts) >= 2:
                    stock_code = parts[0].strip()
                    stock_name = parts[1].strip()
                    if stock_code and not stock_code.startswith('#'):
                        stocks_map[stock_code] = stock_name
                elif len(parts) == 1:
                    stock_code = parts[0].strip()
                    if stock_code and not stock_code.startswith('#'):
                        stocks_map[stock_code] = stock_code
                else:
                    print(f"警告：第{line_num}行格式不正确，跳过：{line}")

        print(f"成功从 {filename} 加载了 {len(stocks_map)} 只股票")
        return stocks_map

    except Exception as e:
        print(f"读取文件 {filename} 时出错：{e}")
        return {}


# ══════════════════════════════════════════════
#   Reusable backtest runner
# ══════════════════════════════════════════════

def run_backtest(stock_code, stock_name, start_date, end_date,
                 period_fast=12, period_slow=26, period_signal=9,
                 atr_period=14, atr_mult=2.0, atr_chandelier_mult=3.0,
                 adx_period=14, adx_threshold=25,
                 use_atr_stop=True, use_chandelier=True, use_adx_filter=True):
    """Run a single backtest and return results dict. Creates its own cerebro."""
    cerebro = bt.Cerebro()

    stock_hfq_df = ak.stock_zh_a_daily(
        symbol=stock_code, adjust="qfq",
        start_date=start_date, end_date=end_date
    ).iloc[:, :6]
    if len(stock_hfq_df) < 130:
        print(f"{stock_code} {stock_name} 行数少于30，跳过。")
        return None
    stock_hfq_df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    stock_hfq_df.index = pd.to_datetime(stock_hfq_df['date'])
    data = bt.feeds.PandasData(dataname=stock_hfq_df)
    cerebro.adddata(data)

    start_cash = 100000
    cerebro.broker.setcash(start_cash)
    cerebro.broker.setcommission(commission=0.002)
    cerebro.broker.set_slippage_perc(0.0001)
    cerebro.addsizer(bt.sizers.AllInSizer, percents=95)

    cerebro.addstrategy(
        fast_macd_strtgy,
        stock_code=stock_code, stock_name=stock_name,
        period_fast=period_fast, period_slow=period_slow, period_signal=period_signal,
        atr_period=atr_period, atr_mult=atr_mult, atr_chandelier_mult=atr_chandelier_mult,
        adx_period=adx_period, adx_threshold=adx_threshold,
        use_atr_stop=use_atr_stop, use_chandelier=use_chandelier, use_adx_filter=use_adx_filter,
    )

    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02,
                        annualize=True, timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
    cerebro.addanalyzer(bt.analyzers.Transactions, _name='txn')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual_return')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='time_return')

    result = cerebro.run()
    port_value = cerebro.broker.getvalue()
    pnl = port_value - start_cash
    return_rate = (pnl / start_cash) * 100

    ta = result[0].analyzers.ta.get_analysis()
    drawdown = result[0].analyzers.drawdown.get_analysis()
    sharpe = result[0].analyzers.sharpe.get_analysis()

    total_trades = ta.get('total', {}).get('closed', 0) if isinstance(ta, dict) else 0
    won_trades = ta.get('won', {}).get('total', 0) if isinstance(ta, dict) else 0
    win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0.0
    max_dd = drawdown.get('max', {}).get('drawdown', 0.0) if isinstance(drawdown, dict) else 0.0
    sharpe_raw = sharpe.get('sharperatio', None) if isinstance(sharpe, dict) else None
    sharpe_ratio = float(sharpe_raw) if sharpe_raw is not None else 0.0

    return {
        'return_rate': return_rate,
        'sharpe': sharpe_ratio,
        'max_drawdown': max_dd,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'port_value': port_value,
        'pnl': pnl,
        'cerebro': cerebro,
        'result': result[0],
    }


def run_single_stock(stock_code, stock_name, start_date, end_date, args):
    """回测单只股票"""
    print(f"\n{'='*60}")
    print(f"回测: {stock_code} {stock_name}")
    print(f"{'='*60}")

    result = run_backtest(
        stock_code, stock_name, start_date, end_date,
        period_fast=args.fast, period_slow=args.slow, period_signal=args.signal,
        atr_period=args.atr_period, atr_mult=args.atr_mult,
        atr_chandelier_mult=args.atr_chandelier_mult,
        adx_period=args.adx_period, adx_threshold=args.adx_threshold,
        use_atr_stop=args.use_atr_stop, use_chandelier=args.use_chandelier,
        use_adx_filter=args.use_adx_filter,
    )

    if result is None:
        return None

    start_cash = 100000
    print(f"Stock: {stock_name}")
    print(f"初始资金: {start_cash}")
    print(f"总资金: {round(result['port_value'], 2)}")
    print(f"净收益: {round(result['pnl'], 2)}")
    print(f"收益率: {result['return_rate']:.2f}%")
    print(f"Sharpe: {result['sharpe']:.2f}")
    print(f"最大回撤: {result['max_drawdown']:.2f}%")
    print(f"交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate']:.1f}%")

    if result['total_trades'] > 0:
        printTradeAnalysis(result['cerebro'], result['result'].analyzers)

    return result


def run_sweep(stock_code, stock_name, start_date, end_date, args):
    """对所有 MACD preset 进行参数扫描对比"""
    print(f"\n{'='*60}")
    print(f"参数扫描: {stock_code} {stock_name}")
    print(f"期间: {start_date} - {end_date}")
    print(f"{'='*60}")

    # Quick check: fetch data once to verify sufficiency
    stock_hfq_df = ak.stock_zh_a_daily(
        symbol=stock_code, adjust="qfq",
        start_date=start_date, end_date=end_date
    ).iloc[:, :6]
    if len(stock_hfq_df) < 130:
        print(f"{stock_code} {stock_name} 行数少于30，跳过。")
        return
    del stock_hfq_df  # run_backtest will fetch again per preset

    results = {}
    for preset_name, preset in MACD_PRESETS.items():
        print(f"\n--- Preset: {preset_name} "
              f"({preset['fast']}/{preset['slow']}/{preset['signal']}) ---")

        result = run_backtest(
            stock_code, stock_name, start_date, end_date,
            period_fast=preset['fast'], period_slow=preset['slow'],
            period_signal=preset['signal'],
            atr_period=args.atr_period, atr_mult=args.atr_mult,
            atr_chandelier_mult=args.atr_chandelier_mult,
            adx_period=args.adx_period, adx_threshold=args.adx_threshold,
            use_atr_stop=args.use_atr_stop, use_chandelier=args.use_chandelier,
            use_adx_filter=args.use_adx_filter,
        )

        if result:
            results[preset_name] = result
            print(f"  收益率: {result['return_rate']:.2f}%, "
                  f"Sharpe: {result['sharpe']:.2f}, "
                  f"最大回撤: {result['max_drawdown']:.2f}%, "
                  f"交易: {result['total_trades']}, "
                  f"胜率: {result['win_rate']:.1f}%")

    # ── Print comparison table ──
    if not results:
        print("无有效结果。")
        return



    # ── Print comparison table ──
    if not results:
        print("无有效结果。")
        return


    # ── Print comparison table ──
    if not results:
        print("无有效结果。")
        return

    header = f"{'Preset':<12} {'Fast':>4} {'Slow':>5} {'Sig':>4}  {'Return%':>8} {'Sharpe':>7} {'MaxDD%':>7} {'Trades':>7} {'WinRate%':>8}"
    print(f"\n{'='*90}")
    print(header)
    print('-' * 90)

    for name, r in results.items():
        p = MACD_PRESETS[name]
        print(f"{name:<12} {p['fast']:>4} {p['slow']:>5} {p['signal']:>4}  "
              f"{r['return_rate']:>7.2f}% {r['sharpe']:>6.2f} {r['max_drawdown']:>6.2f}% "
              f"{r['total_trades']:>7} {r['win_rate']:>7.1f}%")

    # ── Log to file ──
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'parameter_comparison.log')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"\n=== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.write(f"Stock: {stock_code} {stock_name}  Period: {start_date}-{end_date}\n")
        f.write(f"Preset         Fast  Slow  Signal  Return%   Sharpe   MaxDD%   Trades  WinRate%\n")
        for name, r in results.items():
            p = MACD_PRESETS[name]
            f.write(f"{name:<12} {p['fast']:>4} {p['slow']:>5} {p['signal']:>6}  "
                    f"{r['return_rate']:>7.2f}% {r['sharpe']:>6.2f} {r['max_drawdown']:>6.2f}% "
                    f"{r['total_trades']:>7} {r['win_rate']:>7.1f}%\n")
    print(f"\n结果已追加到 {log_path}")


##################################
########## Main #################
##################################

def main():
    parser = argparse.ArgumentParser(description='FastMACD v3.4_ai2 — Enhanced Strategy')

    # Mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--preset', '-p', type=str,
                           choices=list(MACD_PRESETS.keys()),
                           help='MACD parameter preset name')
    mode_group.add_argument('--sweep', action='store_true',
                           help='Run all presets and compare')

    # Data
    parser.add_argument('--stocks_file', '-f', type=str, default='',
                       help='Stock list file path')
    parser.add_argument('--start_date', '-s', type=str, default='20240101',
                       help='Start date (YYYYMMDD)')
    parser.add_argument('--end_date', '-e', type=str,
                       default=datetime.today().strftime('%Y%m%d'),
                       help='End date (YYYYMMDD)')

    # MACD override
    parser.add_argument('--fast', type=int, default=None,
                       help='Override fast EMA period')
    parser.add_argument('--slow', type=int, default=None,
                       help='Override slow EMA period')
    parser.add_argument('--signal', type=int, default=None,
                       help='Override signal period')

    # ATR
    parser.add_argument('--atr-period', type=int, default=14,
                       help='ATR period (default 14)')
    parser.add_argument('--atr-mult', type=float, default=2.0,
                       help='ATR multiplier for stop (default 2.0)')
    parser.add_argument('--atr-chandelier-mult', type=float, default=3.0,
                       help='ATR multiplier for Chandelier Exit (default 3.0)')
    parser.add_argument('--no-atr-stop', action='store_true',
                       help='Disable ATR trailing stop')

    # ADX
    parser.add_argument('--adx-period', type=int, default=14,
                       help='ADX period (default 14)')
    parser.add_argument('--adx-threshold', type=int, default=25,
                       help='ADX threshold (default 25)')
    parser.add_argument('--no-adx-filter', action='store_true',
                       help='Disable ADX trend filter')

    # Chandelier
    parser.add_argument('--no-chandelier', action='store_true',
                       help='Disable Chandelier Exit')

    args = parser.parse_args()

    # Resolve MACD params: preset > explicit > defaults
    if args.preset:
        p = MACD_PRESETS[args.preset]
        args.fast = p['fast']
        args.slow = p['slow']
        args.signal = p['signal']
    else:
        args.fast = args.fast or 12
        args.slow = args.slow or 26
        args.signal = args.signal or 9

    # Feature toggles
    args.use_atr_stop = not args.no_atr_stop
    args.use_chandelier = not args.no_chandelier
    args.use_adx_filter = not args.no_adx_filter

    # Load stocks
    stocks_map = load_stocks_from_file(args.stocks_file)

    if not stocks_map:
        print("使用默认股票列表")
        stocks_map = {
            'sz301209': '联合化学',
            'sh688143': '长盈通',
            'sz300255': '常山药业',
            'sz002364': '中恒电气',
            'sz300607': '拓斯达',
            'sz002131': '利欧股份',
            'sh688521': '芯原股份',
            'sh600580': '卧龙电驱',
            'sz301377': '鼎泰高科',
            'sz002779': '中坚科技',
            'sz002460': '赣锋锂业',
            'sz000858': '五粮液',
            'sz000333': '美的',
            'sh603259': '药明',
            'sz300638': '广和',
            'sz002881': '美格',
            'sh603118': '共进',
            'sh600507': '方大特钢',
            'sh601088': '中国神华',
            'sz300654': '世纪天鸿',
            'sh603011': '合锻智能',
            'sh688095': '福昕软件',
            'sh600895': '张江高科',
            'sh600119': '长江投资',
            'sz301308': '江波龙',
            'sz002466': '天齐锂业',
            'sh688168': '安博通',
            'sh688195': '腾景科技',
            'sz002413': '雷科防务',
            'sz002813': '路畅科技',
            'sz300007': '汉威科技',
            'sz300502': '新易盛',
            'sz000962': '东方钽业',
            'sz002050': '三花智控',
            'sz300842': '帝科股份',
            'sh600198': '大唐电信',
        }

    # Run
    if args.sweep:
        for stock_code in stocks_map:
            stock_name = stocks_map[stock_code]
            run_sweep(stock_code, stock_name, args.start_date, args.end_date, args)
            time.sleep(10)
    else:
        for stock_code in stocks_map:
            stock_name = stocks_map[stock_code]
            run_single_stock(stock_code, stock_name, args.start_date, args.end_date, args)
            time.sleep(10)


if __name__ == "__main__":
    main()
