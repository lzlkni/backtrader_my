#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastMACD 回测 + 热门板块 + AI 分析
N8N 工作流集成入口

用法:
  python fast_macd3.4_ai.py --start_date 20220101

输出: JSON 到 stdout
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))

# 修复 conda 环境 SSL 问题 (Python 3.8+)
conda_lib = os.path.join(os.path.dirname(sys.executable), '..', 'Library', 'bin')
if os.path.exists(conda_lib):
    os.environ['PATH'] = conda_lib + os.pathsep + os.environ.get('PATH', '')
    try:
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(conda_lib)
    except Exception:
        pass

import argparse
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

# ── 所有重量级导入（backtrader / akshare / pandas / importlib）都在函数内 lazy 加载 ──

# ══════════════════════════════════════════════
#   Part 1: 东方财富直连 API（纯 stdlib，秒级）
# ══════════════════════════════════════════════

_EM_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://quote.eastmoney.com/',
}


def _ssl_ctx():
    """创建不验证证书的 SSL 上下文（兼容 conda 环境）"""
    import ssl
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return None


def _em_get(url, timeout=15):
    req = urllib.request.Request(url, headers=_EM_HEADERS)
    try:
        kwargs = {'timeout': timeout}
        if url.startswith('https'):
            kwargs['context'] = _ssl_ctx()
        with urllib.request.urlopen(req, **kwargs) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {'rc': -1, 'error': str(e)}


def get_hot_concept_boards(top_n=5):
    """获取涨幅前 N 个热门概念板块

    使用东方财富 HTTP API（避免 SSL 问题）

    返回: [{'code':'BK0949', 'name':'氦气概念', 'change_pct':3.41}, ...]
    """
    # 使用 push2his HTTP 端点（避免 SSL 问题）
    url = (
        'http://push2his.eastmoney.com/api/qt/clist/get?'
        'cb=&fid=f3&po=1&pz={}&pn=1&np=1&fltt=2&invt=2&'
        'fs=m:90+t:3&fields=f12,f14,f3'
    ).format(top_n)
    time.sleep(2)
    data = _em_get(url)
    if data.get('rc') != 0:
        print('[WARN] 获取概念板块失败: {}'.format(data.get('error', data)), file=sys.stderr)
        return []

    boards = []
    for item in data.get('data', {}).get('diff', []):
        boards.append({
            'code': item.get('f12', ''),
            'name': item.get('f14', ''),
            'change_pct': item.get('f3', 0),
        })
    return boards


def get_board_stocks(board_code, top_n=10):
    """获取指定板块的前 N 只成分股（按涨幅排序）

    返回: [{'code':'sz000858', 'name':'五粮液', 'change_pct':2.5}, ...]
    """
    url = (
        'http://push2his.eastmoney.com/api/qt/clist/get?'
        'cb=&fid=f3&po=1&pz={}&pn=1&np=1&fltt=2&invt=2&'
        'fs=b:{}&fields=f12,f14,f3'
    ).format(top_n, board_code)
    time.sleep(2)
    data = _em_get(url)
    if data.get('rc') != 0:
        print('[WARN] 获取板块 {} 成分股失败: {}'.format(
            board_code, data.get('error', '')), file=sys.stderr)
        return []

    stocks = []
    for item in data.get('data', {}).get('diff', []):
        raw_code = str(item.get('f12', ''))
        name = item.get('f14', '')
        if not raw_code or not name:
            continue
        code_with_prefix = _code_to_prefix(raw_code)
        stocks.append({
            'code': code_with_prefix,
            'name': name,
            'change_pct': item.get('f3', 0),
        })
    return stocks


def _code_to_prefix(raw_code):
    code = str(raw_code).zfill(6)
    return 'sh' + code if code.startswith('6') else 'sz' + code


# ══════════════════════════════════════════════
#   Part 2: 单股回测（lazy 加载重量级库）
# ══════════════════════════════════════════════

def _load_backtest_module():
    """通过 importlib 加载 fast_macd3.4.py（文件名含 . 号）"""
    import importlib.util
    module_path = os.path.join(os.path.dirname(__file__), 'fast_macd3.4.py')
    spec = importlib.util.spec_from_file_location('fast_macd3_4', module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['fast_macd3_4'] = mod
    spec.loader.exec_module(mod)
    return mod


def _get_stock_daily(code, start_date, end_date):
    """通过东方财富 HTTP API 获取股票日线数据（避免 SSL 问题）
    
    返回: pandas DataFrame with columns [date, open, high, low, close, volume]
    """
    import pandas as pd
    
    # 转换代码格式: sz000001 -> 0.000001, sh600000 -> 1.600000
    if code.startswith('sz'):
        secid = '0.' + code[2:]
    else:
        secid = '1.' + code[2:]
    
    url = (
        'http://push2his.eastmoney.com/api/qt/stock/kline/get?'
        'fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&'
        'klt=101&fqt=1&beg={}&end={}&lmt=10000&secid={}'
    ).format(start_date, end_date, secid)
    
    data = _em_get(url)
    if data.get('rc') != 0:
        raise Exception('获取股票数据失败: {}'.format(data.get('error', '')))
    
    klines = data.get('data', {}).get('klines', [])
    if not klines:
        raise Exception('无数据')
    
    rows = []
    for line in klines:
        parts = line.split(',')
        if len(parts) >= 6:
            rows.append({
                'date': parts[0],
                'open': float(parts[1]),
                'high': float(parts[2]),
                'low': float(parts[3]),
                'close': float(parts[4]),
                'volume': float(parts[5]),
            })
    
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df['date'])
    return df


def run_single_backtest(stock_code, stock_name, start_date, end_date):
    """对单只股票运行 FastMACD 回测，返回指标字典"""
    try:
        import backtrader as bt
        import pandas as pd
        bt_mod = _load_backtest_module()
        fast_macd_strtgy = bt_mod.fast_macd_strtgy
    except Exception as e:
        import traceback
        return {'code': stock_code, 'name': stock_name,
                'error': '导入失败: {}'.format(traceback.format_exc(limit=2))}

    try:
        stock_hfq_df = _get_stock_daily(stock_code, start_date, end_date)

        if len(stock_hfq_df) < 30:
            return {'code': stock_code, 'name': stock_name, 'error': '数据不足30行'}

        stock_hfq_df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        stock_hfq_df.index = pd.to_datetime(stock_hfq_df['date'])

        cerebro = bt.Cerebro()
        cerebro.adddata(bt.feeds.PandasData(dataname=stock_hfq_df))
        cerebro.addstrategy(fast_macd_strtgy,
                            stock_code=stock_code,
                            stock_name=stock_name)

        start_cash = 100000
        cerebro.broker.setcash(start_cash)
        cerebro.broker.setcommission(commission=0.002)
        cerebro.broker.set_slippage_perc(0.0001)
        cerebro.addsizer(bt.sizers.AllInSizer, percents=95)

        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(
            bt.analyzers.SharpeRatio, _name='sharpe',
            riskfreerate=0.02, annualize=True,
            timeframe=bt.TimeFrame.Days
        )
        cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')

        result = cerebro.run()
        port_value = cerebro.broker.getvalue()
        analyzers = result[0].analyzers

        ta = analyzers.ta.get_analysis()
        closed_total = (ta.get('total') or {}).get('closed', 0)
        won_total = (ta.get('won') or {}).get('total', 0)
        pnl_net_total = (ta.get('pnl') or {}).get('net', {}).get('total', 0)
        win_rate = (won_total / closed_total * 100) if closed_total > 0 else 0.0

        sharpe = None
        if hasattr(analyzers, 'sharpe'):
            sharpe = (analyzers.sharpe.get_analysis() or {}).get('sharperatio')

        dd = None
        if hasattr(analyzers, 'drawdown'):
            dd = round(((analyzers.drawdown.get_analysis() or {}).get('max') or {}).get('drawdown', 0), 2)

        sqn = None
        if hasattr(analyzers, 'sqn'):
            sqn = (analyzers.sqn.get_analysis() or {}).get('sqn')

        total_return = (port_value - start_cash) / start_cash * 100

        return {
            'code': stock_code,
            'name': stock_name,
            'total_return_pct': round(total_return, 2),
            'sharpe_ratio': round(sharpe, 4) if sharpe is not None else None,
            'max_drawdown_pct': dd,
            'sqn': round(sqn, 4) if sqn is not None else None,
            'total_trades': closed_total,
            'win_rate': round(win_rate, 2),
            'pnl_net': round(pnl_net_total, 2),
        }

    except Exception as e:
        return {'code': stock_code, 'name': stock_name, 'error': str(e)}


# ══════════════════════════════════════════════
#   Part 3: 主入口（N8N JSON 输出）
# ══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='FastMACD 回测 + 热门板块 + AI 分析 (N8N 集成)'
    )
    parser.add_argument('--start_date', '-s', default='20220101')
    parser.add_argument('--end_date', '-e',
                        default=datetime.today().strftime('%Y%m%d'))
    parser.add_argument('--top_sectors', type=int, default=5)
    parser.add_argument('--top_stocks', type=int, default=10)
    parser.add_argument('--sleep', type=float, default=3)
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args()

    result = {
        'date': datetime.today().strftime('%Y-%m-%d'),
        'params': {
            'start_date': args.start_date,
            'end_date': args.end_date,
            'top_sectors': args.top_sectors,
            'top_stocks': args.top_stocks,
        },
        'hot_sectors': [],
        'stocks': [],
        'errors': [],
    }

    # Step 1: 获取热门板块
    if args.debug:
        print('[INFO] 获取热门概念板块...', file=sys.stderr)

    boards = get_hot_concept_boards(top_n=args.top_sectors)
    if not boards:
        print('[WARN] 未获取到任何热门板块，退出', file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False))
        return

    result['hot_sectors'] = boards
    if args.debug:
        for b in boards:
            print('  [板块] {} ({}) 涨幅 {}%'.format(
                b['name'], b['code'], b['change_pct']), file=sys.stderr)

    # Step 2: 获取板块成分股，跨板块去重
    seen = set()
    all_stocks = []

    for board in boards:
        if args.debug:
            print('[INFO] 获取板块 {} 成分股...'.format(board['name']), file=sys.stderr)
        stocks = get_board_stocks(board['code'], top_n=args.top_stocks)

        for s in stocks:
            if s['code'] not in seen:
                seen.add(s['code'])
                s['sector'] = board['name']
                all_stocks.append(s)

    if args.debug:
        print('[INFO] 去重后共 {} 只股票'.format(len(all_stocks)), file=sys.stderr)

    # Step 3: 逐只跑回测
    total = len(all_stocks)
    for idx, s in enumerate(all_stocks, 1):
        if args.debug:
            print('[回测] ({}/{}) {} {} ...'.format(
                idx, total, s['code'], s['name']), file=sys.stderr)

        bt_result = run_single_backtest(
            s['code'], s['name'],
            args.start_date, args.end_date
        )

        bt_result['sector'] = s['sector']
        bt_result['sector_change_pct'] = s['change_pct']

        if 'error' in bt_result:
            result['errors'].append(bt_result)
            if args.debug:
                print('  └─ 失败: {}'.format(bt_result['error']), file=sys.stderr)
        else:
            result['stocks'].append(bt_result)

        if idx < total:
            time.sleep(args.sleep)

    # Step 4: 输出 JSON
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
