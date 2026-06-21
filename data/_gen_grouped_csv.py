import pandas as pd
df = pd.read_csv('data/sector_mapping.csv', encoding='utf-8-sig')
with open('data/sector_stocks_grouped.csv', 'w', encoding='utf-8-sig') as f:
    for _, row in df.iterrows():
        f.write("{},{},{}\n".format(row['code'], row['name'], row['sector']))
print('Generated data/sector_stocks_grouped.csv with', len(df), 'stocks')
