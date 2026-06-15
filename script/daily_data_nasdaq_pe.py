import json
import os
import time
import urllib.request
from datetime import datetime

import pandas as pd
import pandas_datareader.data as web
import yfinance as yf

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

PE_API_URL = "https://historyofmarket.com/api/ndx/forward-pe.json"
PE_MAX_VALID = 80.0
PE_MIN_VALID = 0.0


def fetch_forward_pe(max_retries=3, retry_delay=2.0):
    """从 historyofmarket.com 拉取 Nasdaq-100 Forward PE 月度序列。"""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                PE_API_URL,
                headers={"User-Agent": "gemini_htmls/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            rows = payload.get("forward") or []
            if not rows:
                raise ValueError("API 返回的 forward 序列为空")
            df = pd.DataFrame(rows)
            df = df.rename(columns={"value": "PE"})
            df["Date"] = pd.to_datetime(df["date"])
            df = df[["Date", "PE"]].sort_values("Date").reset_index(drop=True)
            return df
        except Exception as exc:
            last_err = exc
            if attempt < max_retries:
                print(f"拉取 PE 失败（第 {attempt} 次）: {exc}，{retry_delay}s 后重试...")
                time.sleep(retry_delay)
    raise RuntimeError(
        f"无法从 {PE_API_URL} 获取 PE 数据: {last_err}\n"
        "可手动从 GuruFocus 导出 CSV 后粘贴到计算器。"
    )


def clean_pe_series(pe_df):
    """过滤异常 PE 并用前值填充。"""
    df = pe_df.copy()
    invalid_mask = (df["PE"] <= PE_MIN_VALID) | (df["PE"] > PE_MAX_VALID)
    invalid_count = int(invalid_mask.sum())
    if invalid_count:
        print(f"过滤异常 PE 行数: {invalid_count}（保留范围: {PE_MIN_VALID} < PE <= {PE_MAX_VALID}）")
    df.loc[invalid_mask, "PE"] = pd.NA
    df["PE"] = df["PE"].ffill()
    df = df.dropna(subset=["PE"])
    # 规范为每月第一天，同月多条取最后一条
    df["month_key"] = df["Date"].dt.to_period("M")
    df = df.groupby("month_key", as_index=False).last()
    df["Date"] = df["month_key"].dt.to_timestamp()
    df = df[["Date", "PE"]]
    return df


def download_nasdaq_daily(start_date="2000-01-01", end_date=None):
    """下载 NDX 日频收盘价与 Fed 利率。"""
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    nasdaq = yf.download("^NDX", start=start_date, end=end_date, interval="1d")
    if nasdaq.empty:
        raise ValueError("未获取到 ^NDX 日线数据")
    nasdaq_close = nasdaq[["Close"]].copy()
    nasdaq_close.columns = ["Nasdaq_Close"]
    nasdaq_close.index = pd.to_datetime(nasdaq_close.index).tz_localize(None)

    rates = web.DataReader("FEDFUNDS", "fred", start_date, end_date)
    rates.columns = ["Fed_Rate"]
    rates.index = pd.to_datetime(rates.index)
    rates_daily = rates.reindex(nasdaq_close.index).ffill()

    combined = pd.concat([nasdaq_close, rates_daily], axis=1).dropna()
    return combined


def merge_pe_into_daily(daily_df, pe_df):
    """将月度 PE 按 YYYY-MM 合并到日频数据（前向填充）。"""
    pe_map = {
        d.strftime("%Y-%m"): float(v)
        for d, v in zip(pe_df["Date"], pe_df["PE"])
    }
    daily = daily_df.copy()
    daily.index = pd.to_datetime(daily.index)
    month_keys = daily.index.to_series().dt.strftime("%Y-%m")
    pe_series = month_keys.map(pe_map)
    pe_series = pe_series.ffill()
    daily["PE"] = pe_series.values
    return daily


def download_pe_data(start_date="2000-01-01", end_date=None):
    """拉取 PE 并产出月度 CSV 与四列日频合并 CSV。"""
    stamp = datetime.now().strftime("%Y%m%d")
    print("正在拉取 Nasdaq-100 Forward PE...")
    pe_raw = fetch_forward_pe()
    pe_monthly = clean_pe_series(pe_raw)
    pe_monthly_path = os.path.join(DATA_DIR, f"nasdaq_pe_monthly_{stamp}.csv")
    pe_monthly.to_csv(pe_monthly_path, index=False, date_format="%Y-%m-%d")
    print(f"月度 PE 已保存: {pe_monthly_path}（{len(pe_monthly)} 行）")
    print(pe_monthly.tail())

    print(f"\n正在下载纳指日线并合并 PE（{start_date} 起）...")
    daily = download_nasdaq_daily(start_date=start_date, end_date=end_date)
    merged = merge_pe_into_daily(daily, pe_monthly)
    merged_path = os.path.join(DATA_DIR, f"nasdaq_vs_rates_pe_daily_{stamp}.csv")
    merged.to_csv(merged_path, date_format="%Y-%m-%d")
    pe_coverage = merged["PE"].notna().mean() * 100
    print("-" * 30)
    print(f"四列合并 CSV 已保存: {merged_path}")
    print(f"PE 覆盖率: {pe_coverage:.1f}%")
    print(merged.tail())
    return pe_monthly_path, merged_path


if __name__ == "__main__":
    download_pe_data()
