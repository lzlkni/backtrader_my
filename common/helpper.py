import akshare as ak
import pandas as pd
import time

def get_top_10_concepts_by_increase():
    """
    获取同花顺所有概念板块，并返回按涨幅排序的前10名板块
    """
    try:
        # 1. 获取所有板块列表
        concept_df = ak.stock_board_concept_name_ths()
        
        if concept_df is None or concept_df.empty:
            print("无法获取同花顺概念板块列表")
            return None

        # 打印列名用于调试
        print(f"获取到的列名: {concept_df.columns.tolist()}")
        
        # 确定概念名称和代码的列名（处理可能的列名变化）
        concept_name_col = None
        code_col = None
        
        # 可能的列名变体
        possible_name_cols = ['概念名称', '板块名称', 'name', '名称']
        possible_code_cols = ['代码', '板块代码', 'code', '指数代码']
        
        for col in possible_name_cols:
            if col in concept_df.columns:
                concept_name_col = col
                break
        
        for col in possible_code_cols:
            if col in concept_df.columns:
                code_col = col
                break
        
        if concept_name_col is None:
            print(f"错误：无法找到概念名称列。可用列名: {concept_df.columns.tolist()}")
            return None

        # 2. 获取每个板块的涨幅信息
        # 创建保存结果的列表
        concept_gains = []
        for idx, row in concept_df.iterrows():
            concept_name = row[concept_name_col]
            print(concept_name)
            try:
                info = ak.stock_board_concept_info_ths(symbol=concept_name)
                # 部分接口可能返回空，跳过
                if info is not None and not info.empty:
                    # 概念整体涨跌幅, 通常在'涨跌幅' 或 '板块涨幅'字段里
                    if '涨跌幅' in info.columns:
                        gain = info['涨跌幅'].iloc[0]
                    elif '板块涨幅' in info.columns:
                        gain = info['板块涨幅'].iloc[0]
                    else:
                        gain = None
                    concept_gains.append({
                        '概念名称': concept_name,
                        '板块代码': row[code_col] if code_col and code_col in row else None,
                        '涨跌幅': gain
                    })
            except Exception as e:
                print(f"获取板块 {concept_name} 涨幅信息失败: {e}")
                continue

            time.sleep(10)

        # 转为DataFrame
        result_df = pd.DataFrame(concept_gains)
        # 去除没有涨跌幅的
        result_df = result_df[result_df['涨跌幅'].notnull()]
        # 某些接口返回格式为字符串带"%"，统一数值型
        def parse_gain(val):
            if isinstance(val, str):
                return float(val.strip('%'))
            return float(val)
        result_df['涨跌幅'] = result_df['涨跌幅'].map(parse_gain)

        # 3. 排序并返回前10
        result_df = result_df.sort_values('涨跌幅', ascending=False).head(10).reset_index(drop=True)
        return result_df

    except Exception as e:
        print(f"获取热门概念板块信息出错：{e}")
        return None

if __name__ == "__main__":
    top10 = get_top_10_concepts_by_increase()
    print(top10)