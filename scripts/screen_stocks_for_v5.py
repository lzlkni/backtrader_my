#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V5 全市场最佳适配股票筛选器 - 最终版
Step 1: 获取全A股列表 (akshare)
Step 2: 快速4维指标评分 (用最近120天数据)
Step 3: Top200 v5回测
Step 4: HTML报告
"""
import os, sys, time, argparse, warnings
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import requests
warnings.filterwarnings('ignore')

os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
_orig = requests.Session.__init__
def _p(self, *a, **k):
    _orig(self, *a, **k)
    self.trust_env = False
requests.Session.__init__ = _p

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results')
PYTHON_EXE = r'D:\Users\lzl_k\AppData\Local\Programs\Python\Python312\venvs\backtrader\Scripts\python.exe'
V5_SCRIPT = os.path.join(PROJECT_DIR, 'versions', 'fast_macd3.4_v5.py')


def fetch_all_stocks():
    """获取全A股列表"""
    print("[1/5] 获取全A股列表...", flush=True)
    import akshare as ak
    df = ak.stock_info_a_code_name()
    df.columns = ['code', 'name']
    original = len(df)
    df = df[~df['name'].str.contains('ST|退|N', na=False)]
    df = df[~df['code'].str.startswith('8')]
    df = df[~df['code'].str.startswith('4')]
    df = df[df['code'].str.match(r'^(0|3|6)')]
    df['code'] = df['code'].astype(str).str.zfill(6)
    print(f"  原始: {original} → 过滤后: {len(df)} 只", flush=True)
    return df.reset_index(drop=True)


def calculate_metrics_batch(stocks_df):
    """分批计算指标 - 每批处理后保存中间结果"""
    import akshare as ak

    total = len(stocks_df)
    print(f"\n[2/5] 计算 {total} 只股票指标...", flush=True)
    t0 = time.time()

    all_results = []
    batch_size = 100
    checkpoint_file = os.path.join(DATA_DIR, 'screening_checkpoint.csv')

    # 从checkpoint恢复
    start_idx = 0
    if os.path.exists(checkpoint_file):
        try:
            prev = pd.read_csv(checkpoint_file)
            all_results = prev.to_dict('records')
            start_idx = len(all_results) // 80 * batch_size  # 近似恢复
            print(f"  从checkpoint恢复: 已有 {len(all_results)} 条", flush=True)
        except:
            pass

    for batch_start in range(start_idx, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = stocks_df.iloc[batch_start:batch_end]

        for _, row in batch.iterrows():
            code = row['code']
            name = row['name']
            try:
                symbol = f'sh{code}' if code.startswith('6') else f'sz{code}'
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=400)).strftime('%Y%m%d')
                d = ak.stock_zh_a_daily(symbol=symbol, adjust="qfq",
                                           start_date=start_date, end_date=end_date)
                if d is None or len(d) < 60:
                    continue

                d = d.iloc[:, :6]
                d.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                c = d['close'].astype(float)
                h = d['high'].astype(float)
                low = d['low'].astype(float)
                n = len(d)
                lb = min(120, n)

                avg_amp = float(((h - low) / c * 100).tail(lb).mean())

                tr = pd.concat([h - low, abs(h - c.shift(1)), abs(low - c.shift(1))], axis=1).max(axis=1)
                pdm = h.diff().clip(lower=0)
                mdm = (-low.diff()).clip(lower=0)
                pdm[pdm < mdm] = 0
                mdm[mdm < pdm] = 0
                atr14 = tr.rolling(14).mean()
                pdi = 100 * (pdm.rolling(14).mean() / atr14)
                mdi = 100 * (mdm.rolling(14).mean() / atr14)
                dx = 100 * abs(pdi - mdi) / (pdi + mdi + 1e-10)
                adx = dx.rolling(14).mean()
                adx_v = adx.dropna()
                adx_ratio = float((adx_v.tail(min(120, len(adx_v))) > 20).mean() * 100) if len(adx_v) >= 30 else 0

                c6m = c.tail(lb)
                rmin = c6m.expanding().min()
                max_rise = float(((c6m - rmin) / rmin * 100).max())

                ann_vol = float(c.pct_change().dropna().std() * np.sqrt(252) * 100)

                all_results.append({
                    'code': code, 'name': name,
                    'avg_amplitude': round(avg_amp, 2),
                    'adx_ratio': round(adx_ratio, 1),
                    'max_rise_6m': round(max_rise, 2),
                    'ann_volatility': round(ann_vol, 2),
                })
            except Exception:
                pass

        # 保存checkpoint
        pd.DataFrame(all_results).to_csv(checkpoint_file, index=False, encoding='utf-8-sig')

        elapsed = time.time() - t0
        done = batch_end
        eta = elapsed / done * (total - done) if done > 0 else 0
        print(f"  [{done}/{total}] valid={len(all_results)} {elapsed:.0f}s ETA {eta:.0f}s", flush=True)

    print(f"  完成: {len(all_results)} 有效 / {total} / {time.time()-t0:.0f}s", flush=True)
    return all_results


def score_stock(m):
    amp = m['avg_amplitude']
    if 2 <= amp <= 8: amp_s = 1.0
    elif amp < 2: amp_s = max(0, amp / 2)
    else: amp_s = max(0, 1 - (amp - 8) / 8)

    adx_s = min(m['adx_ratio'] / 100, 1.0)
    rise = m['max_rise_6m']
    rise_s = min(max(0, rise / 100), 1.0) if rise > 5 else 0

    vol = m['ann_volatility']
    if 25 <= vol <= 60: vol_s = 1.0
    elif vol < 25: vol_s = max(0, vol / 25)
    else: vol_s = max(0, 1 - (vol - 60) / 60)

    total = amp_s * 0.30 + adx_s * 0.30 + rise_s * 0.25 + vol_s * 0.15
    return {**m, 'total_score': round(total, 4)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--top', type=int, default=200)
    parser.add_argument('--start', type=str, default='20240101')
    parser.add_argument('--end', type=str, default='20250610')
    parser.add_argument('--skip-screening', action='store_true')
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"{'='*60}", flush=True)
    print(f" V5 全市场最佳适配股票筛选", flush=True)
    print(f" 候选数: {args.top} | 回测区间: {args.start}-{args.end}", flush=True)
    print(f"{'='*60}", flush=True)

    t_start = time.time()

    if not args.skip_screening:
        stocks_df = fetch_all_stocks()
        metrics = calculate_metrics_batch(stocks_df)

        scored = [score_stock(m) for m in metrics]
        scored.sort(key=lambda x: x['total_score'], reverse=True)

        screened_df = pd.DataFrame(metrics)
        screened_df.to_csv(os.path.join(DATA_DIR, 'screened_stocks.csv'), index=False, encoding='utf-8-sig')

        top_list = scored[:args.top]
        top_df = pd.DataFrame(top_list)
        top_df.to_csv(os.path.join(DATA_DIR, 'top200_candidates.csv'), index=False, encoding='utf-8-sig')
        print(f"  Top {args.top} 候选已保存", flush=True)

        for i, s in enumerate(top_list[:10]):
            print(f"    {i+1}. {s['code']} {s['name']:<8} score={s['total_score']:.4f}", flush=True)
    else:
        top_df = pd.read_csv(os.path.join(DATA_DIR, 'top200_candidates.csv'))
        top_df['code'] = top_df['code'].astype(str).str.zfill(6)
        screened_df = None
        print(f"  已加载已有候选: {len(top_df)} 只", flush=True)

    # Step 3: v5 backtest
    stock_file = os.path.join(DATA_DIR, 'v5_backtest_stocks.csv')
    lines = []
    for _, r in top_df.iterrows():
        code = r['code']
        if code.startswith('6'):
            symbol = f'sh{code}'
        else:
            symbol = f'sz{code}'
        lines.append(f"{symbol},{r['name']}")
    with open(stock_file, 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(lines) + '\n')

    output_csv = os.path.join(DATA_DIR, 'v5_best_fit_results.csv')
    print(f"\n[3/5] 执行 v5 回测...", flush=True)

    import subprocess
    with open(os.path.join(DATA_DIR, 'v5_backtest_output.txt'), 'w', encoding='utf-8') as logf:
        proc = subprocess.run(
            [PYTHON_EXE, V5_SCRIPT, '-f', stock_file, '-s', args.start, '-e', args.end],
            stdout=logf, stderr=subprocess.STDOUT, cwd=PROJECT_DIR, timeout=7200
        )

    print(f"  回测完成 (exit: {proc.returncode})", flush=True)

    result_csv = os.path.join(PROJECT_DIR, 'batch_results_v5_top200.csv')
    if os.path.exists(result_csv):
        os.rename(result_csv, output_csv)

    # Step 4: HTML report
    results = []
    if os.path.exists(output_csv):
        results = pd.read_csv(output_csv)
        if 'return_pct' in results.columns:
            results = results.sort_values('return_pct', ascending=False)

    generate_report(screened_df, top_df, output_csv,
                   os.path.join(RESULTS_DIR, 'v5_best_fit_report.html'))

    elapsed = time.time() - t_start
    print(f"\n完成! 总耗时: {elapsed:.0f}s ({elapsed/60:.1f}min)", flush=True)


def generate_report(screened_df, top_df, results_csv, output_path):
    results = []
    if os.path.exists(results_csv):
        results = pd.read_csv(results_csv)
        if 'return_pct' in results.columns:
            results = results.sort_values('return_pct', ascending=False)

    c = lambda v: '#27ae60' if v > 0 else '#e74c3c'
    html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<style>
body{{font-family:'Microsoft YaHei',sans-serif;max-width:1200px;margin:0 auto;padding:20px;background:#f5f6fa;color:#2c3e50}}
h1{{color:#2c3e50;border-bottom:3px solid #3498db;padding-bottom:10px}}
h2{{color:#34495e;margin-top:30px;border-left:4px solid #3498db;padding-left:12px}}
table{{width:100%;border-collapse:collapse;margin:12px 0;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
th{{background:#3498db;color:#fff;padding:10px 12px;text-align:left;font-size:13px}}
td{{padding:8px 12px;border-bottom:1px solid #eee;font-size:13px}}
tr:hover{{background:#f0f7ff}}
.pos{{color:#27ae60;font-weight:bold}}
.neg{{color:#e74c3c;font-weight:bold}}
.summary-box{{background:#fff;padding:16px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08);margin:12px 0}}
.metric{{display:inline-block;margin:8px 16px 8px 0}}
.metric-label{{font-size:12px;color:#7f8c8d}}
.metric-value{{font-size:20px;font-weight:bold}}
</style></head><body>
<h1>V5 全市场最佳适配股票筛选报告</h1>
<p style="color:#7f8c8d">生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")} | 候选池: Top 200 | 回测区间: 2024-01-01 ~ 2025-06-10</p>
'''

    if len(results) > 0 and 'return_pct' in results.columns:
        avg_ret = results['return_pct'].mean()
        win_n = len(results[results['return_pct'] > 0])
        win_r = win_n / len(results) * 100
        med_ret = results['return_pct'].median()
        avg_sh = results['sharpe'].mean() if 'sharpe' in results.columns else 0
        avg_dd = results['max_dd'].mean() if 'max_dd' in results.columns else 0
        clr = '#27ae60' if avg_ret > 0 else '#e74c3c'
        html += f'''
<div class="summary-box">
  <h2 style="margin-top:0;border:none;padding:0">总体统计</h2>
  <div class="metric"><div class="metric-label">平均收益</div><div class="metric-value" style="color:{clr}">{avg_ret:+.2f}%</div></div>
  <div class="metric"><div class="metric-label">中位数收益</div><div class="metric-value" style="color:{clr}">{med_ret:+.2f}%</div></div>
  <div class="metric"><div class="metric-label">胜率</div><div class="metric-value" style="color:{'#27ae60' if win_r >= 50 else '#e74c3c'}">{win_n}/{len(results)} ({win_r:.1f}%)</div></div>
  <div class="metric"><div class="metric-label">平均夏普</div><div class="metric-value">{avg_sh:.3f}</div></div>
  <div class="metric"><div class="metric-label">平均最大回撤</div><div class="metric-value" style="color:#e74c3c">{avg_dd:.2f}%</div></div>
</div>
'''
        html += '<h2>TOP 20 V5 最佳适配股票</h2>'
        html += '<table><tr><th>#</th><th>代码</th><th>名称</th><th>收益率</th><th>胜率</th><th>夏普</th><th>最大回撤</th><th>交易次数</th></tr>'
        for i, (_, r) in enumerate(results.head(20).iterrows()):
            ret = r.get('return_pct', 0)
            cls = 'pos' if ret > 0 else 'neg'
            wr = r.get('win_rate', 0)
            sh = r.get('sharpe', None)
            sh_s = f'{sh:.3f}' if sh is not None and not np.isnan(sh) else 'N/A'
            dd = r.get('max_dd', 0)
            nm = r.get('name', '')
            html += f'<tr><td>{i+1}</td><td>{r["code"]}</td><td>{nm}</td><td class="{cls}">{ret:+.2f}%</td><td class="{"pos" if wr >= 50 else "neg"}">{wr:.1f}%</td><td>{sh_s}</td><td class="neg">{dd:.2f}%</td><td>{int(r.get("trades", 0))}</td></tr>'
        html += '</table>'

    if len(results) > 0 and 'return_pct' in results.columns and len(results) > 20:
        html += '<h2>Bottom 10</h2>'
        html += '<table><tr><th>#</th><th>代码</th><th>名称</th><th>收益率</th><th>胜率</th><th>夏普</th><th>最大回撤</th></tr>'
        for i, (_, r) in enumerate(results.tail(10).iterrows()):
            ret = r.get('return_pct', 0)
            cls = 'pos' if ret > 0 else 'neg'
            nm = r.get('name', '')
            sh = r.get('sharpe', None)
            sh_s = f'{sh:.3f}' if sh is not None and not np.isnan(sh) else 'N/A'
            dd = r.get('max_dd', 0)
            html += f'<tr><td>{i+1}</td><td>{r["code"]}</td><td>{nm}</td><td class="{cls}">{ret:+.2f}%</td><td>{r.get("win_rate", 0):.1f}%</td><td>{sh_s}</td><td class="neg">{dd:.2f}%</td></tr>'
        html += '</table>'

    if screened_df is not None and len(screened_df) > 0:
        html += '<h2>筛选指标分布 (全市场)</h2>'
        html += '<table><tr><th>指标</th><th>均值</th><th>中位数</th><th>P25</th><th>P75</th><th>P90</th></tr>'
        for col, label in [('avg_amplitude', '日均振幅(%)'), ('adx_ratio', 'ADX>20占比(%)'),
                          ('max_rise_6m', '6月最大涨幅(%)'), ('ann_volatility', '年化波动率(%)')]:
            if col in screened_df.columns:
                v = screened_df[col].dropna()
                html += f'<tr><td>{label}</td><td>{v.mean():.2f}</td><td>{v.median():.2f}</td><td>{v.quantile(.25):.2f}</td><td>{v.quantile(.75):.2f}</td><td>{v.quantile(.90):.2f}</td></tr>'
        html += '</table>'

    html += '</body></html>'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  报告已保存: {output_path}", flush=True)


if __name__ == '__main__':
    main()
