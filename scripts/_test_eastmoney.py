import requests
import json

s = requests.Session()
s.trust_env = False

url = "https://push2.eastmoney.com/api/qt/clist/get"
params = {
    "pn": 1, "pz": 5, "po": 1, "np": 1,
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "fltt": 2, "invt": 2, "fid": "f12",
    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
    "fields": "f12,f14",
}
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
r = s.get(url, params=params, headers=headers, timeout=15)
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:1000]}")
