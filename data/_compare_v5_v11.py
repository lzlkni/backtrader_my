import pandas as pd

v5 = pd.read_csv('batch_results_20260621_100628.csv', encoding='utf-8-sig')
v11 = pd.read_csv('batch_results_20260621_184538.csv', encoding='utf-8-sig')
bh = pd.read_csv('data/deepseek_bh_returns.csv', encoding='utf-8-sig')

merged = v5[['code','name','group','return_pct','sharpe','max_dd']].merge(
    v11[['code','return_pct','sharpe','max_dd']], on='code', suffixes=('_v5','_v11'))
merged = merged.merge(bh[['code','bh_return']], on='code')

def grp_stats(df):
    return pd.Series({
        'v5': df['return_pct_v5'].mean(),
        'v11': df['return_pct_v11'].mean(),
        'bh': df['bh_return'].mean(),
        'v5_wr': (df['return_pct_v5']>0).mean()*100,
        'v11_wr': (df['return_pct_v11']>0).mean()*100,
        'v5_sharpe': df['sharpe_v5'].mean(),
        'v11_sharpe': df['sharpe_v11'].mean(),
        'v5_dd': df['max_dd_v5'].mean(),
        'v11_dd': df['max_dd_v11'].mean(),
        'n': len(df),
    })

grp = merged.groupby('group').apply(grp_stats).round(2)
grp = grp.sort_values('v5', ascending=False)

hdr = '{:<12} {:>8} {:>8} {:>8} {:>8} {:>6} {:>6} {:>6} {:>6}'.format(
    '板块', 'V5', 'V11', '持有', '超额V11', 'V5胜率', 'V11胜率', 'V5DD', 'V11DD')
print(hdr)
print('-' * 80)
for g, row in grp.iterrows():
    excess = row['v11'] - row['bh']
    line = '{:<12} {:>+7.2f}% {:>+7.2f}% {:>+7.2f}% {:>+7.2f}% {:>5.0f}% {:>5.0f}% {:>5.2f}% {:>5.2f}%'.format(
        g, row['v5'], row['v11'], row['bh'], excess,
        row['v5_wr'], row['v11_wr'], row['v5_dd'], row['v11_dd'])
    print(line)
print('-' * 80)
total = '{:<12} {:>+7.2f}% {:>+7.2f}% {:>+7.2f}% {:>+7.2f}% {:>5.0f}% {:>5.0f}%'.format(
    '总体', merged['return_pct_v5'].mean(), merged['return_pct_v11'].mean(),
    merged['bh_return'].mean(), merged['return_pct_v11'].mean()-merged['bh_return'].mean(),
    (merged['return_pct_v5']>0).mean()*100, (merged['return_pct_v11']>0).mean()*100)
print(total)

print('\n=== TOP5 改进个股 ===')
merged['diff'] = merged['return_pct_v11'] - merged['return_pct_v5']
for _, r in merged.sort_values('diff', ascending=False).head(5).iterrows():
    print('  {:>+7.2f}% | {} {} ({}) | v5={:+.2f}% v11={:+.2f}%'.format(
        r['diff'], r['code'], r['name'], r['group'], r['return_pct_v5'], r['return_pct_v11']))

print('\n=== BOTTOM5 倒退个股 ===')
for _, r in merged.sort_values('diff', ascending=True).head(5).iterrows():
    print('  {:>+7.2f}% | {} {} ({}) | v5={:+.2f}% v11={:+.2f}%'.format(
        r['diff'], r['code'], r['name'], r['group'], r['return_pct_v5'], r['return_pct_v11']))
