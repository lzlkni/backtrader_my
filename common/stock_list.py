import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time


def _extract_earliest_trade_date(stock_hist_df):
    """
    从历史数据 DataFrame 中提取最早的交易日期
    """
    earliest_date = None

    if isinstance(stock_hist_df.index, pd.DatetimeIndex):
        earliest_date = stock_hist_df.index.min()
    elif hasattr(stock_hist_df.index, 'dtype') and pd.api.types.is_datetime64_any_dtype(stock_hist_df.index):
        earliest_date = pd.to_datetime(stock_hist_df.index).min()

    if earliest_date is None and not stock_hist_df.empty:
        first_col = stock_hist_df.columns[0]
        try:
            dates = pd.to_datetime(stock_hist_df[first_col], errors='coerce').dropna()
            if not dates.empty:
                earliest_date = dates.min()
        except Exception:
            pass

    if earliest_date is None and '日期' in stock_hist_df.columns:
        try:
            dates = pd.to_datetime(stock_hist_df['日期'], errors='coerce').dropna()
            if not dates.empty:
                earliest_date = dates.min()
        except Exception:
            pass

    if earliest_date is None:
        for col in stock_hist_df.columns:
            try:
                dates = pd.to_datetime(stock_hist_df[col], errors='coerce').dropna()
                if not dates.empty:
                    valid_dates = dates[
                        (dates >= pd.Timestamp('1900-01-01')) & (dates <= pd.Timestamp('2100-01-01'))
                    ]
                    if not valid_dates.empty:
                        earliest_date = valid_dates.min()
                        break
            except Exception:
                continue

    if earliest_date is None:
        return None

    if isinstance(earliest_date, pd.Timestamp):
        return earliest_date.to_pydatetime()

    try:
        return pd.to_datetime(earliest_date).to_pydatetime()
    except Exception:
        return None


def filter_new_stock(stock_code: str, stock_name: str, cutoff_date: datetime, start_date: str, end_date: str):
    """
    判断股票是否通过新股过滤

    :return: (是否通过, 最早日期, 失败原因)
             失败原因: None / 'no_data' / 'no_date' / 'too_new' / 'error:<message>'
    """
    stock_code = str(stock_code).zfill(6)
    stock_code_with_prefix = 'sh' + stock_code if stock_code.startswith('6') else 'sz' + stock_code

    try:
        stock_hist_df = ak.stock_zh_a_daily(
            symbol=stock_code_with_prefix,
            adjust="qfq",
            start_date=start_date,
            end_date=end_date
        )
    except Exception as exc:
        return False, None, f"error:{exc}"

    if stock_hist_df.empty:
        return False, None, 'no_data'

    earliest_date = _extract_earliest_trade_date(stock_hist_df)

    if earliest_date is None:
        return False, None, 'no_date'

    if earliest_date <= cutoff_date:
        return True, earliest_date, None

    return False, earliest_date, 'too_new'


def prepare_sector_top_stocks(sector_stocks, sector_name, sector_code, cutoff_date, start_date, end_date):
    """
    对板块股票列表进行新股过滤并返回最终的前10只股票 DataFrame
    """
    if sector_stocks.empty:
        print(f"板块 '{sector_name}' 没有股票数据，跳过")
        return None

    filtered_rows = []
    new_stock_filtered = 0
    error_filtered = 0

    for _, stock_row in sector_stocks.iterrows():
        raw_code = str(stock_row['代码']).zfill(6)
        stock_label = f"{raw_code} {stock_row['名称']}"
        is_valid, earliest_date, reason = filter_new_stock(
            stock_code=raw_code,
            stock_name=stock_row['名称'],
            cutoff_date=cutoff_date,
            start_date=start_date,
            end_date=end_date
        )

        if is_valid:
            filtered_rows.append(stock_row.copy())
        else:
            new_stock_filtered += 1
            if reason and reason.startswith('error:'):
                error_filtered += 1
                if error_filtered <= 3:
                    error_message = reason.split('error:', 1)[1]
                    print(f"  警告: {stock_label} 获取历史数据失败: {error_message}")
            else:
                if new_stock_filtered <= 3:
                    if reason == 'no_data':
                        print(f"  过滤新股（无历史数据）: {stock_label}")
                    elif reason == 'no_date':
                        print(f"  过滤新股（无法解析日期）: {stock_label}")
                    elif reason == 'too_new' and earliest_date is not None:
                        print(f"  过滤新股: {stock_label} 最早数据日期: {earliest_date.strftime('%Y-%m-%d')}")

        time.sleep(0.05)

        if len(filtered_rows) >= 10:
            break

    if not filtered_rows:
        print(f"板块 '{sector_name}' 过滤新股后没有符合条件的股票，跳过")
        return None

    top_10_stocks = pd.DataFrame(filtered_rows).head(10).copy()
    top_10_stocks['板块名称'] = sector_name
    top_10_stocks['板块代码'] = sector_code

    return top_10_stocks


def get_all_stocks():
    """
    获取A股所有股票代码和名称，过滤掉ST股票和上市时间少于1年的新股
    通过读取股票历史数据，如果有大于1年前的数据则为非新股
    """
    # 获取A股所有股票代码和名称
    stock_info = ak.stock_info_a_code_name()
    
    # 过滤掉ST股票
    stock_info = stock_info[~stock_info['name'].str.contains('ST|退')]
    
    # 处理股票代码为6位格式（暂时不添加前缀，用于查询历史数据）
    stock_info['code_raw'] = stock_info['code'].str.zfill(6)
    
    # 计算1年前的日期
    one_year_ago = datetime.now() - timedelta(days=365)
    print(f"过滤条件：历史数据最早日期早于 {one_year_ago.strftime('%Y-%m-%d')}")
    
    # 获取历史数据的开始日期（设置为6个月前，确保能获取到足够的历史数据来判断是否为新股）
    # 对于新股判断，我们只需要知道是否有1年前的数据
    # 但获取更长时间范围的数据可以提高准确性
    start_date = (datetime.now() - timedelta(days=400)).strftime('%Y%m%d')
    end_date = datetime.now().strftime('%Y%m%d')
    
    print(f"\n开始检查 {len(stock_info)} 只股票的历史数据...")
    print("注意：此过程可能需要较长时间，因为需要查询每只股票的历史数据")
    
    valid_stocks = []
    failed_count = 0
    new_stock_count = 0
    total_count = len(stock_info)
    processed_count = 0
    
    for idx, row in stock_info.iterrows():
        stock_code = row['code_raw']
        stock_name = row['name']
        processed_count += 1
        
        # 显示进度
        if processed_count % 50 == 0 or processed_count == total_count:
            print(f"进度: {processed_count}/{total_count} ({processed_count*100/total_count:.1f}%), 已过滤新股: {new_stock_count}, 失败: {failed_count}")
        
        try:
            is_valid, earliest_date, reason = filter_new_stock(
                stock_code=stock_code,
                stock_name=stock_name,
                cutoff_date=one_year_ago,
                start_date=start_date,
                end_date=end_date
            )

            if is_valid:
                valid_stocks.append({
                    'code': stock_code,
                    'name': stock_name,
                    'earliest_date': earliest_date.strftime('%Y-%m-%d')
                })
            else:
                new_stock_count += 1

                if reason and reason.startswith('error:'):
                    failed_count += 1
                    error_message = reason.split('error:', 1)[1]
                    if failed_count <= 10:
                        print(f"  警告: {stock_code} {stock_name} 获取历史数据失败: {error_message}")
                else:
                    if new_stock_count <= 10:
                        if reason == 'no_data':
                            print(f"  过滤新股（无历史数据）: {stock_code} {stock_name}")
                        elif reason == 'no_date':
                            print(f"  过滤新股（无法解析日期）: {stock_code} {stock_name}")
                        elif reason == 'too_new' and earliest_date is not None:
                            print(f"  过滤新股: {stock_code} {stock_name} 最早数据日期: {earliest_date.strftime('%Y-%m-%d')}")

            time.sleep(0.05)

        except Exception as e:
            failed_count += 1
            # 如果获取失败，可能是新股或数据问题，过滤掉（保守策略）
            if failed_count <= 10:  # 只显示前10个错误
                print(f"  警告: {stock_code} {stock_name} 获取历史数据失败: {e}")
            new_stock_count += 1
            continue
    
    print(f"\n过滤完成:")
    print(f"  原始股票数: {len(stock_info)}")
    print(f"  过滤新股数: {new_stock_count}")
    print(f"  获取失败数: {failed_count}")
    print(f"  最终股票数: {len(valid_stocks)}")
    
    # 转换为DataFrame
    stock_info_filtered = pd.DataFrame(valid_stocks)
    
    if stock_info_filtered.empty:
        print("\n警告：没有符合条件的股票！")
        return
    
    # 处理股票代码为6位格式并添加前缀
    stock_info_filtered['code'] = stock_info_filtered['code'].str.zfill(6)
    # 添加sh或sz前缀
    stock_info_filtered['code'] = stock_info_filtered['code'].apply(lambda x: 'sh' + x if x.startswith('6') else 'sz' + x)
    
    # 打印股票总数
    print(f"\n总共有 {len(stock_info_filtered)} 只股票（已过滤ST股票和新股）")
    
    # 显示前10只股票作为示例
    print("\n前10只股票示例：")
    print(stock_info_filtered[['code', 'name']].head(10))
    
    # 保存到CSV文件，格式为：股票代码,股票名称
    with open('stocks_all.csv', 'w', encoding='utf-8-sig') as f:
        f.write("# 股票列表文件\n")
        f.write("# 格式：股票代码,股票名称\n")
        f.write("# 支持注释行（以#开头）\n")
        f.write("# 已过滤ST股票和上市时间少于1年的新股\n")
        f.write("\n")
        
        for _, row in stock_info_filtered.iterrows():
            f.write(f"{row['code']},{row['name']}\n")
    
    print("\n股票信息已保存到 stocks.csv")

def read_stocks():
    # 读取stocks.csv
    stocks_df = pd.read_csv('stocks.csv')
    
    # 确保股票代码为6位格式并添加前缀
    stocks_df['code'] = stocks_df['code'].astype(str).str.zfill(6)
    stocks_df['code'] = stocks_df['code']
    
    print("\n读取的股票信息：")
    print(stocks_df.head(10))
    return stocks_df

def get_hot_sectors():
    try:
        # 获取热门板块数据
        hot_sectors = ak.stock_board_industry_name_em()
        
        # 显示前10个热门板块
        print("\n热门板块前10名：")
        print(hot_sectors.head(10))
        
        # 保存到CSV文件
        hot_sectors.to_csv('hot_sectors.csv', index=False, encoding='utf-8-sig')
        print("\n热门板块信息已保存到 hot_sectors.csv")
        
        return hot_sectors
    except Exception as e:
        print(f"获取热门板块数据时出错：{str(e)}")
        return None


def get_hot_sectors_ths(top_n: int = 10, save_path: str = 'hot_sectors_ths.csv'):
    """
    使用同花顺概念接口获取热门板块（概念）列表

    :param top_n: 需要展示和保存的热门板块数量
    :param save_path: 保存数据的 CSV 文件名
    :return: pandas.DataFrame or None
    """
    try:
        print("\n正在通过同花顺接口获取热门概念板块...")
        concept_df = ak.stock_board_concept_name_ths()

        if concept_df is None or concept_df.empty:
            print("未能获取到任何概念板块数据，请稍后重试或检查网络。")
            return None
        else:
            return concept_df
      
    except Exception as e:
        print(f"使用同花顺接口获取热门板块数据时出错：{e}")
        print("常见问题：同花顺可能需要验证码或限流，建议稍后重试。")
        return None


def get_top_concept_returns_from_ths(top_n: int = 10):
    """
    基于 get_hot_sectors_ths 返回的板块，获取各板块开盘价、收盘价并计算涨跌幅，返回涨幅前 top_n 的板块
    """
    concept_df = get_hot_sectors_ths()
    if concept_df is None or concept_df.empty:
        print("未能获取到热门概念板块，无法计算涨幅。")
        return None

    result_df = pd.DataFrame()  # 新增结果DataFrame
    for _, row in concept_df.iterrows():
        symbol = row["name"]
        sector_name = row["code"]
        print(f"正在获取板块 {sector_name}({symbol}) 指数")

        try:
            idx_df = ak.stock_board_concept_index_ths(symbol=symbol)
        except Exception as exc:
            print(f"获取板块 {sector_name}({symbol}) 指数失败: {exc}")
            continue

        if idx_df is None or idx_df.empty:
            print(f"板块 {sector_name}({symbol}) 指数数据为空，跳过。")
            continue

        open_candidates = ['开盘', '开盘价', '今开', 'open', 'open_price']
        close_candidates = ['收盘', '收盘价', '最新价', 'close', 'close_price']

        open_col = next((col for col in open_candidates if col in idx_df.columns), None)
        close_col = next((col for col in close_candidates if col in idx_df.columns), None)

        if open_col is None or close_col is None:
            print(f"板块 {sector_name}({symbol}) 缺少开盘/收盘列，现有列：{idx_df.columns}")
            continue

        latest = idx_df.iloc[-1].copy()
        open_price = pd.to_numeric(latest[open_col], errors='coerce')
        close_price = pd.to_numeric(latest[close_col], errors='coerce')

        if pd.isna(open_price) or pd.isna(close_price) or open_price == 0:
            print(f"板块 {sector_name}({symbol}) 数据异常：open={open_price}, close={close_price}")
            continue
        # 计算涨跌幅
        latest['涨跌幅(%)'] = (close_price - open_price) / open_price * 100
        latest['板块名称'] = symbol
        latest['板块代码'] = sector_name

        # 将latest追加到result_df
        result_df = pd.concat([result_df, latest.to_frame().T], ignore_index=True)

        time.sleep(3)

    if result_df.empty:
        print("未计算出任何板块的涨跌幅。")
        return None

    top_df = result_df.sort_values(['涨跌幅(%)', '成交额'], ascending=[False, False]).head(top_n)
    print(f"\n涨幅前 {top_n} 的板块：")
    print(top_df[['板块名称', '板块代码', '涨跌幅(%)']].to_string(index=False))
    return top_df

def get_top_stocks_by_sectors():
    """
    获取前10个热门板块中每个板块的前10个股票（只取沪深A股，排除B股和ST股票）
    """
    cutoff_date = datetime.now() - timedelta(days=365)
    history_start = (datetime.now() - timedelta(days=400)).strftime('%Y%m%d')
    history_end = datetime.now().strftime('%Y%m%d')

    try:
        # 获取热门板块数据
        # 东方财富-概念板块
        print("正在获取热门板块数据...")
        hot_sectors = ak.stock_board_concept_name_em()
        
        # 取前10个热门板块
        top_10_sectors = hot_sectors.head(10)
        
        print(f"\n获取前10个热门板块的股票信息：")
        print(top_10_sectors[['板块名称', '板块代码']].to_string(index=False))
        
        all_sector_stocks = []
        
        for index, sector in top_10_sectors.iterrows():
            time.sleep(30)
            sector_name = sector['板块名称']
            sector_code = sector['板块代码']
            
            print(f"\n正在获取板块 '{sector_name}' 的股票...")
            
            try:
                # 获取该板块的股票列表
                print(f"正在获取板块代码 '{sector_code}' 的股票数据...")
                sector_stocks = ak.stock_board_industry_cons_em(symbol=sector_code)
                print(sector_stocks)
                print(f"获取到 {len(sector_stocks)} 只股票")
                
                # 检查数据是否为空
                if sector_stocks.empty:
                    print(f"板块 '{sector_name}' 没有股票数据，跳过")
                    continue
                
                # 过滤只保留沪深A股（排除北交所股票，北交所股票代码以8开头）
                sector_stocks = sector_stocks[~sector_stocks['代码'].str.startswith('8')]
                
                # 排除B股（B股代码以2开头）
                sector_stocks = sector_stocks[~sector_stocks['代码'].str.startswith('2')]
                sector_stocks = sector_stocks[~sector_stocks['代码'].str.startswith('9')]
                
                # 排除ST股票（股票名称包含ST或退）
                sector_stocks = sector_stocks[~sector_stocks['名称'].str.contains('ST|退', na=False)]
                
                # 检查过滤后是否还有数据
                if sector_stocks.empty:
                    print(f"板块 '{sector_name}' 过滤后没有符合条件的股票，跳过")
                    continue

                top_10_stocks = prepare_sector_top_stocks(
                    sector_stocks=sector_stocks,
                    sector_name=sector_name,
                    sector_code=sector_code,
                    cutoff_date=cutoff_date,
                    start_date=history_start,
                    end_date=history_end
                )

                if top_10_stocks is None:
                    continue
                
                all_sector_stocks.append(top_10_stocks)
                
                print(f"板块 '{sector_name}' 前10只股票（沪深A股，排除B股和ST）：")
                print(top_10_stocks[['代码', '名称', '最新价', '涨跌幅']].to_string(index=False))
                
            except Exception as e:                
                print(f"获取板块 '{sector_name}' 股票时出错：{str(e)}")
                continue
            
        
        if all_sector_stocks:
            # 合并所有板块的股票数据
            combined_stocks = pd.concat(all_sector_stocks, ignore_index=True)
            
            # 去重（同一个股票可能属于多个板块）
            combined_stocks = combined_stocks.drop_duplicates(subset=['代码', '名称'])
            
            # 只保留代码和名称字段，并重命名列
            stocks_simple = combined_stocks[['代码', '名称']].copy()
            stocks_simple.columns = ['code', 'name']
            
            # 处理股票代码格式：确保为6位数字，并添加sh或sz前缀
            stocks_simple['code'] = stocks_simple['code'].astype(str).str.zfill(6)
            stocks_simple['code'] = stocks_simple['code'].apply(lambda x: 'sh' + x if x.startswith('6') else 'sz' + x)
            
            # 保存到stocks.csv文件，格式为：股票代码,股票名称
            with open('stocks.csv', 'w', encoding='utf-8-sig') as f:
                f.write("# 股票列表文件\n")
                f.write("# 格式：股票代码,股票名称\n")
                f.write("# 支持注释行（以#开头）\n")
                f.write("\n")
                
                for _, row in stocks_simple.iterrows():
                    f.write(f"{row['code']},{row['name']}\n")
            
            print(f"\n股票信息已保存到 stocks.csv（只包含沪深A股，排除B股和ST股票）")
            print(f"总共获取了 {len(stocks_simple)} 只股票")
            
            # 显示前10只股票作为示例
            print("\n前10只股票示例：")
            print(stocks_simple.head(10))
            
            return stocks_simple
        else:
            print("未能获取任何板块股票数据")
            return None
            
    except Exception as e:
        print(f"获取板块股票数据时出错：{str(e)}")
        return None

if __name__ == "__main__":
    # get_top_stocks_by_sectors() 
    top_concept_df = get_top_concept_returns_from_ths()
    print(top_concept_df.head(10))