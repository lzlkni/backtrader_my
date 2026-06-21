import pandas as pd

v5 = pd.read_csv('batch_results_20260621_100628.csv', encoding='utf-8-sig')
bh = pd.read_csv('data/deepseek_bh_returns.csv', encoding='utf-8-sig')

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
merged['excess'] = (merged['v5_return'] - merged['bh_return']).round(2)
merged = merged.sort_values('v5_return', ascending=False)

hdr = '{:<12} {:>8} {:>8} {:>8} {:>6} {:>8} {:>6}'.format('板块', 'V5收益', '持有收益', '超额', '胜率', '夏普', '回撤')
print(hdr)
print('-' * 60)
for g, row in merged.iterrows():
    line = '{:<12} {:>+7.2f}% {:>+7.2f}% {:>+7.2f}% {:>5.0f}% {:>+7.2f} {:>5.2f}%'.format(
        g, row['v5_return'], row['bh_return'], row['excess'],
        row['v5_winrate'], row['v5_sharpe'], row['v5_dd'])
    print(line)
print('-' * 60)
total_line = '{:<12} {:>+7.2f}% {:>+7.2f}% {:>+7.2f}%'.format(
    '总计/平均', v5['return_pct'].mean(), bh['bh_return'].mean(),
    v5['return_pct'].mean() - bh['bh_return'].mean())
print(total_line)
