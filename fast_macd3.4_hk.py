from datetime import datetime, timedelta
import time

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
        # self.tr = bt.ind.TR()

        self.data_close = self.datas[0].close  # 指定价格序列
        self.data_high = self.datas[0].high  # 指定价格序列
        self.data_low = self.datas[0].low  # 指定价格序列
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

            # if self.upCrossSignal.crossOver == 1 and self.fastMacd.l.signal[0] > 0:
            

            
            if self.upCrossSignal.crossOver == 1 and self.fastMacd.l.signal[0] > 0: # If macd > 0            
                # print(f"{self.datas[0].datetime.date(0)} Buy tomorrow!")
                self.email_notify(f"{self.datas[0].datetime.date(0)} Buy tomorrow!")

                self.order = self.buy()  # 执行买入

        else:
            # if self.data_close[0] < self.sma[0]:  # 执行卖出条件判断：收盘价格跌破20日均线
            # if self.upCrossSignal.crossOver == -1:

            # if highest > target revise out_point_down
            if self.data_high[0] >= self.out_point_up * 0.985:
                out_point_down_chk = min(self.data_close[0], self.data_low[0], self.buy_price)
                if out_point_down_chk > self.out_point_down:
                    self.out_point_down = out_point_down_chk
                    # print((f"Out point down revised to {self.out_point_down}"))
                    self.email_notify(f"Out point down revised to {self.out_point_down}")


            if self.data_close[0] >= self.out_point_up or self.data_close[0] <= self.out_point_down:  
            # if self.data_high[0] >= self.out_point_up or self.data_high[0] <= self.out_point_down:
                # print(f"{self.datas[0].datetime.date(0)} Sell tomorrow!")
                self.email_notify(f"{self.datas[0].datetime.date(0)} Sell tomorrow!")
                self.order = self.close()  # 执行卖出

    def notify_order(self, order):

        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm

                self.out_point_down = self.inOutLine.lowest[0]

                cat = 0

                std_scale =   (self.buy_price - self.inOutLine.lowest[0]) * 1.5
                
                ###
                # Set out point up
                if self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * 0.6:
                    self.out_point_up = self.buy_price + std_scale * 0.3
                    cat = 1
                    
                elif self.fastMacd.macd[0] > self.fastMacd.l.macd_highest[0] * 0.3:
                    self.out_point_up = self.buy_price + std_scale * 0.5
                    cat =2
                    
                else:
                    self.out_point_up = self.buy_price + std_scale
                    cat = 3

                msg = f"{stock} Buy executed, Price: {order.executed.price: .2f}, Cost: {order.executed.value}, Comm: {order.executed.comm}, target: {self.out_point_up}, stop: {self.out_point_down}, cat: {cat}, std_scale: {std_scale}"
                self.log(msg)
                self.email_notify(msg)

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
            if dt > (datetime.today() - timedelta(days=300)).date():
                print(f"{dt.isoformat()} {txt}")


########## Main #################
print('start')
# Prepare data
start_date = datetime(2022, 1, 1).strftime('%Y%m%d')  # 回测开始时间
# end_date = datetime(2022, 12, 16)  # 回测结束时间
end_date = datetime.today().strftime('%Y%m%d')

# 300568 星源材质
# 002460 赣锋锂业
# 从CSV文件读取港股代码和名称
try:
    stocks_df = pd.read_csv('hk_stocks.csv')
    # 检查列名并统一格式
    if '代码' in stocks_df.columns and '名称' in stocks_df.columns:
        # 中文列名
        stocks_df['code'] = stocks_df['代码'].astype(str).str.zfill(5)  # 港股代码5位
        stocks_df['name'] = stocks_df['名称']
    elif 'code' in stocks_df.columns and 'name' in stocks_df.columns:
        # 英文列名
        stocks_df['code'] = stocks_df['code'].astype(str).str.zfill(5)  # 港股代码5位
        stocks_df['name'] = stocks_df['name']
    else:
        print("CSV文件格式错误，请确保包含'代码'/'code'和'名称'/'name'列")
        exit(1)
    
    stocks_map = dict(zip(stocks_df['code'], stocks_df['name']))
    print(f"成功读取 {len(stocks_map)} 只港股")
except Exception as e:
    print(f"读取港股列表文件失败: {e}")
    print("请先运行 stock_list_hk.py 生成 hk_stocks.csv 文件")
    exit(1)


# 创建结果存储列表
analysis_results = []

# 添加进度统计
total_stocks = len(stocks_map)
processed_count = 0
success_count = 0
failed_count = 0

global stock
global stock_name

for stock in stocks_map.keys():
    processed_count += 1
    stock_name = stocks_map[stock]
    print(f"[{processed_count}/{total_stocks}] 正在分析: {stock} {stock_name}")
    
    try:
        # 获取港股历史数据 - 使用 stock_hk_hist
        try:
            # 方法1：使用 stock_hk_hist 获取港股历史数据
            stock_hfq_df = ak.stock_hk_hist(symbol=stock, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        except Exception as e1:
            print(f"  尝试 stock_hk_hist 失败: {e1}")
            try:
                # 方法2：使用 stock_hk_daily 获取港股数据
                stock_hfq_df = ak.stock_hk_daily(symbol=stock, adjust="qfq", start_date=start_date, end_date=end_date)
            except TypeError:
                try:
                    # 方法3：使用start和end参数
                    stock_hfq_df = ak.stock_hk_daily(symbol=stock, adjust="qfq", start=start_date, end=end_date)
                except TypeError:
                    # 方法4：不使用日期参数，获取所有数据
                    stock_hfq_df = ak.stock_hk_daily(symbol=stock, adjust="qfq")
                    # 然后按日期筛选
                    if not stock_hfq_df.empty:
                        stock_hfq_df['date'] = pd.to_datetime(stock_hfq_df.iloc[:, 0])
                        stock_hfq_df = stock_hfq_df[(stock_hfq_df['date'] >= start_date) & (stock_hfq_df['date'] <= end_date)]
                        stock_hfq_df = stock_hfq_df.drop('date', axis=1)
        
        # 检查数据是否为空
        if stock_hfq_df.empty:
            print(f"  警告: {stock} {stock_name} 无数据，跳过")
            failed_count += 1
            continue
        
        # 确保数据有足够的列
        if len(stock_hfq_df.columns) >= 6:
            # 只取前6列数据
            stock_hfq_df = stock_hfq_df.iloc[:, :6]

        else:
            print(f"  警告: 数据列数不足，跳过")
            failed_count += 1
            continue
        
        # 设置列名
        stock_hfq_df.columns = [
            'date',
            'open',
            'close',
            'high',
            'low',
            'volume',
        ]
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        

        stock_hfq_df.index = pd.to_datetime(stock_hfq_df['date'])

        
        cerebro = bt.Cerebro()  # 初始化回测系统
        data = bt.feeds.PandasData(dataname=stock_hfq_df)  # 加载数据

        cerebro.adddata(data)  # 将数据传入回测系统
        cerebro.addstrategy(fast_macd_strtgy)
        # cerebro.add_signal(bt.SIGNAL_LONGSHORT, UpCrossSignal)
        start_cash = 100000
        cerebro.broker.setcash(start_cash)  # 设置初始资本为 100000
        cerebro.broker.setcommission(commission=0.005)  # 设置港股交易手续费为 0.5%
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
        cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
        cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')

        result = cerebro.run()
        port_value = cerebro.broker.getvalue()  # 获取回测结束后的总资金
        pnl = port_value - start_cash  # 盈亏统计

        print(f"Stock: {stocks_map[stock]}")
        print(f"初始资金: {start_cash}")
        print(f"总资金: {round(port_value, 2)}")
        print(f"净收益: {round(pnl, 2)}")
        
        # 获取分析结果
        try:
            sharpe_ratio = result[0].analyzers.sharpe.get_analysis().get('sharperatio', 0)
        except:
            sharpe_ratio = 0
            
        try:
            max_drawdown = result[0].analyzers.drawdown.get_analysis().get('max', {}).get('drawdown', 0)
        except:
            max_drawdown = 0
            
        try:
            total_trades = len(result[0].analyzers.ta.get_analysis())
        except:
            total_trades = 0
            
        # 保存分析结果
        analysis_result = {
            '股票代码': stock,
            '股票名称': stock_name,
            '初始资金': start_cash,
            '最终资金': round(port_value, 2),
            '净收益': round(pnl, 2),
            '收益率(%)': round(pnl/start_cash*100, 2),
            '夏普比率': round(sharpe_ratio, 4),
            '最大回撤(%)': round(max_drawdown*100, 2),
            '交易次数': total_trades
        }
        analysis_results.append(analysis_result)
        
        # print('Sharp:', result[0].analyzers.SharpeRatio.get_analysis()['sharperatio'] )
        # print('DrawDown: ', result[0].analyzers.DrawDown.get_analysis()['max']['drawdown'])
        # ret = result[0].analyzers.AnnualReturn.get_analysis()
        # print('AnnualReturn: ', result[0].analyzers.AnnualReturn.get_analysis())
        # print('TradeAnalyzer: ', result[0].analyzers.TradeAnalyzer.get_analysis())

        printTradeAnalysis(cerebro, result[0].analyzers)

        # cerebro.plot(style='candlestick', volume=True)  # 画图

        # input('next')
        time.sleep(10)
        
        success_count += 1
        
    except Exception as e:
        print(f"  错误: {stock} {stock_name} 分析失败: {e}")
        failed_count += 1
        continue

# 打印最终统计
print(f"\n=== 分析完成 ===")
print(f"总股票数: {total_stocks}")
print(f"成功分析: {success_count}")
print(f"分析失败: {failed_count}")
print(f"成功率: {success_count/total_stocks*100:.1f}%")

# 保存分析结果到CSV文件
if analysis_results:
    try:
        results_df = pd.DataFrame(analysis_results)
        # 按收益率排序
        results_df = results_df.sort_values('收益率(%)', ascending=False)
        
        # 保存到CSV文件
        output_filename = f'hk_analysis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        results_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
        print(f"\n分析结果已保存到: {output_filename}")
        
        # 显示前10名股票
        print(f"\n=== 收益率前10名股票 ===")
        top_10 = results_df.head(10)
        for _, row in top_10.iterrows():
            print(f"{row['股票代码']} {row['股票名称']}: {row['收益率(%)']}% (夏普比率: {row['夏普比率']})")
            
    except Exception as e:
        print(f"保存结果时发生错误: {e}")
else:
    print("没有成功分析任何股票")