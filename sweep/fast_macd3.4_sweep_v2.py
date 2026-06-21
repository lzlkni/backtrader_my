#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dual parameter sweep for fast_macd3.4.py: upper_mult × MACD thresholds"""

from datetime import datetime, timedelta
import time
import argparse
import os, sys
import csv
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))

import backtrader as bt
import akshare as ak
import pandas as pd

from backtrader.indicators import EMA, Lowest

import send_email
from PrintAnalyzer import *
from datetime import date

class InOutLine(bt.Indicator):
    lines = ('lowest', 'upper',)
    params = (('low_period', 12),)
    plotinfo = dict(subplot=False, plot=True)
    def __init__(self):
        self.l.lowest = bt.ind.Lowest(self.data, period=self.p.low_period)
        self.l.upper = bt.ind.Highest(self.data, period=self.p.low_period)

class FastMACD(bt.Indicator):
    lines = ('macd', 'signal', 'histo', 'macd_highest')
    params = (('period_fast', 12), ('period_slow', 26), ('period_signal', 9), ('high_period', 12),)
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
        ('stock_code', ''), ('stock_name', ''),
        ('upper_mult', 1.5),
        ('macd_high_thresh', 0.6),
        ('macd_low_thresh', 0.3),
    )
    def __init__(self):
        self.sma = bt.indicators.SimpleMovingAverage(self.datas[0], period=120)
        self.fastMacd = FastMACD()
        self.upCrossSignal = UpCrossSignal()
        self.inOutLine = InOutLine()
        self.data_close = self.datas[0].close
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.out_point_up = None
        self.out_point_down = None
        self.stock_code = self.params.stock_code
        self.stock_name = self.params.stock_name

    def next(self):
        if self.order:
            return
        if not self.position:
            if self.upCrossSignal.crossOver == 1 and self.fastMacd.l.signal[0] > 0:
                current_price = self.data_close[0]
                estimated_out_point_up, estimated_out_point_down, estimated_return, estimated_stop_loss, cat, std_scale = self.calculate_stop_loss_target(current_price)
                self.log(f"Buy! Price: {current_price:.2f}, Target: {estimated_out_point_up:.2f}, Stop: {estimated_out_point_down:.2f}, Cat: {cat}")
                self.order = self.buy()
        else:
            if self.data_high[0] >= self.out_point_up * 0.985:
                out_point_down_chk = min(self.data_close[0], self.data_low[0], self.buy_price)
                if out_point_down_chk > self.out_point_down:
                    self.out_point_down = out_point_down_chk
            if self.data_close[0] >= self.out_point_up or self.data_close[0] <= self.out_point_down:
                self.log(f"Sell!")
                self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                self.out_point_up, self.out_point_down, expected_return, stop_loss_return, cat, std_scale = self.calculate_stop_loss_target(self.buy_price)
                self.log(f"Buy exec: {order.executed.price:.2f}, target: {self.out_point_up:.2f}, stop: {self.out_point_down:.2f}")
            else:
                self.log(f"Sell exec: {order.executed.price:.2f}")
        self.order = None

    def calculate_stop_loss_target(self, current_price):
        out_point_down = self.inOutLine.lowest[0] if self.inOutLine.lowest[0] <= current_price else current_price
        std_scale = (current_price - self.inOutLine.lowest[0]) * self.params.upper_mult
        cat = 0
        if std_scale < 0:
            out_point_up = self.inOutLine.upper[0]
        elif self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * self.params.macd_high_thresh:
            out_point_up = current_price + std_scale * 0.3
        elif self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * self.params.macd_low_thresh:
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
            self.log(f"Profit: {trade.pnl:.2f}, Return: {return_rate:.2f}%")

    def log(self, txt, dt=None, doprint=False):
        pass  # suppress output for sweep

def load_stocks_from_file(filename):
    stocks_map = {}
    if not os.path.exists(filename):
        return stocks_map
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                line = line.replace('﻿', '')
                parts = line.split(',')
                if len(parts) >= 2:
                    stocks_map[parts[0].strip()] = parts[1].strip()
                elif len(parts) == 1:
                    stocks_map[parts[0].strip()] = parts[0].strip()
        return stocks_map
    except:
        return stocks_map

def main():
    parser = argparse.ArgumentParser(description='Dual parameter sweep for fast_macd3.4')
    parser.add_argument('--start_date', '-s', type=str, default='20240101')
    parser.add_argument('--end_date', '-e', type=str, default='20250610')
    args = parser.parse_args()

    stocks_map = {
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

    upper_mults = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0]
    macd_highs = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    macd_lows = [0.1, 0.2, 0.3, 0.4, 0.5]

    results = []
    total = len(upper_mults) * len(macd_highs) * len(macd_lows) * len(stocks_map)
    count = 0

    for upper_mult in upper_mults:
        for macd_high in macd_highs:
            for macd_low in macd_lows:
                for stock_code, stock_name in stocks_map.items():
                    count += 1
                    print(f"[{count}/{total}] um={upper_mult}, mh={macd_high}, ml={macd_low}, stock={stock_name}")

                    try:
                        cerebro = bt.Cerebro()
                        stock_hfq_df = ak.stock_zh_a_daily(symbol=stock_code, adjust="qfq",
                                                            start_date=args.start_date, end_date=args.end_date).iloc[:, :6]
                        if len(stock_hfq_df) < 30:
                            continue
                        stock_hfq_df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                        stock_hfq_df.index = pd.to_datetime(stock_hfq_df['date'])

                        cerebro.adddata(bt.feeds.PandasData(dataname=stock_hfq_df))
                        cerebro.addstrategy(fast_macd_strtgy,
                                            stock_code=stock_code, stock_name=stock_name,
                                            upper_mult=upper_mult,
                                            macd_high_thresh=macd_high,
                                            macd_low_thresh=macd_low)
                        cerebro.broker.setcash(100000)
                        cerebro.broker.setcommission(commission=0.002)
                        cerebro.broker.set_slippage_perc(0.0001)
                        cerebro.addsizer(bt.sizers.AllInSizer, percents=95)
                        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
                        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')
                        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe',
                                            riskfreerate=0.02, annualize=True, timeframe=bt.TimeFrame.Days)

                        result = cerebro.run()
                        port_value = cerebro.broker.getvalue()
                        return_rate = (port_value - 100000) / 100000 * 100

                        ta = result[0].analyzers.ta.get_analysis()
                        dd = result[0].analyzers.dd.get_analysis()
                        sharpe = result[0].analyzers.sharpe.get_analysis()

                        total_trades = ta.total.closed if hasattr(ta, 'total') else 0
                        won_trades = ta.won.total if hasattr(ta, 'won') else 0
                        win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0.0
                        max_dd = dd.get('max', {}).get('drawdown', 0.0)
                        sharpe_ratio = sharpe.get('sharperatio', 0.0) if sharpe.get('sharperatio') else 0.0

                        results.append({
                            'upper_mult': upper_mult,
                            'macd_high': macd_high,
                            'macd_low': macd_low,
                            'stock': stock_name,
                            'return': return_rate,
                            'sharpe': sharpe_ratio,
                            'max_dd': max_dd,
                            'trades': total_trades,
                            'win_rate': win_rate,
                        })
                    except Exception as e:
                        print(f"  Error: {e}")
                    time.sleep(1)

    # Save results
    with open('sweep_v2_results.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['upper_mult', 'macd_high', 'macd_low', 'stock',
                                                'return', 'sharpe', 'max_dd', 'trades', 'win_rate'])
        writer.writeheader()
        writer.writerows(results)

    # Analyze
    df = pd.DataFrame(results)
    grouped = df.groupby(['upper_mult', 'macd_high', 'macd_low']).agg({
        'return': 'mean',
        'sharpe': 'mean',
        'max_dd': 'mean',
        'trades': 'mean',
        'win_rate': 'mean',
    }).reset_index()
    grouped = grouped.sort_values('return', ascending=False)

    print("\n=== Top 20 Parameter Combinations ===")
    print(grouped.head(20).to_string(index=False))

if __name__ == "__main__":
    main()
