#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import time
import argparse
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))

import backtrader as bt
# import matplotlib.pyplot as plt
import akshare as ak
import pandas as pd

from backtrader.indicators import EMA, Lowest

import send_email
from PrintAnalyzer import *
from datetime import date

######
# Change notes
# 3.3 Add pre instrustion for buy/sell
# 3.4.1 Fix outpoint
#####


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
    params = (('period_fast', 12), ('period_slow', 26), ('period_signal', 9),('high_period', 12),)

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
        ('upper_mult', 2.5), ('macd_high_thresh', 0.8), ('macd_low_thresh', 0.4),
        ('macd_high_factor', 0.3), ('macd_low_factor', 0.6),
        ('profit_threshold', 8.0), ('sell_pct', 30.0),
        ('atr_period', 14), ('atr_stop_mult', 2.0),
    )

    def __init__(self):
        self.sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=120
        )

        self.fastMacd = FastMACD()
        self.upCrossSignal = UpCrossSignal()
        self.inOutLine = InOutLine()
        self.atr = bt.ind.ATR(self.datas[0], period=self.p.atr_period)

        # self.atr = bt.ind.ATR(period = 15)
        # self.boll = bt.ind.BollingerBands()
        # self.tr = bt.ind.TR()

        self.data_close = self.datas[0].close  # 指定价格序列
        self.data_high = self.datas[0].high  # 指定价格序列
        self.data_low = self.datas[0].low  # 指定价格序列
        # 初始化交易指令、买卖价格和手续费
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.entry_price = None

        # Scaling out state
        self.partial_sold = False
        self.highest_since_entry = None
        self.current_stop = None

        self.out_point_up = None
        self.out_point_down = None

        # 存储股票信息
        self.stock_code = self.params.stock_code
        self.stock_name = self.params.stock_name

    def next(self):
        if self.order:
            return

        if not self.position:
            # ── Buy logic ──
            if self.upCrossSignal.crossOver == 1 and self.fastMacd.l.signal[0] > 0:
                current_price = self.data_close[0]
                estimated_out_point_up, estimated_out_point_down, estimated_return, estimated_stop_loss, cat, std_scale = self.calculate_stop_loss_target(current_price)

                msg = f"Buy tomorrow! Price: {current_price:.2f}, Target: {estimated_out_point_up:.2f}, Stop: {estimated_out_point_down:.2f}, Return: {estimated_return:.2f}%, Cat: {cat}"
                self.log(msg)
                self.email_notify(msg)

                self.entry_price = current_price
                self.highest_since_entry = self.data_high[0]
                self.current_stop = estimated_out_point_down
                self.order = self.buy()

        else:
            # ── Sell logic: Scaling Out + Legacy ──
            sell_reason = None

            # 0) Scaling Out: 盈利达 threshold 时卖出 sell_pct%
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

            # 1) ATR Trailing Stop
            if sell_reason is None and self.entry_price is not None:
                self.highest_since_entry = max(self.highest_since_entry, self.data_high[0])
                atr_stop = self.highest_since_entry - self.p.atr_stop_mult * self.atr[0]
                if self.current_stop is None or atr_stop > self.current_stop:
                    self.current_stop = atr_stop
                if self.data_low[0] <= self.current_stop:
                    sell_reason = f"ATR trailing stop at {self.current_stop:.2f} (mult={self.p.atr_stop_mult})"

            # 2) Legacy InOutLine target/stop (fallback)
            if sell_reason is None:
                if self.data_high[0] >= self.out_point_up * 0.985:
                    out_point_down_chk = min(self.data_close[0], self.data_low[0], self.buy_price)
                    if out_point_down_chk > self.out_point_down:
                        self.out_point_down = out_point_down_chk
                        self.log(f"Out point down revised to {self.out_point_down}")
                        self.email_notify(f"Out point down revised to {self.out_point_down}")

                if self.data_close[0] >= self.out_point_up or self.data_close[0] <= self.out_point_down:
                    sell_reason = f"Legacy target/stop (up={self.out_point_up:.2f}, down={self.out_point_down:.2f})"

            if sell_reason is not None:
                self.log(f"Sell! {sell_reason}")
                self.email_notify(f"Sell! {sell_reason}")
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

                # 使用共用方法计算止盈止损
                self.out_point_up, self.out_point_down, expected_return, stop_loss_return, cat, std_scale = self.calculate_stop_loss_target(self.buy_price)
                
                msg = f"""{self.stock_code} Buy executed, Price: {order.executed.price: .2f}, Cost: {order.executed.value}, target: {self.out_point_up:.2f}, stop: {self.out_point_down:.2f}, expected_return: {expected_return:.2f}%, stop_loss: {stop_loss_return:.2f}%, cat: {cat}, std_scale: {std_scale:.2f} """

                self.log(msg)
                self.email_notify(msg)

            else:
                self.log(
                    f"{self.stock_code} Sell executed, Price: {order.executed.price: .2f}, Cost: {order.executed.value}"
                )
                self.email_notify(f"Sell executed, Price: {order.executed.price: .2f}, Cost: {order.executed.value}")
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
            content = f"{dt.isoformat()} [v6] {self.stock_code} {self.stock_name} {txt}"
            send.send_mail(user_list, sub, content)

    def calculate_stop_loss_target(self, current_price):
        """
        计算止盈止损价格和收益率 (v2: 优化参数)
        返回: (out_point_up, out_point_down, expected_return, stop_loss_return, cat, std_scale)
        """
        out_point_down = self.inOutLine.lowest[0] if self.inOutLine.lowest[0] <= current_price else current_price
        std_scale = (current_price - self.inOutLine.lowest[0]) * 2.5
        cat = 0

        # 设置止盈价格 (使用 params 中的阈值和倍数)
        if std_scale < 0:
            out_point_up = self.inOutLine.upper[0]
        elif self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * self.params.macd_high_thresh:
            out_point_up = current_price + std_scale * self.params.macd_high_factor
        elif self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * self.params.macd_low_thresh:
            out_point_up = current_price + std_scale * self.params.macd_low_factor
            cat = 2
        else:
            out_point_up = current_price + std_scale
            cat = 3

        # 计算收益率
        expected_return = (out_point_up - current_price) / current_price * 100 if current_price else 0.0
        stop_loss_return = (out_point_down - current_price) / current_price * 100 if current_price else 0.0

        return out_point_up, out_point_down, expected_return, stop_loss_return, cat, std_scale

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        
        # 计算收益率
        if trade.pnl and trade.value:
            return_rate = (trade.pnl / trade.value) * 100
            self.log(f"Operation profit, Gross {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}, Return Rate: {return_rate:.2f}%")
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
    例如：
    sz300568,星源材质
    sz002460,赣锋锂业
    sz000858,五粮液
    """
    stocks_map = {}
    
    if not os.path.exists(filename):
        print(f"错误：文件 {filename} 不存在")
        return stocks_map
    
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:  # 使用 utf-8-sig 自动处理BOM
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):  # 跳过空行和注释行
                    continue
                
                # 去除BOM字符
                line = line.replace('\ufeff', '')
                
                parts = line.split(',')
                if len(parts) >= 2:
                    # 格式：股票代码,股票名称
                    stock_code = parts[0].strip()
                    stock_name = parts[1].strip()
                    # 确保股票代码不为空且不是注释
                    if stock_code and not stock_code.startswith('#'):
                        stocks_map[stock_code] = stock_name
                elif len(parts) == 1:
                    # 格式：只有股票代码
                    stock_code = parts[0].strip()
                    # 确保股票代码不为空且不是注释
                    if stock_code and not stock_code.startswith('#'):
                        stocks_map[stock_code] = stock_code  # 使用代码作为名称
                else:
                    print(f"警告：第{line_num}行格式不正确，跳过：{line}")
        
        print(f"成功从 {filename} 加载了 {len(stocks_map)} 只股票")
        
        return stocks_map
        
    except Exception as e:
        print(f"读取文件 {filename} 时出错：{e}")
        return {}







##################################
########## Main #################
##################################

def main():
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='股票回测系统')
    parser.add_argument('--stocks_file', '-f', type=str, default='',
                       help='股票列表文件路径 (默认: stocks.csv)')
    parser.add_argument('--start_date', '-s', type=str, default='20240101',
                       help='回测开始日期 (格式: YYYYMMDD, 默认: 20220101)')
    parser.add_argument('--end_date', '-e', type=str, default=datetime.today().strftime('%Y%m%d'),
                       help='回测结束日期 (格式: YYYYMMDD, 默认: 今天)')
    
    args = parser.parse_args()
    
    # 准备数据
    start_date = args.start_date
    end_date = args.end_date

    # 从文件加载股票列表
    stocks_map = load_stocks_from_file(args.stocks_file)
    
    
    # 如果没有指定文件或文件为空，使用默认股票列表
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
            'sh600580': '卧龙电驱',
            'sz002413': '雷科防务',
            'sz002813': '路畅科技',
            'sz300007': '汉威科技',
            'sz300502': '新易盛',
            'sz000962': '东方钽业',
            'sz002050': '三花智控',
            "sz300842": "帝科股份",
            'sh600198': '大唐电信'
        }
        # stocks_map = {
        #      'sz301377': '鼎泰高科'
        # }
        

    for stock_code in stocks_map.keys():
        
        stock_name = stocks_map[stock_code]
        # stock_hfq_df = ak.stock_zh_a_hist(symbol=stock_code, adjust="qfq", start_date=start_date, end_date=end_date).iloc[:, :6]  # 利用 AkShare 一行获取复权数据
        
        stock_hfq_df = ak.stock_zh_a_daily(symbol=stock_code, adjust="qfq", start_date=start_date, end_date=end_date).iloc[:, :6]
        if len(stock_hfq_df) < 30:
            print(f"{stock_code} {stock_name} 行数少于30，跳过。")
            continue
        stock_hfq_df.columns = [
            'date',
            'open',
            'high',
            'low',
            'close',
            'volume',
        ]

        stock_hfq_df.index = pd.to_datetime(stock_hfq_df['date'])

        cerebro = bt.Cerebro()  # 初始化回测系统
        data = bt.feeds.PandasData(dataname=stock_hfq_df)  # 加载数据

        cerebro.adddata(data)  # 将数据传入回测系统
        cerebro.addstrategy(fast_macd_strtgy, stock_code=stock_code, stock_name=stock_name)
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
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual_return')
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='time_return')

        result = cerebro.run()
        port_value = cerebro.broker.getvalue()  # 获取回测结束后的总资金
        pnl = port_value - start_cash  # 盈亏统计

        print(f"Stock: {stock_name}")
        print(f"初始资金: {start_cash}")
        print(f"总资金: {round(port_value, 2)}")
        print(f"净收益: {round(pnl, 2)}")

        # SQN值解释：
        # SQN > 2.0: 优秀的交易系统
        # SQN 1.6 - 2.0: 良好的交易系统
        # SQN 1.0 - 1.6: 一般的交易系统
        # SQN < 1.0: 较差的交易系统

        printTradeAnalysis(cerebro, result[0].analyzers)
        # 计算并显示最大回撤
        drawdown_analysis = result[0].analyzers.drawdown.get_analysis()
        max_drawdown = drawdown_analysis['max']['drawdown']
        max_drawdown_len = drawdown_analysis['max']['len']
        print(f"最大回撤: {max_drawdown:.2f}%")
        print(f"最大回撤持续时间: {max_drawdown_len} 天")

        # cerebro.plot(style='candlestick', volume=True)  # 画图

        
        time.sleep(10)

if __name__ == "__main__":
    main()
