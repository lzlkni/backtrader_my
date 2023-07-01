import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

wd = webdriver.Chrome(service=Service(r'C:\Users\lzl_k\AppData\Local\Microsoft\WindowsApps\chromedriver.exe'))
wd.implicitly_wait(1)
# 53
wd.get("https://chaoshi.detail.tmall.com/item.htm?spm=a220l.1.0.0.2eb57f33k22QdV&id=20739895092")
# 42
# wd.get("https://chaoshi.detail.tmall.com/item.htm?spm=a3204.7933263.0.0.308d47cczqXxPB&id=655727220256&rewcatid=50514008")

# Lianhua
# wd.get("https://detail.tmall.com/item.htm?id=539845300741&spm=a1z0d.6639537/tb.1997196601.24.4b5b7484PK51Z9&skuId=3199755438654")

input()
# elemet = wd.find_element(By.ID, 'kw')
# elemet.send_keys('tesing')
# wd.switch_to.frame('baxia-dialog-content')
#
#
#
# eName = wd.find_element(By.ID, 'fm-login-id')
# eName.send_keys('lzlkni')
# ePw = wd.find_element(By.ID, 'fm-login-password')
# ePw.send_keys('sugartang1117')

trigger = wd.find_element(By.ID, 'J_LinkBuy')

while trigger.accessible_name != '立即购买':
    print(datetime.datetime.now())

    trigger = wd.find_element(By.ID, 'J_LinkBuy')

trigger.click()
print('done: ' + str(datetime.datetime.now()))

input()
order = wd.find_element(By.CLASS_NAME, "go-btn")
order.click()
print('ordered: ' + str(datetime.datetime.now()))

time.sleep(15)
wd.quit()