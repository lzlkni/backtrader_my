#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# v5_stock_profiler.py - 股票画像: v5收益 vs 特征关联
import os, sys, time, argparse, csv, importlib.util
from collections import OrderedDict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'common'))

# Import v5 strategy (filename has dots, use importlib)
_v5_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'versions', 'fast_macd3.4_v5.py')
_v5_spec = importlib.util.spec_from_file_location('fast_macd3_4_v5', _v5_path)
_v5_mod = importlib.util.module_from_spec(_v5_spec)
sys.modules['fast_macd3_4_v5'] = _v5_mod
_v5_spec.loader.exec_module(_v5_mod)
fast_macd_strtgy = _v5_mod.fast_macd_strtgy

import backtrader as bt
import akshare as ak
import pandas as pd
import numpy as np


def compute_features(df):
    f = OrderedDict()
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['volume'].values
    n = len(close)
    if n < 30:
        return None
    returns = np.diff(close) / close[:-1]
    f['daily_vol'] = round(np.std(returns) * 100, 4)
    f['annual_vol'] = round(np.std(returns) * np.sqrt(252) * 100, 2)
    tr = np.maximum(high[1:] - low[1:], np.abs(high[1:] - close[:-1]))
    tr = np.maximum(tr, np.abs(low[1:] - close[:-1]))
    atr14 = pd.Series(tr).rolling(14).mean().iloc[-1]
    f['atr_pct'] = round((atr14 / close[-1]) * 100, 4) if close[-1] > 0 else 0
    f['hl_ratio'] = round(np.mean((high - low) / close) * 100, 4)
    sma120 = pd.Series(close).rolling(120).mean()
    f['above_sma120_pct'] = round(np.mean(close[119:] > sma120[119:].values) * 100, 2) if n >= 120 else 0
    if n >= 60:
        sma60 = pd.Series(close).rolling(60).mean().values[-60:]
        slope, _ = np.polyfit(np.arange(60), sma60, 1)
        f['trend_slope'] = round(slope / close[-1] * 100 * 252, 2)
    else:
        f['trend_slope'] = 0
    f['up_day_ratio'] = round(np.mean(returns > 0) * 100, 2)
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd = ema12 - ema26
    signal = pd.Series(macd).ewm(span=9, adjust=False).mean().values
    histo = macd - signal
    f['macd_pos_pct'] = round(np.mean(histo > 0) * 100, 2)
    f['macd_histo_mean'] = round(np.mean(histo[120:]) / close[-1] * 100, 4) if n >= 120 else 0
    f['macd_histo_std'] = round(np.std(histo[120:]) / close[-1] * 100, 4) if n >= 120 else 0
    crossovers = np.diff(np.sign(macd - signal))
    f['macd_cross_freq'] = round(np.sum(np.abs(crossovers) > 0) / n * 252, 2)
    f['avg_volume_m'] = round(np.mean(volume) / 1e6, 2)
    f['volume_cv'] = round(np.std(volume) / np.mean(volume), 4) if np.mean(volume) > 0 else 0
    peak = np.maximum.accumulate(close)
    dd = (close - peak) / peak * 100
    f['max_dd'] = round(np.min(dd), 2)
    f['price'] = round(close[-1], 2)
    f['price_range'] = round((np.max(close) - np.min(close)) / np.mean(close) * 100, 2)
    f['price_position'] = round((close[-1] - np.min(close)) / (np.max(close) - np.min(close)) * 100, 2) if np.max(close) > np.min(close) else 50
    return f


def run_v5_on_stock(stock_code, stock_name, start_date, end_date):
    try:
        df = ak.stock_zh_a_daily(symbol=stock_code, adjust='qfq', start_date=start_date, end_date=end_date).iloc[:, :6]
        if len(df) < 30:
            return None
        df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        df.index = pd.to_datetime(df['date'])
        cerebro = bt.Cerebro()
        cerebro.adddata(bt.feeds.PandasData(dataname=df))
        cerebro.addstrategy(fast_macd_strtgy, stock_code=stock_code, stock_name=stock_name)
        cerebro.broker.setcash(100000)
        cerebro.broker.setcommission(commission=0.002)
        cerebro.broker.set_slippage_perc(0.0001)
        cerebro.addsizer(bt.sizers.AllInSizer, percents=95)
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
        start_cash = 100000
        result = cerebro.run()
        pnl = cerebro.broker.getvalue() - start_cash
        return_pct = pnl / start_cash * 100
        ta = result[0].analyzers.ta.get_analysis()
        total = ta.get('total', {}).get('total', 0)
        won = ta.get('won', {}).get('total', 0)
        wr = (won / total * 100) if total > 0 else 0
        return {'v5_return': round(return_pct, 2), 'v5_trades': total, 'v5_win_rate': round(wr, 1)}
    except Exception as e:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', type=str, default='results/bh_results_20260621_101654.csv')
    parser.add_argument('--output', '-o', type=str, default='results/v5_profile_full.csv')
    parser.add_argument('--start', '-s', type=str, default='20240101')
    parser.add_argument('--end', '-e', type=str, default='20250610')
    parser.add_argument('--limit', '-n', type=int, default=0)
    parser.add_argument('--resume', '-r', action='store_true')
    args = parser.parse_args()

    done = set()
    if args.resume and os.path.exists(args.output):
        with open(args.output, 'r', encoding='utf-8-sig') as f:
            done = {r['code'] for r in csv.DictReader(f)}
        print(f'Resuming: {len(done)} already done')

    stocks = []
    with open(args.input, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['code'] not in done:
                stocks.append((row['code'], row['name'], row.get('group', ''), float(row.get('bh_return', 0))))
    if args.limit > 0:
        stocks = stocks[:args.limit]

    print(f'To process: {len(stocks)} stocks')
    if not stocks:
        print('All done!')
        return

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    need_header = not (args.resume and os.path.exists(args.output))
    out_f = open(args.output, 'a', newline='', encoding='utf-8-sig')
    try:
        for i, (code, name, group, bh) in enumerate(stocks):
            sys.stdout.write(f'\r[{i+1}/{len(stocks)}] {code} {name}')
            sys.stdout.flush()
            try:
                df = ak.stock_zh_a_daily(symbol=code, adjust='qfq', start_date=args.start, end_date=args.end).iloc[:, :6]
                if len(df) < 30:
                    print(f' SKIP:{len(df)}rows')
                    time.sleep(3)
                    continue
            except Exception as e:
                print(f' SKIP:{e}')
                time.sleep(3)
                continue
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            features = compute_features(df)
            if features is None:
                print(' SKIP:features')
                time.sleep(3)
                continue
            v5 = run_v5_on_stock(code, name, args.start, args.end)
            if v5 is None:
                print(' SKIP:v5')
                time.sleep(5)
                continue
            row = OrderedDict()
            row['code'] = code; row['name'] = name; row['group'] = group; row['bh_return'] = bh
            row.update(v5); row.update(features)
            w = csv.DictWriter(out_f, fieldnames=row.keys())
            if need_header:
                w.writeheader(); need_header = False
            w.writerow(row); out_f.flush()
            print(f' BH:{bh:+.1f}% V5:{v5["v5_return"]:+.1f}% T:{v5["v5_trades"]} WR:{v5["v5_win_rate"]:.0f}%')
            time.sleep(8)
    finally:
        out_f.close()
    print(f'\nDone. {args.output}')


if __name__ == '__main__':
    main()
