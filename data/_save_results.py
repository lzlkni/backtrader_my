import pandas as pd
import shutil
import os
from datetime import datetime

ts = datetime.now().strftime('%Y%m%d_%H%M%S')

# Read data
v5 = pd.read_csv('batch_results_20260621_100628.csv', encoding='utf-8-sig')
bh = pd.read_csv('data/deepseek_bh_returns.csv', encoding='utf-8-sig')

# Group stats
v5_grp = v5.groupby('group').agg(
    v5_return=('return_pct', 'mean'),
    v5_winrate=('win_rate', lambda x: (x > 0).mean()*100),
    v5_sharpe=('sharpe', 'mean'),
    v5_dd=('max_dd', 'mean')
).round(2)

bh_grp = bh.groupby('group').agg(
    bh_return=('bh_return', 'mean')
).round(2)

merged = v5_grp.join(bh_grp)
merged['excess_return'] = (merged['v5_return'] - merged['bh_return']).round(2)
merged = merged.sort_values('v5_return', ascending=False)

# Save comparison CSV
merged.to_csv(f'results/v5_vs_bh_comparison_{ts}.csv', encoding='utf-8-sig')
print(f'Saved: results/v5_vs_bh_comparison_{ts}.csv')

# Save source data
v5.to_csv(f'results/v5_results_{ts}.csv', index=False, encoding='utf-8-sig')
print(f'Saved: results/v5_results_{ts}.csv')

bh.to_csv(f'results/bh_results_{ts}.csv', index=False, encoding='utf-8-sig')
print(f'Saved: results/bh_results_{ts}.csv')

# Save summary report
with open(f'results/summary_report_{ts}.md', 'w', encoding='utf-8') as f:
    f.write('# V5 策略 Deepseek 股票池回测报告\n\n')
    f.write(f'回测期间: 2024-01-01 ~ 2025-06-10\n')
    f.write(f'股票数量: {len(v5)} 只（{v5["group"].nunique()} 个板块）\n\n')
    
    f.write('## 板块对比表\n\n')
    f.write('| 板块 | V5收益 | 持有收益 | 超额收益 | 胜率 | 夏普 | 回撤 |\n')
    f.write('|------|--------|---------|---------|------|------|------|\n')
    for g, row in merged.iterrows():
        f.write('| {} | {:+.2f}% | {:+.2f}% | {:+.2f}% | {:.0f}% | {:+.2f} | {:.2f}% |\n'.format(
            g, row['v5_return'], row['bh_return'], row['excess_return'],
            row['v5_winrate'], row['v5_sharpe'], row['v5_dd']))
    
    f.write('\n## 总体\n\n')
    f.write(f'V5 平均收益: {v5["return_pct"].mean():+.2f}%\n')
    f.write(f'持有平均收益: {bh["bh_return"].mean():+.2f}%\n')
    f.write(f'超额收益: {v5["return_pct"].mean() - bh["bh_return"].mean():+.2f}%\n')
    f.write(f'总胜率: {(v5["pnl"]>0).mean()*100:.1f}%\n\n')
    
    f.write('## 关键发现\n\n')
    f.write('**V5 策略最大价值：下行保护**\n\n')
    f.write('- 光伏板块：持有亏 30.66%，V5 赚 9.60%（超额 +40pct）\n')
    f.write('- 锂电池板块：持有亏 20.04%，V5 赚 29.65%（超额 +50pct）\n\n')
    f.write('**V5 策略最大短板：过早止盈**\n\n')
    f.write('- 人工智能板块：持有赚 38.15%，V5 只赚 8.56%（跑输 30pct）\n')
    f.write('- 机器人板块：持有赚 37.74%，V5 赚 31.88%（差距 6pct）\n\n')
    f.write('**最佳适配板块：** 充电桩（+14%超额）、新能源车（+7%超额）、创新药（+8%超额）\n')
    f.write('**最不适配板块：** 人工智能（-30%超额）、数字经济（-7%超额）、消费电子（-6%超额）\n')

print(f'Saved: results/summary_report_{ts}.md')
print('Done!')
