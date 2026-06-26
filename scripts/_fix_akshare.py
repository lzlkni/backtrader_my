import os

base = r'D:\Users\lzl_k\AppData\Local\Programs\Python\Python312\venvs\backtrader\Lib\site-packages\akshare\stock'
files = [f for f in os.listdir(base) if f.endswith('_sina.py')]

for fname in files:
    path = os.path.join(base, fname)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    orig = content
    content = content.replace(
        'temp_df = temp_df.iloc[:, :-1]',
        'temp_df = temp_df.iloc[:, :-1].copy()'
    )
    content = content.replace(
        'temp_df = temp_df[start_date:end_date]',
        'temp_df = temp_df.loc[start_date:end_date].copy()'
    )
    
    if content != orig:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed: {fname}')
    else:
        print(f'No changes: {fname}')

print('Done!')
