import warnings
from pandas.errors import SettingWithCopyWarning
import akshare as ak

warnings.filterwarnings('error', category=SettingWithCopyWarning)

symbols = ['sz000001', 'sh600519', 'sz300750']
for symbol in symbols:
    df = ak.stock_zh_a_daily(symbol=symbol, adjust='qfq', start_date='20250101', end_date='20250610')
    print(f'{symbol}: {len(df)} rows')

print('ALL OK - no SettingWithCopyWarning')
