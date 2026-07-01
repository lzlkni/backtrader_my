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
# v9: +分批止盈比例递减 (3层: +8%/30% → +15%/20% → +25%/20%)
#     +追涨加仓 (右侧加仓: 每层卖出后趋势延续则加回50%仓位)
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
        # 分批止盈比例递减 (profit%, sell%)
        ('scale_tier1_profit', 8.0), ('scale_tier1_sell', 30.0),
        ('scale_tier2_profit', 15.0), ('scale_tier2_sell', 20.0),
        ('scale_tier3_profit', 25.0), ('scale_tier3_sell', 20.0),
        # 追涨加仓: 卖出一层后趋势延续 +n% 则加回仓位
        ('pyramid_reentry_pct', 5.0),
        ('pyramid_size_pct', 50.0),
        # 保留原单次止盈参数（备选回退）
        ('profit_threshold', 8.0), ('sell_pct', 30.0),
    )
    
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
        self.entry_price = None

        # Scaling out state (v9 multi-tier)
        self.scale_tier = 0               # 0=未卖, 1/2/3=已卖第N层
        self.initial_pos_size = 0         # 买入时的仓位大小
        self.pyramid_added = False        # 是否已经追涨加仓
        self.highest_since_entry = None
        self.current_stop = None
        self.atr = bt.ind.ATR(self.datas[0], period=14)

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
            # ── v9 Sell logic: Multi-tier Scaling Out + Pyramiding + Legacy ──
            sell_reason = None
            profit_pct = ((self.data_close[0] - self.entry_price) / self.entry_price * 100
                          if self.entry_price and self.entry_price > 0 else 0)

            # 更新最高价跟踪
            if self.highest_since_entry is None or self.data_high[0] > self.highest_since_entry:
                self.highest_since_entry = self.data_high[0]

            # ── 0) 分批止盈比例递减 ──
            ALL_TIERS = 3
            tier_params = [
                (1, self.params.scale_tier1_profit, self.params.scale_tier1_sell),
                (2, self.params.scale_tier2_profit, self.params.scale_tier2_sell),
                (3, self.params.scale_tier3_profit, self.params.scale_tier3_sell),
            ]
            for tier, profit_thresh, sell_pct in tier_params:
                if self.scale_tier == tier - 1 and profit_pct >= profit_thresh:
                    sell_size = int(self.position.size * sell_pct / 100)
                    self.scale_tier = tier
                    if self.scale_tier == 1:
                        self.initial_pos_size = self.position.size
                        # 第1层止盈时抬高legacy停损，允许价格飞更远
                        self.out_point_up = max(
                            self.out_point_up,
                            self.entry_price * (1 + self.params.scale_tier3_profit / 100 * 2)
                        ) if self.out_point_up else self.entry_price * 1.5
                    self.log(f"Scaling out tier {tier}: sell {sell_pct:.0f}% at +{profit_pct:.1f}% profit")
                    self.email_notify(f"Scale tier {tier}: +{profit_pct:.1f}% sell {sell_pct:.0f}%")
                    if sell_size > 0:
                        self.order = self.sell(size=sell_size)
                        return

            # ── 1) 追涨加仓 ──
            if (self.scale_tier > 0 and not self.pyramid_added
                    and self.data_close[0] >= self.entry_price * (1 + self.params.pyramid_reentry_pct / 100)
                    and self.fastMacd.l.signal[0] > 0):
                reentry_size = int(self.initial_pos_size * self.params.pyramid_size_pct / 100)
                if reentry_size > 0 and self.broker.getcash() > reentry_size * self.data_close[0]:
                    self.log(f"Pyramid add: buy {self.params.pyramid_size_pct:.0f}% at {self.data_close[0]:.2f}")
                    self.email_notify(f"Pyramid add: +{profit_pct:.1f}% buy back {self.params.pyramid_size_pct:.0f}%")
                    self.pyramid_added = True
                    self.order = self.buy(size=reentry_size)
                    return

            # ── 2) Legacy 止盈/止损 (仅当所有分批止盈层都完成或未触发时检查) ──
            max_tier_profit = max(p[1] for p in tier_params)
            # 如果还未完成所有分批层，提高legacy止盈门槛 = 最高层 × 2，避免过早截断
            effective_up = self.out_point_up
            if self.scale_tier < ALL_TIERS and self.scale_tier > 0:
                effective_up = self.entry_price * (1 + max_tier_profit / 100 * 1.5) if self.entry_price else self.out_point_up

            if self.data_high[0] >= effective_up * 0.985:
                out_point_down_chk = min(self.data_close[0], self.data_low[0], self.buy_price)
                if out_point_down_chk > self.out_point_down:
                    self.out_point_down = out_point_down_chk

            if self.data_close[0] >= effective_up or self.data_close[0] <= self.out_point_down:
                sell_reason = f"Target/stop (up={effective_up:.2f}, down={self.out_point_down:.2f})"

            if sell_reason is not None:
                self.log(f"Sell! {sell_reason}")
                self.email_notify(f"Sell! {sell_reason}")
                self.entry_price = None
                self.highest_since_entry = None
                self.current_stop = None
                self.scale_tier = 0
                self.initial_pos_size = 0
                self.pyramid_added = False
                self.order = self.close()

    def notify_order(self, order):

        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm

                # 重置 v9 分批止盈状态
                self.scale_tier = 0
                self.initial_pos_size = self.position.size
                self.pyramid_added = False

                # 使用共用方法计算止盈止损
                self.out_point_up, self.out_point_down, expected_return, stop_loss_return, cat, std_scale = self.calculate_stop_loss_target(self.buy_price)
                
                msg = f"""{self.stock_code} Buy executed, Price: {order.executed.price: .2f}, Cost: {order.executed.value}, target: {self.out_point_up:.2f}, stop: {self.out_point_down:.2f}, expected_return: {expected_return:.2f}%, stop_loss: {stop_loss_return:.2f}%, cat: {cat}, std_scale: {std_scale:.2f} """

                self.log(msg)
                self.email_notify(msg)

            else:
                # Sell complete → reset v9 state
                self.entry_price = None
                self.highest_since_entry = None
                self.scale_tier = 0
                self.initial_pos_size = 0
                self.pyramid_added = False
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
            content = f"{dt.isoformat()} [v9] {self.stock_code} {self.stock_name} {txt}"
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
    文件格式（支持3种）：
      1) "股票代码,股票名称"               -> group=None
      2) "股票代码"                        -> group=None, name=code
      3) "股票代码,股票名称,板块/分组"       -> group=板块
    例如：
    sz300568,星源材质
    sz002460,赣锋锂业,有色金属
    """
    stocks_map = {}
    group_map = {}
    
    if not os.path.exists(filename):
        print(f"错误：文件 {filename} 不存在")
        return stocks_map, group_map
    
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                line = line.replace('\ufeff', '')
                
                parts = line.split(',')
                stock_code = parts[0].strip()
                if not stock_code or stock_code.startswith('#'):
                    continue
                
                if len(parts) >= 3:
                    # code, name, group
                    stock_name = parts[1].strip()
                    stock_group = parts[2].strip()
                    stocks_map[stock_code] = stock_name
                    group_map[stock_code] = stock_group
                elif len(parts) >= 2:
                    stock_name = parts[1].strip()
                    stocks_map[stock_code] = stock_name
                else:
                    stocks_map[stock_code] = stock_code
        
        print(f"成功从 {filename} 加载了 {len(stocks_map)} 只股票")
        if group_map:
            groups = set(group_map.values())
            print(f"包含 {len(groups)} 个分组: {', '.join(groups)}")
        
        return stocks_map, group_map
        
    except Exception as e:
        print(f"读取文件 {filename} 时出错：{e}")
        return {}, {}







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
    stocks_map, group_map = load_stocks_from_file(args.stocks_file)
    
    # 如果没有指定文件或文件为空，使用默认股票列表
    if not stocks_map:
        print("使用默认股票列表")
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
            'sz002050': '三花智控', "sz300842": "帝科股份", 'sh600198': '大唐电信'
        }

    # 收集结果用于分组分析
    all_results = []
    
    for stock_code in stocks_map.keys():
        
        stock_name = stocks_map[stock_code]
        # stock_hfq_df = ak.stock_zh_a_hist(symbol=stock_code, adjust="qfq", start_date=start_date, end_date=end_date).iloc[:, :6]  # 利用 AkShare 一行获取复权数据
        
        try:
            stock_hfq_df = ak.stock_zh_a_daily(symbol=stock_code, adjust="qfq", start_date=start_date, end_date=end_date).iloc[:, :6]
        except Exception as e:
            print(f"{stock_code} {stock_name} 数据获取失败: {e}")
            continue
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
        port_value = cerebro.broker.getvalue()
        pnl = port_value - start_cash

        # 提取分析器数据
        ta = result[0].analyzers.ta.get_analysis()
        dd = result[0].analyzers.drawdown.get_analysis()
        sharpe = result[0].analyzers.sharpe.get_analysis()
        sharp_ratio = sharpe.get('sharperatio', None)

        total_closed = ta.get('total', {}).get('closed', 0)
        won = ta.get('won', {}).get('total', 0)
        lost = ta.get('lost', {}).get('total', 0)
        win_rate = round(won / total_closed * 100, 1) if total_closed > 0 else 0
        max_dd = dd.get('max', {}).get('drawdown', 0)
        max_dd_len = dd.get('max', {}).get('len', 0)

        group = group_map.get(stock_code, '')
        ret_pct = round((port_value / start_cash - 1) * 100, 2)

        # 存入结果
        all_results.append({
            'code': stock_code, 'name': stock_name, 'group': group,
            'pnl': round(pnl, 2), 'return_pct': ret_pct,
            'trades': total_closed, 'win_rate': win_rate,
            'sharpe': round(sharp_ratio, 4) if sharp_ratio is not None else None,
            'max_dd': round(max_dd, 2), 'max_dd_days': max_dd_len,
        })

        # 单只股票简略输出
        print(f"[{stock_code}] {stock_name:<8} | 收益: {ret_pct:>+7.2f}% | 交易: {total_closed} | 胜率: {win_rate:>5.1f}% | 夏普: {sharp_ratio if sharp_ratio is not None else 'N/A':>8} | 回撤: {max_dd:.2f}%")

    # ════════════════════════════════════════
    # 分组汇总
    # ════════════════════════════════════════
    if all_results:
        df = pd.DataFrame(all_results)
        # 保存原始明细
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        df.to_csv(f'results/batch_results_{ts}.csv', index=False, encoding='utf-8-sig')
        print(f"\n明细已保存到 batch_results_{ts}.csv")

        print(f"\n{'='*70}")
        print(f" 批量回测汇总 — {len(df)} 只股票")
        print(f"{'='*70}")

        # 总体统计
        avg_ret = df['return_pct'].mean()
        win_count = len(df[df['pnl'] > 0])
        print(f"【总体】平均收益: {avg_ret:>+7.2f}% | 盈利: {win_count}/{len(df)} ({win_count/len(df)*100:.1f}%)")

        # 按组分组的统计 —— 仅当有分组信息时
        has_group = df['group'].notna().any() and (df['group'] != '').any()
        if has_group:
            print(f"\n{'='*70}")
            print(f" 按分组分析:")
            print(f"{'分组':<14} {'数量':>4} {'平均收益':>10} {'胜率':>8} {'平均夏普':>10} {'平均回撤':>8}")
            print(f"{'-'*56}")
            
            grp_stats = []
            for g, sub in df.groupby('group'):
                avg = sub['return_pct'].mean()
                wr = (sub['pnl'] > 0).mean() * 100
                asharpe = sub['sharpe'].mean()
                add = sub['max_dd'].mean()
                grp_stats.append((g, len(sub), avg, wr, asharpe, add))
            
            grp_stats.sort(key=lambda x: x[2], reverse=True)
            for g, n, avg, wr, asharpe, add in grp_stats:
                print(f"{g:<14} {n:>4} {avg:>+9.2f}% {wr:>6.1f}% {asharpe:>+9.4f} {add:>6.2f}%")
            print(f"{'-'*56}")

        # TOP/BOTTOM
        print(f"\n{'='*70}")
        print(f" TOP 5:")
        for _, r in df.sort_values('return_pct', ascending=False).head(5).iterrows():
            g = f" ({r['group']})" if r['group'] else ''
            print(f"  +{r['return_pct']:>6.2f}% | {r['code']} {r['name']}{g} | Sharpe={r['sharpe']} | DD={r['max_dd']}%")

        print(f"\n BOTTOM 5:")
        for _, r in df.sort_values('return_pct', ascending=True).head(5).iterrows():
            g = f" ({r['group']})" if r['group'] else ''
            print(f"  {r['return_pct']:>+7.2f}% | {r['code']} {r['name']}{g} | Sharpe={r['sharpe']} | DD={r['max_dd']}%")

if __name__ == "__main__":
    main()
