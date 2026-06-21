import akshare as ak
import pandas as pd
from datetime import datetime
import time
import sys

# Read deepseek stock list
df = pd.read_csv('data/deepseek_stocks.csv', encoding='utf-8-sig', header=None, names=['code', 'name', 'group'])
print(f'Total stocks: {len(df)}', file=sys.stderr)

start_date = '20240101'
end_date = '20250610'

bh_results = []

for i, (_, row) in enumerate(df.iterrows()):
    code = row['code']
    name = row['name']
    group = row['group']
    
    try:
        data = ak.stock_zh_a_daily(symbol=code, adjust="qfq", start_date=start_date, end_date=end_date)
        if len(data) < 5:
            print(f'[{i+1}/{len(df)}] {code} {name}: insufficient data ({len(data)})', file=sys.stderr)
            continue
        
        # Buy & hold: first close -> last close
        first_close = data['close'].iloc[0]
        last_close = data['close'].iloc[-1]
        bh_ret = (last_close - first_close) / first_close * 100
        
        bh_results.append({
            'code': code, 'name': name, 'group': group,
            'bh_return': round(bh_ret, 2),
            'first_date': data['date'].iloc[0],
            'last_date': data['date'].iloc[-1],
        })
    except Exception as e:
        print(f'[{i+1}/{len(df)}] {code} {name}: {e}', file=sys.stderr)
    
    time.sleep(0.3)  # rate limit
    
    if (i+1) % 20 == 0:
        print(f'Progress: {i+1}/{len(df)}', file=sys.stderr)
        sys.stdout.flush()

if bh_results:
    bh_df = pd.DataFrame(bh_results)
    bh_df.to_csv('data/deepseek_bh_returns.csv', index=False, encoding='utf-8-sig')
    
    print(f'\n=== Buy & Hold Returns by Group ===')
    grp = bh_df.groupby('group')['bh_return'].agg(['mean', 'std', 'min', 'max', 'count'])
    grp = grp.sort_values('mean', ascending=False)
    for g, row2 in grp.iterrows():
        print(f'{g:<10} mean={row2["mean"]:>+7.2f}%  std={row2["std"]:.2f}  min={row2["min"]:>+7.2f}%  max={row2["max"]:>+7.2f}%  n={int(row2["count"])}')
    
    print(f'\nOverall B&H mean: {bh_df["bh_return"].mean():+.2f}%')
else:
    print('No data collected')
