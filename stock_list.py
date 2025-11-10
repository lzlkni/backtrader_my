import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time

def get_all_stocks():
    """
    获取A股所有股票代码和名称，过滤掉ST股票和上市时间少于1个月的新股
    通过读取股票历史数据，如果有大于一个月前的数据则为非新股
    """
    # 获取A股所有股票代码和名称
    stock_info = ak.stock_info_a_code_name()
    
    # 过滤掉ST股票
    stock_info = stock_info[~stock_info['name'].str.contains('ST|退')]
    
    # 处理股票代码为6位格式（暂时不添加前缀，用于查询历史数据）
    stock_info['code_raw'] = stock_info['code'].str.zfill(6)
    
    # 计算1个月前的日期
    one_month_ago = datetime.now() - timedelta(days=30)
    print(f"过滤条件：历史数据最早日期早于 {one_month_ago.strftime('%Y-%m-%d')}")
    
    # 获取历史数据的开始日期（设置为6个月前，确保能获取到足够的历史数据来判断是否为新股）
    # 对于新股判断，我们只需要知道是否有1个月前的数据
    # 但获取更长时间范围的数据可以提高准确性
    start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')
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
            # 给股票代码加上前缀（sh或sz）
            stock_code_with_prefix = 'sh' + stock_code if stock_code.startswith('6') else 'sz' + stock_code
            
            # 使用stock_zh_a_daily获取A股历史数据
            stock_hist_df = ak.stock_zh_a_daily(symbol=stock_code_with_prefix, adjust="qfq", start_date=start_date, end_date=end_date)
            
            # 检查数据是否为空
            if stock_hist_df.empty:
                # 仍然没有数据，可能是新股，过滤掉
                new_stock_count += 1
                if new_stock_count <= 10:  # 只显示前10只被过滤的新股
                    print(f"  过滤新股（无历史数据）: {stock_code} {stock_name}")
                continue
            
            # 获取历史数据的日期
            # akshare返回的数据，日期可能在索引中，也可能在第一列
            earliest_date = None
            
            # 方法1: 检查索引是否为日期类型
            if isinstance(stock_hist_df.index, pd.DatetimeIndex):
                earliest_date = stock_hist_df.index.min()
            elif hasattr(stock_hist_df.index, 'dtype') and pd.api.types.is_datetime64_any_dtype(stock_hist_df.index):
                earliest_date = pd.to_datetime(stock_hist_df.index).min()
            
            # 方法2: 检查第一列是否为日期
            if earliest_date is None:
                first_col = stock_hist_df.columns[0]
                try:
                    # 尝试将第一列转换为日期
                    dates = pd.to_datetime(stock_hist_df[first_col], errors='coerce')
                    dates = dates.dropna()
                    if not dates.empty:
                        earliest_date = dates.min()
                except:
                    pass
            
            # 方法3: 检查是否有名为'日期'的列
            if earliest_date is None and '日期' in stock_hist_df.columns:
                try:
                    dates = pd.to_datetime(stock_hist_df['日期'], errors='coerce')
                    dates = dates.dropna()
                    if not dates.empty:
                        earliest_date = dates.min()
                except:
                    pass
            
            # 如果还是找不到日期，尝试查找所有可能是日期的列
            if earliest_date is None:
                for col in stock_hist_df.columns:
                    try:
                        dates = pd.to_datetime(stock_hist_df[col], errors='coerce')
                        dates = dates.dropna()
                        if not dates.empty:
                            # 检查日期是否合理（在1900年到2100年之间）
                            valid_dates = dates[(dates >= pd.Timestamp('1900-01-01')) & (dates <= pd.Timestamp('2100-01-01'))]
                            if not valid_dates.empty:
                                earliest_date = valid_dates.min()
                                break
                    except:
                        continue
            
            # 如果仍然找不到日期，跳过该股票
            if earliest_date is None:
                new_stock_count += 1
                if new_stock_count <= 10:
                    print(f"  过滤新股（无法解析日期）: {stock_code} {stock_name}")
                continue
            
            # 确保earliest_date是datetime类型（如果不是，转换为datetime）
            if isinstance(earliest_date, pd.Timestamp):
                earliest_date = earliest_date.to_pydatetime()
            elif not isinstance(earliest_date, datetime):
                earliest_date = pd.to_datetime(earliest_date).to_pydatetime()
            
            # 如果最早日期早于1个月前，则保留
            if earliest_date <= one_month_ago:
                valid_stocks.append({
                    'code': stock_code,
                    'name': stock_name,
                    'earliest_date': earliest_date.strftime('%Y-%m-%d')
                })
            else:
                # 最早日期在1个月内，认为是新股，过滤掉
                new_stock_count += 1
                if new_stock_count <= 10:  # 只显示前10只被过滤的新股
                    print(f"  过滤新股: {stock_code} {stock_name} 最早数据日期: {earliest_date.strftime('%Y-%m-%d')}")
            
            # 添加小延迟避免请求过快
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
        f.write("# 已过滤ST股票和上市时间少于1个月的新股\n")
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

def get_top_stocks_by_sectors():
    """
    获取前10个热门板块中每个板块的前10个股票（只取沪深A股，排除B股和ST股票）
    """
    try:
        # 获取热门板块数据
        hot_sectors = ak.stock_board_concept_name_em()
        
        # 取前10个热门板块
        top_10_sectors = hot_sectors.head(10)
        
        print(f"\n获取前10个热门板块的股票信息：")
        print(top_10_sectors[['板块名称', '板块代码']].to_string(index=False))
        
        all_sector_stocks = []
        
        for index, sector in top_10_sectors.iterrows():
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
                
                # 取前10个股票
                top_10_stocks = sector_stocks.head(10)
                
                # 添加板块信息
                top_10_stocks['板块名称'] = sector_name
                top_10_stocks['板块代码'] = sector_code
                
                all_sector_stocks.append(top_10_stocks)
                
                print(f"板块 '{sector_name}' 前10只股票（沪深A股，排除B股和ST）：")
                print(top_10_stocks[['代码', '名称', '最新价', '涨跌幅']].to_string(index=False))
                
            except Exception as e:                
                print(f"获取板块 '{sector_name}' 股票时出错：{str(e)}")
                print(f"尝试使用备用方法获取板块股票...")
                
                try:
                    # 备用方法：尝试使用板块名称而不是代码
                    sector_stocks = ak.stock_board_industry_cons_em(symbol=sector_name)
                    
                    if not sector_stocks.empty:
                        print(f"备用方法成功获取到 {len(sector_stocks)} 只股票")
                        
                        # 过滤只保留沪深A股（排除北交所股票，北交所股票代码以8开头）
                        sector_stocks = sector_stocks[~sector_stocks['代码'].str.startswith('8')]
                        
                        # 排除B股（B股代码以2开头）
                        sector_stocks = sector_stocks[~sector_stocks['代码'].str.startswith('2')]
                        sector_stocks = sector_stocks[~sector_stocks['代码'].str.startswith('9')]
                        
                        # 排除ST股票（股票名称包含ST或退）
                        sector_stocks = sector_stocks[~sector_stocks['名称'].str.contains('ST|退', na=False)]
                        
                        if not sector_stocks.empty:
                            # 取前10个股票
                            top_10_stocks = sector_stocks.head(10)
                            
                            # 添加板块信息
                            top_10_stocks['板块名称'] = sector_name
                            top_10_stocks['板块代码'] = sector_code
                            
                            all_sector_stocks.append(top_10_stocks)
                            
                            print(f"板块 '{sector_name}' 前10只股票（备用方法）：")
                            print(top_10_stocks[['代码', '名称', '最新价', '涨跌幅']].to_string(index=False))
                        else:
                            print(f"板块 '{sector_name}' 备用方法过滤后没有符合条件的股票")
                    else:
                        print(f"板块 '{sector_name}' 备用方法也没有获取到数据")
                        
                except Exception as e2:
                    print(f"板块 '{sector_name}' 备用方法也失败：{str(e2)}")
                
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
    get_all_stocks()
    # read_stocks()
    # get_hot_sectors()
    # get_top_stocks_by_sectors() 