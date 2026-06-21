import pandas as pd

v5 = pd.read_csv('batch_results_20260621_100628.csv', encoding='utf-8-sig')
v9 = pd.read_csv('batch_results_20260621_103928.csv', encoding='utf-8-sig')
bh = pd.read_csv('data/deepseek_bh_returns.csv', encoding='utf-8-sig')

# Merge v5 & v9
merged = v5[['code','name','group','return_pct','sharpe','max_dd']].merge(
    v9[['code','return_pct','sharpe','max_dd']], on='code', suffixes=('_v5','_v9'))
merged = merged.merge(bh[['code','bh_return']], on='code')

# Group level
def grp_stats(df):
    return pd.Series({
        'v5_mean': df['return_pct_v5'].mean(),
        'v9_mean': df['return_pct_v9'].mean(),
        'bh_mean': df['bh_return'].mean(),
        'v5_wr': (df['return_pct_v5']>0).mean()*100,
        'v9_wr': (df['return_pct_v9']>0).mean()*100,
        'v5_sharpe': df['sharpe_v5'].mean(),
        'v9_sharpe': df['sharpe_v9'].mean(),
        'v5_dd': df['max_dd_v5'].mean(),
        'v9_dd': df['max_dd_v9'].mean(),
        'count': len(df),
    })

grp = merged.groupby('group').apply(grp_stats).round(2)
grp = grp.sort_values('v5_mean', ascending=False)

# Print comparison table
hdr = '{:<12} {:>8} {:>8} {:>8} {:>8} {:>6} {:>6}'.format('板块', 'V5收益', 'V9收益', '持有收益', '超额V9', 'V5胜率', 'V9胜率')
print(hdr)
print('-' * 66)
for g, row in grp.iterrows():
    excess_v9 = row['v9_mean'] - row['bh_mean']
    line = '{:<12} {:>+7.2f}% {:>+7.2f}% {:>+7.2f}% {:>+7.2f}% {:>5.0f}% {:>5.0f}%'.format(
        g, row['v5_mean'], row['v9_mean'], row['bh_mean'], excess_v9, row['v5_wr'], row['v9_wr'])
    print(line)
print('-' * 66)
print('{:<12} {:>+7.2f}% {:>+7.2f}% {:>+7.2f}% {:>+7.2f}% {:>5.0f}% {:>5.0f}%'.format(
    '总体', merged['return_pct_v5'].mean(), merged['return_pct_v9'].mean(),
    merged['bh_return'].mean(), merged['return_pct_v9'].mean()-merged['bh_return'].mean(),
    (merged['return_pct_v5']>0).mean()*100, (merged['return_pct_v9']>0).mean()*100))

print('\n=== v5 vs v9 个股差异最大TOP10 ===')
merged['diff'] = merged['return_pct_v9'] - merged['return_pct_v5']
for _, r in merged.sort_values('diff', ascending=False).head(10).iterrows():
    print('  {:>+6.2f}% | {} {} ({})'.format(r['diff'], r['code'], r['name'], r['group']))
print('\n=== v5 vs v9 个股差异最大BOTTOM10 ===')
for _, r in merged.sort_values('diff', ascending=True).head(10).iterrows():
    print('  {:>+6.2f}% | {} {} ({})'.format(r['diff'], r['code'], r['name'], r['group']))
