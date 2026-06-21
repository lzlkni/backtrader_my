# vN: Sector batch backtest runner for v5
from datetime import datetime, timedelta
import time
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))

import backtrader as bt
import akshare as ak
import pandas as pd
from backtrader.indicators import EMA, Highest
from PrintAnalyzer import *
from datetime import date

# ── Indicators from v5 ──

class InOutLine(bt.Indicator):
    lines = ('lowest', 'upper',)
    params = (('low_period', 12),)
    plotinfo = dict(subplot=False, plot=True)
    def __init__(self):
        self.l.lowest = bt.ind.Lowest(self.data, period=self.p.low_period)
        self.l.upper = bt.ind.Highest(self.data, period=self.p.low_period)

class FastMACD(bt.Indicator):
    lines = ('macd', 'signal', 'histo', 'macd_highest')
    params = (('period_fast', 12), ('period_slow', 26), ('period_signal', 9), ('high_period', 12))
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

class NoOpAnalyzer(bt.Analyzer):
    """Sink for analyzers we don't need printed."""
    def get_analysis(self):
        return {}

# ── Strategy (v5) ──

class fast_macd_strtgy(bt.Strategy):
    params = (
        ('stock_code', ''), ('stock_name', ''),
        ('upper_mult', 2.5), ('macd_high_thresh', 0.8), ('macd_low_thresh', 0.4),
        ('macd_high_factor', 0.3), ('macd_low_factor', 0.6),
        ('profit_threshold', 8.0), ('sell_pct', 30.0),
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
        self.entry_price = None
        self.partial_sold = False
        self.highest_since_entry = None
        self.current_stop = None
        self.atr = bt.ind.ATR(self.datas[0], period=14)
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
                self.entry_price = current_price
                self.highest_since_entry = self.data_high[0]
                self.current_stop = estimated_out_point_down
                self.order = self.buy()
        else:
            sell_reason = None
            if not self.partial_sold and self.entry_price is not None and self.entry_price > 0:
                profit_pct = (self.data_close[0] - self.entry_price) / self.entry_price * 100
                if profit_pct >= self.params.profit_threshold:
                    sell_size = int(self.position.size * self.params.sell_pct / 100)
                    self.partial_sold = True
                    if sell_size > 0:
                        self.order = self.sell(size=sell_size)
                        return
            if sell_reason is None:
                if self.data_high[0] >= self.out_point_up * 0.985:
                    out_point_down_chk = min(self.data_close[0], self.data_low[0], self.buy_price)
                    if out_point_down_chk > self.out_point_down:
                        self.out_point_down = out_point_down_chk
                if self.data_close[0] >= self.out_point_up or self.data_close[0] <= self.out_point_down:
                    sell_reason = "target/stop"
            if sell_reason is not None:
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
                self.out_point_up, self.out_point_down, expected_return, stop_loss_return, cat, std_scale = self.calculate_stop_loss_target(self.buy_price)
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            pass
        self.order = None

    def calculate_stop_loss_target(self, current_price):
        out_point_down = self.inOutLine.lowest[0] if self.inOutLine.lowest[0] <= current_price else current_price
        std_scale = (current_price - self.inOutLine.lowest[0]) * 2.5
        cat = 0
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
        expected_return = (out_point_up - current_price) / current_price * 100 if current_price else 0.0
        stop_loss_return = (out_point_down - current_price) / current_price * 100 if current_price else 0.0
        return out_point_up, out_point_down, expected_return, stop_loss_return, cat, std_scale


# ── Main ──

def backtest_stock(stock_code, stock_name, start_date, end_date):
    """Run v5 backtest on a single stock, return result dict."""
    try:
        stock_hfq_df = ak.stock_zh_a_daily(symbol=stock_code, adjust="qfq", start_date=start_date, end_date=end_date).iloc[:, :6]
    except Exception as e:
        return {'code': stock_code, 'name': stock_name, 'error': str(e)}

    if len(stock_hfq_df) < 30:
        return {'code': stock_code, 'name': stock_name, 'error': f'data_rows={len(stock_hfq_df)} < 30'}

    stock_hfq_df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    stock_hfq_df.index = pd.to_datetime(stock_hfq_df['date'])

    cerebro = bt.Cerebro()
    data = bt.feeds.PandasData(dataname=stock_hfq_df)
    cerebro.adddata(data)
    cerebro.addstrategy(fast_macd_strtgy, stock_code=stock_code, stock_name=stock_name)
    start_cash = 100000
    cerebro.broker.setcash(start_cash)
    cerebro.broker.setcommission(commission=0.002)
    cerebro.broker.set_slippage_perc(0.0001)
    cerebro.addsizer(bt.sizers.AllInSizer, percents=95)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02, annualize=True, timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(NoOpAnalyzer, _name='vwr')
    cerebro.addanalyzer(NoOpAnalyzer, _name='sqn')
    cerebro.addanalyzer(NoOpAnalyzer, _name='txn')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    result = cerebro.run()
    port_value = cerebro.broker.getvalue()
    pnl = port_value - start_cash
    ret_pct = (port_value / start_cash - 1) * 100

    r = result[0]
    ta = r.analyzers.ta.get_analysis()
    dd = r.analyzers.drawdown.get_analysis()
    sharpe = r.analyzers.sharpe.get_analysis()
    rets = r.analyzers.returns.get_analysis()

    total_closed = ta.get('total', {}).get('closed', 0)
    won = ta.get('won', {}).get('total', 0)
    lost = ta.get('lost', {}).get('total', 0)

    sharp_ratio = sharpe.get('sharperatio', None)
    max_dd = dd.get('max', {}).get('drawdown', 0)
    max_dd_len = dd.get('max', {}).get('len', 0)

    return {
        'code': stock_code,
        'name': stock_name,
        'pnl': round(pnl, 2),
        'return_pct': round(ret_pct, 2),
        'total_trades': total_closed,
        'winning_trades': won,
        'losing_trades': lost,
        'win_rate': round(won / total_closed * 100, 1) if total_closed > 0 else 0,
        'sharpe': round(sharp_ratio, 4) if sharp_ratio is not None else None,
        'max_drawdown': round(max_dd, 2),
        'max_drawdown_days': max_dd_len,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Sector batch backtest')
    parser.add_argument('--start_date', '-s', type=str, default='20240101')
    parser.add_argument('--end_date', '-e', type=str, default=datetime.today().strftime('%Y%m%d'))
    args = parser.parse_args()

    start_date = args.start_date
    end_date = args.end_date
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Read sector mapping
    mapping_path = os.path.join(base_dir, 'sector_mapping.csv')
    if not os.path.exists(mapping_path):
        print(f'ERROR: {mapping_path} not found')
        return

    mapping = pd.read_csv(mapping_path, encoding='utf-8-sig')
    print(f'Loaded {len(mapping)} stocks with sector mapping')

    results = []
    failed = []

    for i, (_, row) in enumerate(mapping.iterrows()):
        code = row['code']
        name = row['name']
        sector = row['sector']
        
        print(f'[{i+1}/{len(mapping)}] {sector} | {code} {name}')
        sys.stdout.flush()

        r = backtest_stock(code, name, start_date, end_date)
        r['sector'] = sector
        if 'error' in r:
            failed.append(r)
            print(f'  FAILED: {r.get("error")}')
        else:
            results.append(r)
            print(f'  PnL: {r["pnl"]:+.2f} ({r["return_pct"]:+.2f}%) | Trades: {r["total_trades"]} | WR: {r["win_rate"]}% | Sharpe: {r["sharpe"]} | DD: {r["max_drawdown"]}%')
        sys.stdout.flush()

    # ── Summary ──
    df = pd.DataFrame(results)
    df.to_csv(os.path.join(base_dir, 'sector_backtest_results.csv'), index=False, encoding='utf-8-sig')
    print(f'\n\n{"="*80}')
    print(f'BATCH BACKTEST SUMMARY ({len(results)} stocks, {len(failed)} failed)')
    print(f'{"="*80}')

    # Overall stats
    avg_ret = df['return_pct'].mean()
    win_count = len(df[df['pnl'] > 0])
    print(f'Overall: Avg Return = {avg_ret:+.2f}% | Win = {win_count}/{len(df)} ({win_count/len(df)*100:.1f}%)')

    # By sector
    print(f'\n{"="*80}')
    print('BY SECTOR:')
    print(f'{"Sector":<12} {"Count":>5} {"AvgRet":>8} {"WinRate":>8} {"AvgSharpe":>10} {"AvgDD":>7}')
    print('-' * 50)

    sector_stats = []
    for sector, group in df.groupby('sector'):
        avg = group['return_pct'].mean()
        wr = (group['pnl'] > 0).mean() * 100
        asharpe = group['sharpe'].mean()
        add = group['max_drawdown'].mean()
        sector_stats.append({
            'sector': sector, 'count': len(group), 'avg_return': avg,
            'win_rate': wr, 'avg_sharpe': asharpe, 'avg_dd': add
        })

    sector_stats.sort(key=lambda x: x['avg_return'], reverse=True)

    print(f'{"ALL":<12} {len(df):>5} {avg_ret:>+8.2f} {win_count/len(df)*100:>7.1f}% {"":>10} {"":>7}')
    for ss in sector_stats:
        print(f'{ss["sector"]:<12} {ss["count"]:>5} {ss["avg_return"]:>+8.2f}% {ss["win_rate"]:>7.1f}% {ss["avg_sharpe"]:>+10.4f} {ss["avg_dd"]:>6.2f}%')

    print(f'\n{"="*80}')
    print('TOP 10 BEST:')
    top10 = df.sort_values('return_pct', ascending=False).head(10)
    for _, r in top10.iterrows():
        print(f'  {r["sector"]:<10} | {r["code"]} {r["name"]:<8} | Ret: {r["return_pct"]:+.2f}% | Sharpe: {r["sharpe"]} | DD: {r["max_drawdown"]}%')

    print(f'\nBOTTOM 10 WORST:')
    bot10 = df.sort_values('return_pct', ascending=True).head(10)
    for _, r in bot10.iterrows():
        print(f'  {r["sector"]:<10} | {r["code"]} {r["name"]:<8} | Ret: {r["return_pct"]:+.2f}% | Sharpe: {r["sharpe"]} | DD: {r["max_drawdown"]}%')

    if failed:
        print(f'\nFAILED ({len(failed)}):')
        for f in failed:
            print(f'  {f["code"]} {f["name"]}: {f.get("error")}')

    print(f'\nResults saved to sector_backtest_results.csv')


if __name__ == '__main__':
    main()
