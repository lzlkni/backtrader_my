import os, sys, numpy as np, pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results')

screened_df = pd.read_csv(os.path.join(DATA_DIR, 'screened_stocks.csv'))
top_df = pd.read_csv(os.path.join(DATA_DIR, 'top200_candidates.csv'))
top_df['code'] = top_df['code'].astype(str).str.zfill(6)
results_csv = os.path.join(DATA_DIR, 'v5_best_fit_results.csv')
output_path = os.path.join(RESULTS_DIR, 'v5_best_fit_report.html')

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
<p style="color:#7f8c8d">生成时间: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")} | 候选池: Top 200 | 回测区间: 2024-01-01 ~ 2025-06-10</p>
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
print(f"报告已保存: {output_path}")
print(f"结果数: {len(results)}")
if len(results) > 0:
    print(f"平均收益: {results['return_pct'].mean():+.2f}%")
    print(f"胜率: {(results['return_pct'] > 0).sum()}/{len(results)} ({(results['return_pct'] > 0).mean()*100:.1f}%)")
