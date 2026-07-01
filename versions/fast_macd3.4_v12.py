#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import argparse
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))

import backtrader as bt
import akshare as ak
import pandas as pd

from backtrader.indicators import EMA

import send_email
from PrintAnalyzer import *
from datetime import date

######
# Change notes
# v12: +加入趋势过滤（20/60均线、成交量）
#      +增加冷却期，降低重复进出
#      +保留 ATR 趋势止损 + scale-out 分批止盈
#####


class FastMACD(bt.Indicator):
    lines = ('macd', 'signal', 'histo', 'macd_highest')
    params = (('period_fast', 12), ('period_slow', 26), ('period_signal', 9), ('high_period', 120),)

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
        self.l.macd_highest = bt.ind.Highest(self.l.macd, period=self.p.high_period)


class UpCrossSignal(bt.Indicator):
    lines = ('crossOver',)

    def __init__(self):
        fastmacd = FastMACD(self.datas[0])
        self.lines.crossOver = bt.indicators.CrossOver(fastmacd.l.macd, fastmacd.l.signal)

    plotinfo = dict(plot=False)


class fast_macd_strtgy(bt.Strategy):
    params = (
        ('stock_code', ''), ('stock_name', ''),
        ('profit_threshold', 8.0), ('sell_pct', 30.0),
        ('atr_period', 14), ('atr_stop_mult', 3.5),
    )

    def __init__(self):
        self.fastMacd = FastMACD()
        self.upCrossSignal = UpCrossSignal()
        self.sma20 = bt.indicators.SimpleMovingAverage(self.datas[0], period=20)
        self.sma60 = bt.indicators.SimpleMovingAverage(self.datas[0], period=60)
        self.vol20 = bt.indicators.SimpleMovingAverage(self.datas[0].volume, period=20)

        self.data_close = self.datas[0].close
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_volume = self.datas[0].volume

        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.entry_price = None
        self.partial_sold = False
        self.atr = bt.ind.ATR(self.datas[0], period=self.p.atr_period)
        self.highest_since_entry = None
        self.current_stop = None
        self.last_exit_bar = -999999

        self.stock_code = self.params.stock_code
        self.stock_name = self.params.stock_name

    def next(self):
        if self.order:
            return

        if not self.position:
            if (
                self.upCrossSignal.crossOver == 1
                and self.fastMacd.l.signal[0] > 0
                and self.data_close[0] > self.sma20[0]
                and self.sma20[0] > self.sma60[0]
                and self.data_volume[0] > self.vol20[0] * 1.2
                and len(self) - self.last_exit_bar >= 5
            ):
                current_price = self.data_close[0]
                self.log(f"Buy tomorrow! Price: {current_price:.2f}")
                self.email_notify(f"Buy tomorrow! Price: {current_price:.2f}")
                self.entry_price = current_price
                self.highest_since_entry = self.data_high[0]
                self.current_stop = current_price - self.p.atr_stop_mult * self.atr[0]
                self.order = self.buy()
        else:
            sell_reason = None

            if not self.partial_sold and self.entry_price is not None and self.entry_price > 0:
                profit_pct = (self.data_close[0] - self.entry_price) / self.entry_price * 100
                if profit_pct >= self.params.profit_threshold:
                    sell_size = int(self.position.size * self.params.sell_pct / 100)
                    self.log(f"Scaling out: sell {self.params.sell_pct:.0f}% at +{profit_pct:.1f}% profit")
                    self.email_notify(f"Scaling out: sell {self.params.sell_pct:.0f}% at +{profit_pct:.1f}%")
                    self.partial_sold = True
                    if sell_size > 0:
                        self.order = self.sell(size=sell_size)
                        return

            if sell_reason is None and self.entry_price is not None:
                self.highest_since_entry = max(self.highest_since_entry, self.data_high[0])
                atr_stop = self.highest_since_entry - self.p.atr_stop_mult * self.atr[0]
                if self.current_stop is None or atr_stop > self.current_stop:
                    self.current_stop = atr_stop
                if self.data_low[0] <= self.current_stop:
                    sell_reason = f"ATR trailing stop at {self.current_stop:.2f}"

            if sell_reason is not None:
                self.log(f"Sell! {sell_reason}")
                self.email_notify(f"Sell! {sell_reason}")
                self.last_exit_bar = len(self)
                self.entry_price = None
                self.highest_since_entry = None
                self.current_stop = None
                self.partial_sold = False
                self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                self.current_stop = self.buy_price - self.p.atr_stop_mult * self.atr[0]
                self.highest_since_entry = self.buy_price
                self.log(f"Buy executed, Price: {self.buy_price:.2f}, ATR stop: {self.current_stop:.2f}")
            else:
                self.log(f"Sell executed, Price: {order.executed.price:.2f}")
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order {order.status}')
        self.order = None

    def email_notify(self, txt):
        if self.datas[0].datetime.date(0) == date.today():
            dt = self.datas[0].datetime.date(0)
            send = send_email.SendEmail()
            user_list = ['lzl_kni@qq.com']
            sub = 'fmacd_execut'
            content = f"{dt.isoformat()} [v12] {self.stock_code} {self.stock_name} {txt}"
            send.send_mail(user_list, sub, content)

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        if trade.pnl and trade.value:
            return_rate = (trade.pnl / trade.value) * 100
            self.log(f"Operation profit, Gross {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}, Return Rate: {return_rate:.2f}%")

    def log(self, txt, dt=None, doprint=True):
        if doprint:
            dt = dt or self.datas[0].datetime.date(0)
            if dt > (datetime.today() - timedelta(days=90)).date():
                print(f"{datetime.today().strftime('%Y-%m-%d')} {dt.isoformat()} {txt}")


def load_stocks_from_file(filename):
    stocks_map = {}
    if not os.path.exists(filename):
        print(f"错误：文件 {filename} 不存在")
        return stocks_map
    with open(filename, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            stock_code = parts[0].strip()
            stock_name = parts[1].strip() if len(parts) >= 2 else stock_code
            stocks_map[stock_code] = stock_name
    return stocks_map


def main():
    parser = argparse.ArgumentParser(description='股票回测系统')
    parser.add_argument('--stocks_file', '-f', type=str, default='', help='股票列表文件路径')
    parser.add_argument('--start_date', '-s', type=str, default='20240101', help='回测开始日期')
    parser.add_argument('--end_date', '-e', type=str, default=datetime.today().strftime('%Y%m%d'), help='回测结束日期')
    args = parser.parse_args()

    start_date = args.start_date
    end_date = args.end_date
    stocks_map = load_stocks_from_file(args.stocks_file)
    if not stocks_map:
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
            'sz002050': '三花智控', 'sz300842': '帝科股份', 'sh600198': '大唐电信'
        }

    all_results = []
    for stock_code in stocks_map.keys():
        stock_name = stocks_map[stock_code]
        try:
            stock_hfq_df = ak.stock_zh_a_daily(symbol=stock_code, adjust='qfq', start_date=start_date, end_date=end_date).iloc[:, :6]
        except Exception as e:
            print(f"{stock_code} {stock_name} 数据获取失败: {e}")
            continue
        if len(stock_hfq_df) < 30:
            print(f"{stock_code} {stock_name} 行数少于30，跳过。")
            continue
        stock_hfq_df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        stock_hfq_df.index = pd.to_datetime(stock_hfq_df['date'])

        cerebro = bt.Cerebro()
        data = bt.feeds.PandasData(dataname=stock_hfq_df)
        cerebro.adddata(data)
        cerebro.addstrategy(fast_macd_strtgy, stock_code=stock_code, stock_name=stock_name)
        cerebro.broker.setcash(100000)
        cerebro.broker.setcommission(commission=0.002)
        cerebro.broker.set_slippage_perc(0.0001)
        cerebro.addsizer(bt.sizers.AllInSizer, percents=95)

        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02, annualize=True, timeframe=bt.TimeFrame.Days)
        cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
        cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

        result = cerebro.run()
        port_value = cerebro.broker.getvalue()
        pnl = port_value - 100000
        ta = result[0].analyzers.ta.get_analysis()
        dd = result[0].analyzers.drawdown.get_analysis()
        sharpe = result[0].analyzers.sharpe.get_analysis()
        sharp_ratio = sharpe.get('sharperatio', None)
        total_closed = ta.get('total', {}).get('closed', 0)
        won = ta.get('won', {}).get('total', 0)
        win_rate = round(won / total_closed * 100, 1) if total_closed > 0 else 0
        max_dd = dd.get('max', {}).get('drawdown', 0)
        ret_pct = round((port_value / 100000 - 1) * 100, 2)
        all_results.append({'code': stock_code, 'name': stock_name, 'pnl': round(pnl, 2), 'return_pct': ret_pct, 'trades': total_closed, 'win_rate': win_rate, 'sharpe': round(sharp_ratio, 4) if sharp_ratio is not None else None, 'max_dd': round(max_dd, 2)})
        print(f"[{stock_code}] {stock_name:<8} | 收益: {ret_pct:>+7.2f}% | 交易: {total_closed} | 胜率: {win_rate:>5.1f}% | 夏普: {sharp_ratio if sharp_ratio is not None else 'N/A':>8} | 回撤: {max_dd:.2f}%")

    if all_results:
        df = pd.DataFrame(all_results)
        avg_ret = df['return_pct'].mean()
        win_count = len(df[df['pnl'] > 0])
        print(f"\n【总体】平均收益: {avg_ret:>+7.2f}% | 盈利: {win_count}/{len(df)} ({win_count/len(df)*100:.1f}%)")

if __name__ == '__main__':
    main()
