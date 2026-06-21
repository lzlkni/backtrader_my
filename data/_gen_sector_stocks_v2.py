import akshare as ak
import pandas as pd
import time
import sys
import os

sectors = ak.stock_sector_spot()

# Sort by change percent (涨跌幅, column index 5)
sectors = sectors.sort_values(sectors.columns[5], ascending=False)
top_sectors = sectors.head(10)

all_stocks = []

def get_sector_name_from_label(label):
    """Get clean sector name from sector spot data."""
    row = sectors[sectors['label'] == label].iloc[0]
    # Column 1 is the sector name (板块名称)
    return str(row.iloc[1])

for i, (_, sector) in enumerate(top_sectors.iterrows()):
    label = sector['label']
    sector_name = get_sector_name_from_label(label)
    
    print(f'[{i+1}/10] {sector_name} ({label})', file=sys.stderr)
    
    try:
        stocks = ak.stock_sector_detail(sector=label)
        
        count = 0
        for _, row in stocks.iterrows():
            sym = str(row['symbol'])
            name = str(row['name'])
            
            # Filter: skip ST stocks and BJ stocks
            if 'ST' in name or '退' in name or 'S' == name[0] or name.startswith('*'):
                continue
            if sym.startswith('bj'):
                continue
            
            all_stocks.append({
                'code': sym,
                'name': name,
                'sector': sector_name
            })
            count += 1
            if count >= 10:
                break
        
        print(f'  Got {count} valid stocks', file=sys.stderr)
        
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
    out_path = 'data/sector_stocks_v5.csv'
    with open(out_path, 'w', encoding='utf-8-sig') as f:
        for _, row in df.iterrows():
            f.write(f"{row['code']},{row['name']}\n")
    
    print(f'Saved {len(df)} stocks to {out_path}', file=sys.stderr)
    
    print(f'\n=== Sector Distribution ===')
    for sector, group in df.groupby('sector'):
        stocks_list = ', '.join(f'{r["code"]} {r["name"]}' for _, r in group.iterrows())
        print(f'{sector} ({len(group)}): {stocks_list}')
    
    # Save sector-to-stock mapping
    with open('data/sector_mapping.csv', 'w', encoding='utf-8-sig') as f:
        f.write('sector,code,name\n')
        for _, row in df.iterrows():
            f.write(f"{row['sector']},{row['code']},{row['name']}\n")
    
    sys.stdout.flush()
else:
    print('No stocks collected', file=sys.stderr)
