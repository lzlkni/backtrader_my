import akshare as ak
sectors = ak.stock_sector_spot()
print('Columns:', list(sectors.columns))
sectors_list = [{col: s[col] for col in sectors.columns} for _, s in sectors.iterrows()]
for i, s in enumerate(sectors_list[:12]):
    print(f'[{i}] label={s.get("label")}')
    for k, v in s.items():
        print(f'  {k}: {v}')
    print()
