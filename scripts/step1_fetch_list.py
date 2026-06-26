#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速获取全A股列表 + 预计算筛选指标
"""
import os, sys, time, warnings
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import requests
warnings.filterwarnings('ignore')

os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
_orig = requests.Session.__init__
def _p(self, *a, **k):
    _orig(self, *a, **k)
    self.trust_env = False
requests.Session.__init__ = _p

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'data')

print("获取全A股列表...", flush=True)
import akshare as ak

df_list = ak.stock_zh_a_spot_em()
print(f"  spot_em 返回 {len(df_list)} 只", flush=True)

if '代码' in df_list.columns:
    df_list = df_list.rename(columns={'代码': 'code', '名称': 'name'})
df_list['code'] = df_list['code'].astype(str).str.zfill(6)
df_list = df_list[~df_list['name'].str.contains('ST|退|N', na=False)]
df_list = df_list[~df_list['code'].str.startswith('8')]
df_list = df_list[~df_list['code'].str.startswith('4')]
df_list = df_list[df_list['code'].str.match(r'^(0|3|6)')]
print(f"  过滤后: {len(df_list)} 只", flush=True)

df_list[['code', 'name']].to_csv(os.path.join(DATA_DIR, 'all_stocks_filtered.csv'), index=False, encoding='utf-8-sig')
print(f"  已保存 all_stocks_filtered.csv", flush=True)
