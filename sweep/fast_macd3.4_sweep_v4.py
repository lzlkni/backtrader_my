#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run remaining parameter combinations for fast_macd3.4 sweep"""

from datetime import datetime, timedelta
import time
import os, sys
import csv
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))

import backtrader as bt
import akshare as ak
import pandas as pd

from backtrader.indicators import EMA, Lowest

class InOutLine(bt.Indicator):
    lines = ('lowest', 'upper',)
    params = (('low_period', 12),)
    def __init__(self):
        self.l.lowest = bt.ind.Lowest(self.data, period=self.p.low_period)
        self.l.upper = bt.ind.Highest(self.data, period=self.p.low_period)

class FastMACD(bt.Indicator):
    lines = ('macd', 'signal', 'histo', 'macd_highest')
    params = (('period_fast', 12), ('period_slow', 26), ('period_signal', 9),)
    def __init__(self):
        f1 = EMA(self.data, period=self.p.period_fast)
        f2 = EMA(f1, period=self.p.period_fast)
        fast = f1 * 2 - f2
        s1 = EMA(self.data, period=self.p.period_slow)
        s2 = EMA(s1, period=self.p.period_slow)
        slow = s1 * 2 - s2
        self.l.macd = fast - slow
        sg1 = EMA(self.l.macd, period=self.p.period_signal)
        sg2 = EMA(sg1, period=self.p.period_signal)
        self.l.signal = sg1 * 2 - sg2
        self.l.macd_highest = bt.ind.Highest(self.l.macd, period=120)

class UpCrossSignal(bt.Indicator):
    lines = ('crossOver',)
    def __init__(self):
        fm = FastMACD(self.datas[0])
        self.lines.crossOver = bt.indicators.CrossOver(fm.l.macd, fm.l.signal)

class Strategy(bt.Strategy):
    params = (('stock_code', ''), ('stock_name', ''),
                ('upper_mult', 1.5), ('macd_high_thresh', 0.6), ('macd_low_thresh', 0.3),)
    def __init__(self):
        self.fm = FastMACD()
        self.uc = UpCrossSignal()
        self.io = InOutLine()
        self.dc = self.datas[0].close
        self.dh = self.datas[0].high
        self.dl = self.datas[0].low
        self.order = None
        self.oup = None
        self.odp = None

    def next(self):
        if self.order: return
        if not self.position:
            if self.uc.crossOver == 1 and self.fm.l.signal[0] > 0:
                self.order = self.buy()
        else:
            if self.dh[0] >= self.oup * 0.985:
                chk = min(self.dc[0], self.dl[0], self.buy_price)
                if chk > self.odp: self.odp = chk
            if self.dc[0] >= self.oup or self.dc[0] <= self.odp:
                self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]: return
        if order.status in [order.Completed] and order.isbuy():
            self.buy_price = order.executed.price
            self.oup, self.odp, _, _, _, _ = self.calc(self.buy_price)
        self.order = None

    def calc(self, cp):
        odp = self.io.lowest[0] if self.io.lowest[0] <= cp else cp
        ss = (cp - self.io.lowest[0]) * self.params.upper_mult
        if ss < 0:
            oup = self.io.upper[0]
        elif self.fm.l.macd[0] > self.fm.l.macd_highest[0] * self.params.macd_high_thresh:
            oup = cp + ss * 0.3
        elif self.fm.l.macd[0] > self.fm.l.macd_highest[0] * self.params.macd_low_thresh:
            oup = cp + ss * 0.5
        else:
            oup = cp + ss
        return oup, odp, 0, 0, 0, 0

    def log(self, *a, **k): pass

def main():
    stocks = {
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

    # Remaining combinations: 1.5 (partial), 1.8, 2.0, 2.5, 3.0
    combos = []
    for um in [1.5, 1.8, 2.0, 2.5, 3.0]:
        for mh in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
            for ml in [0.1, 0.2, 0.3, 0.4, 0.5]:
                # Skip already tested (1.5, 0.4, 0.5 was the last tested)
                if um == 1.5 and mh <= 0.4:
                    continue
                combos.append((um, mh, ml))

    total = len(combos) * len(stocks)
    count = 0

    with open('sweep_v4_results.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['upper_mult', 'macd_high', 'macd_low', 'stock', 'return', 'sharpe', 'max_dd', 'trades', 'win_rate'])

        for um, mh, ml in combos:
            for sc, sn in stocks.items():
                count += 1
                if count % 50 == 0:
                    print(f"[{count}/{total}] um={um}, mh={mh}, ml={ml}, stock={sn}")
                try:
                    cerebro = bt.Cerebro()
                    df = ak.stock_zh_a_daily(symbol=sc, adjust="qfq", start_date='20240101', end_date='20250610').iloc[:, :6]
                    if len(df) < 30: continue
                    df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                    df.index = pd.to_datetime(df['date'])
                    cerebro.adddata(bt.feeds.PandasData(dataname=df))
                    cerebro.addstrategy(Strategy, stock_code=sc, stock_name=sn,
                                        upper_mult=um, macd_high_thresh=mh, macd_low_thresh=ml)
                    cerebro.broker.setcash(100000)
                    cerebro.broker.setcommission(commission=0.002)
                    cerebro.broker.set_slippage_perc(0.0001)
                    cerebro.addsizer(bt.sizers.AllInSizer, percents=95)
                    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
                    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')
                    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sh', riskfreerate=0.02, annualize=True, timeframe=bt.TimeFrame.Days)
                    r = cerebro.run()
                    pv = cerebro.broker.getvalue()
                    ret = (pv - 100000) / 100000 * 100
                    ta = r[0].analyzers.ta.get_analysis()
                    dd = r[0].analyzers.dd.get_analysis()
                    sh = r[0].analyzers.sh.get_analysis()
                    tt = ta.total.closed if hasattr(ta, 'total') else 0
                    wt = ta.won.total if hasattr(ta, 'won') else 0
                    wr = (wt / tt * 100) if tt > 0 else 0.0
                    md = dd.get('max', {}).get('drawdown', 0.0)
                    sr = sh.get('sharperatio', 0.0) if sh.get('sharperatio') else 0.0
                    w.writerow([um, mh, ml, sn, f'{ret:.2f}', f'{sr:.2f}', f'{md:.2f}', tt, f'{wr:.1f}'])
                    del cerebro, r, ta, dd, sh
                except Exception as e:
                    print(f"  Error: {e}")

    print("Done! Analyzing...")
    df = pd.read_csv('sweep_v4_results.csv')
    g = df.groupby(['upper_mult', 'macd_high', 'macd_low']).agg({
        'return': 'mean', 'sharpe': 'mean', 'max_dd': 'mean', 'trades': 'mean', 'win_rate': 'mean',
    }).reset_index().sort_values('return', ascending=False)
    print("\n=== Top 20 (remaining combinations) ===")
    print(g.head(20).to_string(index=False))

if __name__ == "__main__":
    main()
