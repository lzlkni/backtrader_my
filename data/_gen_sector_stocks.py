import akshare as ak
import pandas as pd
import time
import sys

# Get sector spots (49 sectors)
sectors = ak.stock_sector_spot()
print(f'Got {len(sectors)} sectors')

# Sort by change percent (涨跌幅) descending
change_col = [c for c in sectors.columns if '涨幅' in c or 'changepercent' in c.lower() or '涨跌' in c][0]
sectors = sectors.sort_values(change_col, ascending=False)
top_sectors = sectors.head(10)

all_stocks = []
sector_results = []

for i, (_, sector) in enumerate(top_sectors.iterrows()):
    label = sector['label']
    name_col = [c for c in sectors.columns if '公司' in c or '名称' in c or 'name' in c.lower()][0]
    sector_name = sector[name_col]
    
    print(f'[{i+1}/10] {sector_name} (label={label})', file=sys.stderr)
    
    try:
        stocks = ak.stock_sector_detail(sector=label)
        stocks = stocks.head(10)  # Top 10 stocks
        
        codes = []
        for _, row in stocks.iterrows():
            sym = row['symbol']  # e.g. sh600176
            name = row['name']
            all_stocks.append({
                'code': sym,
                'name': name,
                'sector': sector_name
            })
            codes.append(f'{sym} {name}')
        
        print(f'  Got {len(stocks)} stocks: {", ".join(codes)}', file=sys.stderr)
        sector_results.append((sector_name, len(stocks)))
        
    except Exception as e:
        print(f'  Failed: {e}', file=sys.stderr)
    
    time.sleep(1.5)

if all_stocks:
    df = pd.DataFrame(all_stocks)
    before = len(df)
    df = df.drop_duplicates(subset=['code'])
    print(f'De-duplicated: {before} -> {len(df)}', file=sys.stderr)
    
    # Save full detail
    df.to_csv('data/sector_stocks_full.csv', index=False, encoding='utf-8-sig')
    
    # Save simple stock list for v5
    with open('data/sector_stocks_v5.csv', 'w', encoding='utf-8-sig') as f:
        for _, row in df.iterrows():
            f.write(f"{row['code']},{row['name']}\n")
    
    print(f'Saved {len(df)} stocks', file=sys.stderr)
    
    print(f'\n=== Sector Distribution ===')
    for sector, group in df.groupby('sector'):
        stocks_list = ', '.join(f'{r["code"]} {r["name"]}' for _, r in group.iterrows())
        print(f'{sector} ({len(group)}): {stocks_list}')
    sys.stdout.flush()
else:
    print('No stocks collected', file=sys.stderr)

import os
# Print CSV content
if os.path.exists('data/sector_stocks_v5.csv'):
    with open('data/sector_stocks_v5.csv', 'r', encoding='utf-8-sig') as f:
        content = f.read()
    print('\n=== CSV Content ===')
    print(content)
