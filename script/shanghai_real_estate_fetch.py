#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 akshare 拉取 2015 年至今的上海楼市相关数据并保存为 CSV。
需要: pip install akshare pandas
"""

import os
from datetime import datetime

import akshare as ak
import pandas as pd

# 输出目录
OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT_DIR, exist_ok=True)
START_DATE = "2015-01-01"


def fetch_shanghai_house_price():
    """上海新建商品住宅、二手住宅价格指数（月度，含同比/环比/定基）。"""
    print("拉取: 全国新建/二手住宅价格指数（含上海）...")
    df = ak.macro_china_new_house_price()
    df["日期"] = pd.to_datetime(df["日期"])
    sh = df[df["城市"] == "上海"].copy()
    sh = sh[sh["日期"] >= START_DATE].sort_values("日期").reset_index(drop=True)
    out_path = os.path.join(OUT_DIR, "shanghai_house_price_index.csv")
    sh.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  已保存: {out_path}，共 {len(sh)} 条（{sh['日期'].min().strftime('%Y-%m')} ~ {sh['日期'].max().strftime('%Y-%m')}）")
    return sh


def fetch_china_real_estate_index():
    """全国房地产景气指数（月度）。"""
    print("拉取: 全国房地产景气指数...")
    df = ak.macro_china_real_estate()
    df["日期"] = pd.to_datetime(df["日期"])
    df = df[df["日期"] >= START_DATE].sort_values("日期").reset_index(drop=True)
    out_path = os.path.join(OUT_DIR, "china_real_estate_index.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  已保存: {out_path}，共 {len(df)} 条")
    return df


def _nbs_wide_to_long(df_nation, df_region, region_name):
    """将统计局宽表（月份为列）转为长表：日期、地区、指标、值。"""
    def wide_to_long(df, region):
        df = df.reset_index()
        df = df.rename(columns={df.columns[0]: "指标"})
        long = df.melt(id_vars=["指标"], var_name="月份", value_name="值")
        long["地区"] = region
        long["月份"] = long["月份"].str.replace("年", "-").str.replace("月", "")
        long["日期"] = pd.to_datetime(long["月份"] + "-01", errors="coerce")
        long = long.dropna(subset=["日期"])
        return long[["日期", "地区", "指标", "值"]]
    out = []
    if df_nation is not None and len(df_nation) > 0:
        out.append(wide_to_long(df_nation, "全国"))
    if df_region is not None and len(df_region) > 0:
        df_region = df_region.droplevel(0, axis=0) if df_region.index.nlevels > 1 else df_region
        out.append(wide_to_long(df_region, region_name))
    if not out:
        return pd.DataFrame()
    return pd.concat(out, ignore_index=True).sort_values(["地区", "指标", "日期"])


def fetch_sales_area():
    """全国 + 上海市 商品房/商品住宅 销售面积（月度累计值、累计增长）。"""
    print("拉取: 全国及上海市 商品房销售面积...")
    df_nation = ak.macro_china_nbs_nation("月度数据", "房地产>商品房销售面积", period="2015-")
    df_sh = ak.macro_china_nbs_region(
        "分省月度数据", "房地产>商品房销售面积",
        indicator=None, region="上海市", period="2015-"
    )
    long = _nbs_wide_to_long(df_nation, df_sh, "上海市")
    if long.empty:
        print("  未获取到数据")
        return long
    out_path = os.path.join(OUT_DIR, "shanghai_sales_area.csv")
    long.to_csv(out_path, index=False, encoding="utf-8-sig")
    n_sh = long[(long["地区"] == "上海市") & (long["指标"].str.contains("累计值", na=False))]
    n_dates = n_sh["日期"].nunique()
    print(f"  已保存: {out_path}，共 {len(long)} 条（含全国+上海市，{n_dates} 个月）")
    _write_sales_area_chart_json(long)
    return long


def _monthly_from_cumulative(dates_ser, vals_ser):
    """从自年初累计得到当月值：当月[i] = 累计[i] - 累计[i-1]（仅当同一年且上月存在时）。"""
    dates = dates_ser.astype(str).tolist()
    vals = vals_ser.tolist()
    out = []
    for i in range(len(dates)):
        if i == 0:
            out.append(None)
            continue
        a, b = dates[i - 1][:7], dates[i][:7]
        y1, m1 = int(a[:4]), int(a[5:7])
        y2, m2 = int(b[:4]), int(b[5:7])
        if y1 == y2 and m2 == m1 + 1:
            out.append(round(float(vals[i]) - float(vals[i - 1]), 2))
        else:
            out.append(None)
    return out


def _write_sales_area_chart_json(long_df):
    """从销售面积长表生成图表用 JSON（上海：总/现房/期房），输出当月值（本月累计-上月累计）。"""
    import json
    long_df = long_df.copy()
    long_df["值"] = pd.to_numeric(long_df["值"], errors="coerce")
    sh = long_df[
        (long_df["地区"] == "上海市")
        & (long_df["指标"].str.contains("累计值", na=False))
        & (long_df["指标"].str.contains("万平方米", na=False))
    ].dropna(subset=["值"])
    total = sh[sh["指标"] == "商品房销售面积_累计值(万平方米)"].sort_values("日期").reset_index(drop=True)
    xian = sh[sh["指标"] == "商品房现房销售面积_累计值(万平方米)"].sort_values("日期").reset_index(drop=True)
    if total.empty or xian.empty:
        return
    common = total.merge(xian, on="日期", suffixes=("_total", "_xian"))
    common = common.sort_values("日期").reset_index(drop=True)
    dates = common["日期"].astype(str).tolist()
    total_monthly = _monthly_from_cumulative(common["日期"], common["值_total"])
    xian_monthly = _monthly_from_cumulative(common["日期"], common["值_xian"])
    qi_monthly = []
    for i in range(len(dates)):
        if total_monthly[i] is not None and xian_monthly[i] is not None:
            qi_monthly.append(round(total_monthly[i] - xian_monthly[i], 2))
        else:
            qi_monthly.append(None)
    out = {
        "dates": dates,
        "total": total_monthly,
        "xianfang": xian_monthly,
        "qifang": qi_monthly,
    }
    json_path = os.path.join(OUT_DIR, "shanghai_sales_area_chart.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    print(f"  已生成图表数据（当月口径）: {json_path}")


def main():
    print("上海楼市数据拉取（2015 年至今）")
    print("-" * 50)
    fetch_shanghai_house_price()
    fetch_china_real_estate_index()
    fetch_sales_area()
    print("-" * 50)
    print("完成。")


if __name__ == "__main__":
    main()
