from datetime import datetime
import time

import backtrader as bt
import matplotlib.pyplot as plt
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
        # self.l.lowest2 = bt.ind.Lowest(self.data, period=self.p.low_period * 2)
        self.l.upper = self.l.lowest * 1.5



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
    lines = ('macd', 'signal', 'histo')
    params = (('period_fast', 12), ('period_slow', 26), ('period_signal', 9),)
    # params = (('period_fast', 5), ('period_slow', 10), ('period_signal', 15),)
    # params = (('period_fast', 10), ('period_slow', 20), ('period_signal', 7),)

    plotlines = dict(
        histo=dict(_method='bar',
                    alpha=0.50,
                    width=1.0
        ),
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

        # Signal
        signal1 = EMA(self.l.macd, period=self.p.period_signal)
        signal2 = EMA(signal1, period=self.p.period_signal)
        self.l.signal = signal1 * 2 - signal2

        self.l.histo = self.l.macd - self.l.signal


class UpCrossSignal(bt.Indicator):
    lines = ('crossOver',)

    def __init__(self):
        fastmacd = FastMACD(self.datas[0])
        self.lines.crossOver = bt.indicators.CrossOver(fastmacd.l.macd, fastmacd.l.signal)


class fast_macd_strtgy(bt.Strategy):
    # params = (("fast_length", 12), ("slow_length", 26), ("signal_length", 9))

    def __init__(self):
        self.sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=120
        )

        self.fastMacd = FastMACD()
        self.upCrossSignal = UpCrossSignal()
        self.inOutLine = InOutLine()

        # self.atr = bt.ind.ATR(period = 15)
        # self.boll = bt.ind.BollingerBands()
        self.tr = bt.ind.TR()

        self.data_close = self.datas[0].close  # 指定价格序列
        self.data_high = self.datas[0].high  # 指定价格序列
        # 初始化交易指令、买卖价格和手续费
        self.order = None
        self.buy_price = None
        self.buy_comm = None

        self.out_point_up = None
        self.out_point_down = None

    def next(self):


        # print(self.data.datetime.date(0),  self.fastMacd.macd[0], self.fastMacd.signal[0], self.upCrossSignal.crossOver[0], self.fastMacd.histo[0], self.inOutLine.upper[0])

        if self.order:  # 检查是否有指令等待执行,
            return
        # 检查是否持仓
        if not self.position:  # 没有持仓
            # if self.data_close[0] > self.sma[0]:  # 执行买入条件判断：收盘价格上涨突破20日均线

            # if self.upCrossSignal.crossOver == 1 and self.fastMacd.macd[0] > 0.0 and self.fastMacd.signal[0] > 0.0:
            if self.upCrossSignal.crossOver == 1:
                self.order = self.buy()  # 执行买入
                # self.out_point_up = self.inOutLine.lowest[0] * 1.5


                # if self.inOutLine.lowest[0] < self.data_close * 0.8:
                #     self.out_point_down = self.data_close * 0.8
                #     self.out_point_up = self.data_close * 1.3
                # else:
                #     self.out_point_down = self.inOutLine.lowest[0]
                #     self.out_point_up = self.data_close * (
                #                 1 + ((self.data_close - self.inOutLine.lowest[0]) / self.data_close) * 1.5)
        else:
            # if self.data_close[0] < self.sma[0]:  # 执行卖出条件判断：收盘价格跌破20日均线
            # if self.upCrossSignal.crossOver == -1:
            if self.data_close[0] >= self.out_point_up or self.data_close[0] <= self.out_point_down: # 收市价
            # if self.data_high[0] >= self.out_point_up or self.data_high[0] <= self.out_point_down:
                self.order = self.close()  # 执行卖出



    def notify_order(self, order):

        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                #
                # # if self.inOutLine.lowest[0] < self.buy_price * 0.8:
                # if self.inOutLine.lowest[0] < self.buy_price * 0.8 or self.inOutLine.lowest[0] > self.buy_price * 0.95:
                #     self.out_point_down = self.buy_price * 0.8
                #     self.out_point_up = self.buy_price * 1.1
                # elif self.inOutLine.lowest[0] > self.buy_price * 0.95:
                #     self.out_point_down = self.buy_price - self.tr
                #     self.out_point_up = self.buy_price + self.tr * 0.8
                # else:
                #     self.out_point_down = self.inOutLine.lowest[0]
                #     self.out_point_up = self.buy_price * (
                #                 1 + ((self.buy_price - self.inOutLine.lowest[0]) / self.buy_price) * 1.5)

                self.out_point_down = self.inOutLine.lowest[0]
                self.out_point_up = self.buy_price * (
                        1 + ((self.buy_price - self.inOutLine.lowest[0]) / self.buy_price) * 1.5)

                self.log(
                    f"{stock} Buy executed, Price: {order.executed.price: .2f}, Cost: {order.executed.value}, Comm: {order.executed.comm}, target: {self.out_point_up}, stop: {self.out_point_down}, lowest: {self.inOutLine.lowest[0]}, macd: {self.fastMacd.l.signal[0]}"
                )
                self.email_notify(f"Buy executed, Price: {order.executed.price: .2f}, Cost: {order.executed.value}, Comm: {order.executed.comm}, target: {self.out_point_up}, stop: {self.out_point_down}, lowest: {self.inOutLine.lowest[0]}")

            else:
                self.log(
                    f"{stock} Sell executed, Price: {order.executed.price: .2f}, Cost: {order.executed.value}, Comm：{order.executed.comm}"
                )
                self.email_notify(f"Sell executed, Price: {order.executed.price: .2f}, Cost: {order.executed.value}, Comm：{order.executed.comm}")
            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order {order.status}')

        self.order = None

    # If execute is today, send email
    def email_notify(self, txt):
        if self.datas[0].datetime.date(0) == date.today():
        # if str(self.datas[0].datetime.date(0)) == "2023-01-04":
            self.log("sending email")

            dt = self.datas[0].datetime.date(0)
            send = send_email.SendEmail()
            user_list = ['lzl_kni@qq.com']
            sub = "fmacd_execut"
            content = f"{dt.isoformat()} {stock} {stock_name} {txt}"
            send.send_mail(user_list, sub, content)

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f"Operation profit, Gross {trade.pnl}, Net: {trade.pnlcomm}")

    def log(self, txt, dt=None, doprint=True):
        if doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")


########## Main #################

# Prepare data
start_date = datetime(2020, 1, 1)  # 回测开始时间
# end_date = datetime(2022, 12, 16)  # 回测结束时间
end_date = datetime.today()

# 300568 星源材质
# 002460 赣锋锂业

stocks_map = dict([('300568', '星源材质'), ('002460', '赣锋锂业'), ('000858', '五粮液'), ("000333", "美的")])
# stocks_map = dict([('300568', '星源材质')])
# stocks_map = dict([('002460', '赣锋锂业')])
# stocks_map = dict([('000858', '五粮液')])
# stocks_map = dict([('000333', '美的')])

global stock
global stock_name

for stock in stocks_map.keys():
    stock_name = stocks_map[stock]
    stock_hfq_df = ak.stock_zh_a_hist(symbol=stock, adjust="qfq", start_date=start_date, end_date=end_date).iloc[:, :6]  # 利用 AkShare 一行获取复权数据
    stock_hfq_df.columns = [
        'date',
        'open',
        'close',
        'high',
        'low',
        'volume',
    ]

    # stock_hfq_df["stock"] = stock

    stock_hfq_df.index = pd.to_datetime(stock_hfq_df['date'])

    cerebro = bt.Cerebro()  # 初始化回测系统
    data = bt.feeds.PandasData(dataname=stock_hfq_df)  # 加载数据

    cerebro.adddata(data)  # 将数据传入回测系统
    cerebro.addstrategy(fast_macd_strtgy)
    # cerebro.add_signal(bt.SIGNAL_LONGSHORT, UpCrossSignal)
    start_cash = 100000
    cerebro.broker.setcash(start_cash)  # 设置初始资本为 100000
    cerebro.broker.setcommission(commission=0.002)  # 设置交易手续费为 0.2%
    cerebro.broker.set_slippage_perc(0.0001)

    size = bt.sizers.AllInSizer
    cerebro.addsizer(bt.sizers.AllInSizer, percents=95)
    #
    # cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='SharpeRatio')
    # cerebro.addanalyzer(bt.analyzers.DrawDown, _name='DrawDown')
    # cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='AnnualReturn')
    # cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='TradeAnalyzer')

    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02, annualize=True,
                        timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
    cerebro.addanalyzer(bt.analyzers.Transactions, _name='txn')
    cerebro.addanalyzer(bt.analyzers.Transactions, _name='txn')
    cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')

    result = cerebro.run()
    port_value = cerebro.broker.getvalue()  # 获取回测结束后的总资金
    pnl = port_value - start_cash  # 盈亏统计

    print(f"Stock: {stocks_map[stock]}")
    print(f"初始资金: {start_cash}")
    print(f"总资金: {round(port_value, 2)}")
    print(f"净收益: {round(pnl, 2)}")
    # print('Sharp:', result[0].analyzers.SharpeRatio.get_analysis()['sharperatio'] )
    # print('DrawDown: ', result[0].analyzers.DrawDown.get_analysis()['max']['drawdown'])
    # ret = result[0].analyzers.AnnualReturn.get_analysis()
    # print('AnnualReturn: ', result[0].analyzers.AnnualReturn.get_analysis())
    # print('TradeAnalyzer: ', result[0].analyzers.TradeAnalyzer.get_analysis())

    printTradeAnalysis(cerebro, result[0].analyzers)

    # cerebro.plot(style='candlestick', volume=True)  # 画图

    # input('next')
    time.sleep(10)