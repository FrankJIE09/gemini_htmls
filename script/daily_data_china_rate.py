import os
import pandas_datareader.data as web
import pandas as pd
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

def download_china_rate(start_date="1990-01-01", end_date="2025-12-31"):
    """从 FRED 下载中国贴现率 (INTDSRCNM193N)，月度数据。"""
    print(f"开始获取中国利率：从 {start_date} 到 {end_date}...")
    try:
        rates = web.DataReader("INTDSRCNM193N", "fred", start_date, end_date)
        rates.columns = ['China_Rate']
        filename = os.path.join(DATA_DIR, f"china_rate_{datetime.now().strftime('%Y%m%d')}.csv")
        rates.to_csv(filename)
        print(f"成功！已保存至: {filename}")
        print(rates.tail())
    except Exception as e:
        print(f"获取数据时发生错误: {e}")
        print("安装: pip install pandas_datareader pandas")

if __name__ == "__main__":
    download_china_rate()
