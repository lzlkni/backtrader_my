import akshare as ak
import pandas as pd

def get_all_stocks():
    # 获取A股所有股票代码和名称
    stock_info = ak.stock_info_a_code_name()
    
    # 过滤掉ST股票
    stock_info = stock_info[~stock_info['name'].str.contains('ST|退')]
    
    # 处理股票代码为6位格式并添加前缀
    stock_info['code'] = stock_info['code'].str.zfill(6)
    # 添加sh或sz前缀
    stock_info['code'] = stock_info['code'].apply(lambda x: 'sh' + x if x.startswith('6') else 'sz' + x)
    
    # 打印股票总数
    print(f"总共有 {len(stock_info)} 只股票（已过滤ST股票）")
    
    # 显示前10只股票作为示例
    print("\n前10只股票示例：")
    print(stock_info.head(10))
    
    # 保存到CSV文件
    stock_info.to_csv('stocks.csv', index=False, encoding='utf-8-sig')
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
            
            # 保存到stocks.csv文件
            stocks_simple.to_csv('stocks.csv', index=False, encoding='utf-8-sig')
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
    # get_all_stocks()
    # read_stocks()
    # get_hot_sectors()
    get_top_stocks_by_sectors() 