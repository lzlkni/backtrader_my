import akshare as ak
import pandas as pd
from datetime import datetime


def get_stocks():
    """
    获取港股通股票列表
    返回港股通股票的代码和名称
    """
    try:
        # 获取港股实时行情数据
        hk_stocks = ak.stock_hk_spot_em()
        
        # 港股通股票筛选条件：
        # 1. 代码以0开头的股票（港股主板）
        # 2. 排除创业板股票（代码以8开头）
        # 3. 排除停牌股票
        # 4. 排除ST股票
        
        # 筛选主板股票（代码以0开头）
        main_board_stocks = hk_stocks[hk_stocks['代码'].str.startswith('0')]
        
        # 排除创业板股票（代码以8开头）
        main_board_stocks = main_board_stocks[~main_board_stocks['代码'].str.startswith('8')]
        
        # 排除停牌股票（如果状态列存在）
        if '状态' in main_board_stocks.columns:
            main_board_stocks = main_board_stocks[main_board_stocks['状态'] != '停牌']
        
        # 排除ST股票（名称中包含ST的股票）
        main_board_stocks = main_board_stocks[~main_board_stocks['名称'].str.contains('ST', case=False, na=False)]
        
        # 选择代码和名称列
        selected_stocks = main_board_stocks[["代码", "名称"]]
        
        print(f"共获取到 {len(selected_stocks)} 只港股通股票")
        
        # 返回股票代码和名称
        for st in selected_stocks[['代码', '名称']].values.tolist():
            yield st
            
    except Exception as e:
        print(f"获取港股通股票时发生错误: {e}")
        # 备用方案：获取所有港股
        try:
            print("尝试获取所有港股数据...")
            all_hk_stocks = ak.stock_hk_spot_em()
            selected_stocks = all_hk_stocks[["代码", "名称"]]
            
            for st in selected_stocks[['代码', '名称']].values.tolist():
                yield st
        except Exception as e2:
            print(f"获取港股数据也失败: {e2}")
            yield None


def get_hk_connect_stocks():
    """
    获取港股通成分股列表
    使用 stock_hk_ggt_components_em 获取港股通成分股
    """
    try:
        # 获取港股通成分股
        hk_connect_stocks = ak.stock_hk_ggt_components_em()
        
        if hk_connect_stocks.empty:
            print("无法获取港股通成分股数据")
            return pd.DataFrame()
        
        # 检查列名并统一格式
        if '代码' in hk_connect_stocks.columns and '名称' in hk_connect_stocks.columns:
            # 中文列名
            selected_stocks = hk_connect_stocks[["代码", "名称"]]
        elif 'code' in hk_connect_stocks.columns and 'name' in hk_connect_stocks.columns:
            # 英文列名
            selected_stocks = hk_connect_stocks[["code", "name"]]
            selected_stocks.columns = ["代码", "名称"]
        else:
            print("港股通成分股数据格式错误")
            return pd.DataFrame()
        
        # 确保代码格式正确（5位数字）
        selected_stocks = selected_stocks.copy()  # 创建副本避免SettingWithCopyWarning
        selected_stocks['代码'] = selected_stocks['代码'].astype(str).str.zfill(5)
        
        print(f"成功获取 {len(selected_stocks)} 只港股通成分股")
        return selected_stocks
        
    except Exception as e:
        print(f"获取港股通成分股时发生错误: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    # 测试函数
    print("港股通成分股列表:")
    print("代码\t名称")
    print("-" * 30)
    
    # 优先使用港股通成分股
    hk_connect_stocks = get_hk_connect_stocks()
    
    if not hk_connect_stocks.empty:
        print(f"成功获取 {len(hk_connect_stocks)} 只港股通成分股")
        stocks_to_show = hk_connect_stocks
    else:
        print("港股通成分股获取失败，使用备用方法获取港股")
        stocks_to_show = []
        for stock in get_stocks():
            if stock:
                stocks_to_show.append(stock)
            if len(stocks_to_show) >= 50:  # 限制数量
                break
    
    # 保存到CSV文件
    try:
        if isinstance(stocks_to_show, pd.DataFrame):
            # 如果是DataFrame，直接保存
            stocks_to_show.to_csv('hk_stocks.csv', index=False, encoding='utf-8-sig')
            print(f"已将 {len(stocks_to_show)} 只港股通股票保存到 hk_stocks.csv")
        else:
            # 如果是列表，转换为DataFrame后保存
            stocks_df = pd.DataFrame(stocks_to_show, columns=['代码', '名称'])
            stocks_df.to_csv('hk_stocks.csv', index=False, encoding='utf-8-sig')
            print(f"已将 {len(stocks_df)} 只港股通股票保存到 hk_stocks.csv")
    except Exception as e:
        print(f"保存CSV文件时发生错误: {e}")
    
    count = 0
    if isinstance(stocks_to_show, pd.DataFrame):
        for _, row in stocks_to_show.iterrows():
            code, name = row['代码'], row['名称']
            print(f"{code}\t{name}")
            count += 1
            if count >= 20:
                print("...")
                break
    else:
        for stock in stocks_to_show:
            if isinstance(stock, tuple):
                code, name = stock
            else:
                code, name = stock['代码'], stock['名称']
            print(f"{code}\t{name}")
            count += 1
            if count >= 20:
                print("...")
                break
    
    print(f"\n共显示 {count} 只港股通股票")
    
