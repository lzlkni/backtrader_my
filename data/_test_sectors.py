import akshare as ak
import sys

boards = ak.stock_board_concept_name_em()
print('Columns:', list(boards.columns), file=sys.stderr)
for i in range(min(15, len(boards))):
    row = boards.iloc[i]
    print(f'{i}: {row["板块名称"]} ({row["板块代码"]}) 上涨:{row["上涨家数"]} 下跌:{row["下跌家数"]}')
