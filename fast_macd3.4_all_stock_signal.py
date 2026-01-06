from datetime import datetime, timedelta
import time
import os
import sys

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
        if self.datas[0].datetime.date(0) == date.today() or self.datas[0].datetime.date(0) == (date.today() - timedelta(days=1)):
        # if str(self.datas[0].datetime.date(0)) == "2023-01-04":
            self.log("sending email")

            # log has signal today
            global signal
            signal = True

            dt = self.datas[0].datetime.date(0)
            send = send_email.SendEmail()
            user_list = ['lzl_kni@qq.com']
            sub = "fmacd_execut"
            content = f"{dt.isoformat()} {stock} {stock_name} {txt}"
            # send.send_mail(user_list, sub, content)

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
start_date = datetime(2024, 1, 1).strftime('%Y%m%d')  # 回测开始时间
# end_date = datetime(2022, 12, 16)  # 回测结束时间
end_date = datetime.today().strftime('%Y%m%d')

# 结果CSV配置
today_str = datetime.today().strftime("%Y%m%d")
results_csv = f'all_stock_hk_analysis_results_raw_{today_str}.csv'
sig_filename = f'filtered_stocks_signal_{today_str}.csv'
processed_stocks = set()
if os.path.exists(results_csv):
    try:
        existing_results = pd.read_csv(results_csv, dtype={'股票代码': str})
        processed_stocks = set(existing_results['股票代码'].astype(str))
        print(f"已读取历史结果，共 {len(processed_stocks)} 只股票。")
    except Exception as e:
        print(f"读取历史结果失败: {e}")
        processed_stocks = set()

success_count = 0
skip_count = 0
fail_count = 0
sig_success_count = 0

# 300568 星源材质
# 002460 赣锋锂业
# 从CSV文件读取股票代码与名称（文件无表头，含注释行）
stocks_file = sys.argv[1] if len(sys.argv) > 1 else 'stocks_all.csv'
stocks_df = pd.read_csv(
    stocks_file,
    header=None,
    names=['code', 'name'],
    comment='#',
)
stocks_df['code'] = stocks_df['code'].astype(str).str.strip()
stocks_df['name'] = stocks_df['name'].astype(str).str.strip()
stocks_map = dict(zip(stocks_df['code'], stocks_df['name']))


global stock
global stock_name
global signal

signal = False

for stock in stocks_map.keys():
    if stock in processed_stocks:
        print(f"{stock} {stocks_map.get(stock)} 已有回测结果，跳过。")
        skip_count += 1
        continue

    # 每只股票开始前重置当日信号标记
    signal = False

    print(stocks_map.get(stock))
    stock_name = stocks_map[stock]
    stock_hfq_df = ak.stock_zh_a_daily(symbol=stock, adjust="qfq", start_date=start_date, end_date=end_date).iloc[:, :6]  # 利用 AkShare 获取A股复权数据
    if len(stock_hfq_df) < 30:
        print(f"{stock} {stock_name} 行数少于30，跳过。")
        fail_count += 1
        continue    


    stock_hfq_df.columns = [
            'date',
            'open',
            'high',
            'low',
            'close',
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
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown', fund=False)
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
        sharpe_analysis = result[0].analyzers.sharpe.get_analysis()
        if sharpe_analysis is not None:
            sharpe_ratio = sharpe_analysis.get('sharperatio', 0)
            if sharpe_ratio is None:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
    except:
        sharpe_ratio = 0
        
    try:
        drawdown_analysis = result[0].analyzers.drawdown.get_analysis()
        if drawdown_analysis is not None:
            max_drawdown = drawdown_analysis.get('max', {}).get('drawdown', 0)
            max_moneydown = drawdown_analysis.get('max', {}).get('moneydown', 0)
            max_drawdown_len = drawdown_analysis.get('max', {}).get('len', 0)
            # 确保值不为None
            if max_drawdown is None:
                max_drawdown = 0
            if max_moneydown is None:
                max_moneydown = 0
            if max_drawdown_len is None:
                max_drawdown_len = 0
            # 确保回撤值为正数（DrawDown返回的是负值）
            if max_drawdown < 0:
                max_drawdown = abs(max_drawdown)
        else:
            max_drawdown = 0
            max_moneydown = 0
            max_drawdown_len = 0
    except Exception as e:
        print(f"获取回撤数据失败: {e}")
        max_drawdown = 0
        max_moneydown = 0
        max_drawdown_len = 0
        
    try:
        ta_analysis = result[0].analyzers.ta.get_analysis()
        if ta_analysis is not None:
            total_trades = len(ta_analysis)
        else:
            total_trades = 0
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
        '最大回撤(%)': round(max_drawdown, 2),
        '最大回撤金额': round(max_moneydown, 2),
        '最大回撤持续天数': max_drawdown_len,
        '交易次数': total_trades
    }
    
    # 逐条写入CSV
   
    try:
        result_df = pd.DataFrame([analysis_result])
        write_header = not os.path.exists(results_csv) or os.path.getsize(results_csv) == 0
        result_df.to_csv(results_csv, mode='a', header=write_header, index=False, encoding='utf-8-sig')
        processed_stocks.add(stock)
        success_count += 1

        # 如果 signal 为 True，将结果写入另一个CSV文件并计数
        if signal:
            # 将 result_df 写入文件，文件名 filtered_stocks_signal_YYYYMMDD.csv，追加模式，根据文件是否存在决定是否写表头
            result_df.to_csv(
                sig_filename,
                mode='a',
                header=not os.path.exists(sig_filename) or os.path.getsize(sig_filename) == 0,
                index=False,
                encoding='utf-8-sig'
            )
            sig_success_count += len(result_df)

    except Exception as e:
        print(f"写入结果失败: {e}")
        fail_count += 1

    # print('Sharp:', result[0].analyzers.SharpeRatio.get_analysis()['sharperatio'] )
    # print('DrawDown: ', result[0].analyzers.DrawDown.get_analysis()['max']['drawdown'])
    # ret = result[0].analyzers.AnnualReturn.get_analysis()
    # print('AnnualReturn: ', result[0].analyzers.AnnualReturn.get_analysis())
    # print('TradeAnalyzer: ', result[0].analyzers.TradeAnalyzer.get_analysis())

    printTradeAnalysis(cerebro, result[0].analyzers)

    # cerebro.plot(style='candlestick', volume=True)  # 画图

    # input('next')
    time.sleep(10)

# 打印最终统计
attempt_count = len(stocks_map) - skip_count
success_rate = (success_count / attempt_count * 100) if attempt_count else 0
print(f"\n=== 分析完成 ===")
print(f"总股票数: {len(stocks_map)}")
print(f"本次跳过（已有结果）: {skip_count}")
print(f"本次尝试: {attempt_count}")
print(f"成功分析: {success_count}")
print(f"分析失败: {fail_count}")
print(f"成功率: {success_rate:.1f}%")
print(f"触发买入信号并写入 {sig_filename} 的股票数: {sig_success_count}")

# 从CSV读取结果并做过滤排序
if os.path.exists(sig_filename) and os.path.getsize(sig_filename) > 0:
    try:
        results_df = pd.read_csv(sig_filename, dtype={'股票代码': str})
        if results_df.empty:
            print("结果文件为空，无法进行过滤与排序。")
        else:
            # 过滤最大回撤小于20%的股票
            filtered_df = results_df[results_df['最大回撤(%)'] < 20].copy()
            
            if filtered_df.empty:
                print("没有满足最大回撤<20%的股票。")
            else:
                # 按收益率、夏普比率、最大回撤排序（收益率降序，夏普比率降序，最大回撤升序）
                filtered_df = filtered_df.sort_values(['收益率(%)', '夏普比率', '最大回撤(%)'],
                                                      ascending=[False, False, True])
                
                # 统一时间戳，方便关联两个输出文件
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # 保存完整分析结果到CSV文件
                output_filename = f'all_stock_hk_analysis_results_{timestamp}.csv'
                filtered_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
                print(f"\n过滤后的分析结果已保存到: {output_filename}")

                # 只保存筛选后的股票代码和名称，便于后续作为股票池使用
                stock_list_filename = f'filtered_stocks_{timestamp}.csv'
                filtered_df[['股票代码', '股票名称']].to_csv(stock_list_filename, index=False, encoding='utf-8-sig')
                print(f"筛选后的股票列表已保存到: {stock_list_filename}")
                
                # 显示过滤后的统计信息
                print(f"\n=== 过滤后统计 ===")
                print(f"最大回撤<20%的股票数: {len(filtered_df)}")

                # 发送邮件（综合排名前10名，所有字段）
                try:
                    send = send_email.SendEmail()
                    user_list = ['lzl_kni@qq.com']
                    sub = "股票分析结果前10名（综合排名）"
                    top_10 = filtered_df.head(10)
                    content = f"过滤后的分析结果已保存到: {output_filename}\n\n"
                    content += f"最大回撤<20%的股票数: {len(filtered_df)}\n"
                    content += f"结果来源: {results_csv}\n\n"
                    content += "综合排名前10名股票（按收益率、夏普比率、最大回撤排序）：\n\n"
                    content += top_10.to_string(index=False)
                    send.send_mail(user_list, sub, content)
                    print("综合排名前10名股票已通过邮件发送到 lzl_kni@qq.com")
                except Exception as e:
                    print(f"发送邮件失败: {e}")
                
                # 显示前10名股票
                print(f"\n=== 综合排名前10名股票（最大回撤<20%） ===")
                top_10 = filtered_df.head(10)
                for _, row in top_10.iterrows():
                    print(f"{row['股票代码']} {row['股票名称']}: 收益率{row['收益率(%)']}% 夏普比率{row['夏普比率']} 最大回撤{row['最大回撤(%)']}% 回撤持续{row['最大回撤持续天数']}天")
    except Exception as e:
        print(f"处理结果文件时发生错误: {e}")
else:
    print("没有可用于过滤/排序的历史结果。")