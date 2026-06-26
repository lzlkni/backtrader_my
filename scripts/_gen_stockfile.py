import pandas as pd

top_df = pd.read_csv(r'D:\workspace\backtrader_my\data\top200_candidates.csv')
lines = []
for _, r in top_df.iterrows():
    code = str(r['code']).zfill(6)
    if code.startswith('6'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    lines.append(f"{symbol},{r['name']}")

with open(r'D:\workspace\backtrader_my\data\v5_backtest_stocks.csv', 'w', encoding='utf-8-sig') as f:
    f.write('\n'.join(lines) + '\n')

print(f"Written {len(lines)} stocks")
print(lines[:3])
