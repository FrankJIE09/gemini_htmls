import os
import re
import time
import argparse
import urllib.request
from datetime import datetime, timezone
from collections import OrderedDict

import pandas as pd
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

MULT_PE_URL = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
CURRENT_PE_URL = "https://www.multpl.com/s-p-500-pe-ratio"


def fetch_table_html(url, max_retries=3, retry_delay=3.0):
    """从 multpl.com 下载 PE 表格 HTML"""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            return html
        except Exception as exc:
            last_err = exc
            if attempt < max_retries:
                print(f"下载失败（第 {attempt} 次）: {exc}，{retry_delay}s 后重试...")
                time.sleep(retry_delay)
    raise RuntimeError(f"无法从 {url} 获取数据: {last_err}")


def extract_current_pe(html):
    """从首页 HTML 提取当前 PE 值"""
    m = re.search(r'Current S&P 500 PE Ratio:\s*([\d.]+)', html)
    if m:
        return float(m.group(1))
    m = re.search(r'PE Ratio\s*</a>\s*</h1>\s*<span[^>]*>([\d.]+)', html, re.DOTALL)
    if m:
        return float(m.group(1))
    return None


def extract_pe_table(html):
    """从 multpl HTML 表格中提取日期和 PE 值"""
    rows = []
    # 查找 <table id="datatable"> ... </table>
    table_match = re.search(r'<table[^>]*id="datatable"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not table_match:
        print("警告：未找到 datatable")
        return pd.DataFrame(columns=["Date", "PE"])

    table_html = table_match.group(1)

    # 匹配 <tr class="odd"> 或 <tr class="even">
    tr_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)
    for tr_match in tr_pattern.finditer(table_html):
        tr_content = tr_match.group(1)
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr_content, re.DOTALL)
        if len(tds) < 2:
            continue

        # 处理日期 td
        date_text = re.sub(r'<[^>]+>', '', tds[0]).strip()
        # 处理值 td (去掉 <abbr>, &#x2002; 等)
        value_text = re.sub(r'<[^>]+>', '', tds[1]).strip()
        value_text = value_text.replace('&#x2002;', '').replace('†', '').strip()

        try:
            # 解析日期: "Jun 26, 2026" 或 "Jun 1, 2026"
            dt = pd.to_datetime(date_text, format="%b %d, %Y", errors="coerce")
            if pd.isna(dt):
                dt = pd.to_datetime(date_text, format="%b %d %Y", errors="coerce")
            if pd.isna(dt):
                continue
            value = float(value_text)
            rows.append((dt, value))
        except (ValueError, TypeError):
            continue

    if not rows:
        print("警告：未从 HTML 中解析出任何 PE 数据行")
        return pd.DataFrame(columns=["Date", "PE"])

    df = pd.DataFrame(rows, columns=["Date", "PE"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def compute_percentiles(pe_series, current_pe):
    """计算当前 PE 在给定序列中的百分位"""
    if len(pe_series) == 0 or current_pe is None:
        return None
    # 计算严格小于当前值的比例
    pct_less = (pe_series < current_pe).sum() / len(pe_series) * 100
    # 计算严格大于当前值的比例
    pct_greater = (pe_series > current_pe).sum() / len(pe_series) * 100
    pct_equal = (pe_series == current_pe).sum() / len(pe_series) * 100
    return {
        "current_pe": current_pe,
        "count": len(pe_series),
        "min": float(np.min(pe_series)),
        "max": float(np.max(pe_series)),
        "mean": float(np.mean(pe_series)),
        "median": float(np.median(pe_series)),
        "std": float(np.std(pe_series, ddof=1)),
        "percentile_less": round(pct_less, 1),
        "percentile_greater": round(pct_greater, 1),
        "percentile_equal": round(pct_equal, 1),
        "percentile_rank": round(pct_less + pct_equal / 2, 1),
    }


def format_percentile_result(label, stats):
    """格式化输出"""
    if stats is None:
        return f"{label}: 数据不足"
    lines = [
        f"\n{'=' * 50}",
        f"  {label}",
        f"{'=' * 50}",
        f"  当前 PE:         {stats['current_pe']:.2f}",
        f"  数据点数:         {stats['count']}",
        f"  最小值:           {stats['min']:.2f}",
        f"  最大值:           {stats['max']:.2f}",
        f"  平均值:           {stats['mean']:.2f}",
        f"  中位数:           {stats['median']:.2f}",
        f"  标准差:           {stats['std']:.2f}",
        f"  低于当前 PE 占比: {stats['percentile_less']:.1f}%",
        f"  高于当前 PE 占比: {stats['percentile_greater']:.1f}%",
        f"  等于当前 PE 占比: {stats['percentile_equal']:.1f}%",
        f"  → 历史分位:      {stats['percentile_rank']:.1f}%",
        f"  （{stats['percentile_rank']:.1f}% 的历史数据低于当前 PE）",
    ]
    if stats['percentile_rank'] >= 90:
        lines.append(f"  ⚠️  当前 PE 处于历史高位（>90% 分位）")
    elif stats['percentile_rank'] <= 10:
        lines.append(f"  ✅ 当前 PE 处于历史低位（<10% 分位）")
    return "\n".join(lines)


def run_analysis():
    print("=" * 50)
    print("  标普 500 PE 数据下载与历史分位分析")
    print("=" * 50)

    stamp = datetime.now().strftime("%Y%m%d")

    # 1. 下载表格 HTML
    print(f"\n正在从 multpl.com 下载 PE 历史数据...")
    print(f"URL: {MULT_PE_URL}")
    table_html = fetch_table_html(MULT_PE_URL)

    # 2. 提取 PE 数据
    pe_df = extract_pe_table(table_html)
    print(f"\n成功提取 {len(pe_df)} 条月度 PE 数据")
    if len(pe_df) > 0:
        print(f"时间范围: {pe_df['Date'].min().date()} ~ {pe_df['Date'].max().date()}")
    else:
        print("警告：未能解析任何 PE 数据！")

    # 3. 获取当前 PE
    print(f"\n正在获取当前 PE...")
    current_html = fetch_table_html(CURRENT_PE_URL)
    current_pe = extract_current_pe(current_html)
    if current_pe is None and not pe_df.empty:
        current_pe = float(pe_df.iloc[-1]["PE"])
        print(f"  从表格取最新 PE: {current_pe:.2f}")
    else:
        print(f"  当前 PE: {current_pe:.2f}")

    # 4. 保存 CSV
    csv_path = os.path.join(DATA_DIR, f"sp500_pe_monthly_{stamp}.csv")
    pe_df.to_csv(csv_path, index=False, date_format="%Y-%m-%d")
    print(f"\n月度 PE 数据已保存: {csv_path}")

    # 5. 计算各时间范围的分位
    pe_series = pe_df["PE"].values

    # 全部历史
    all_time_stats = compute_percentiles(pe_series, current_pe)
    print(format_percentile_result("全部历史", all_time_stats))

    # 最近 20 年
    cutoff_20y = datetime.now() - pd.DateOffset(years=20)
    pe_20y = pe_df[pe_df["Date"] >= cutoff_20y]["PE"].values
    stats_20y = compute_percentiles(pe_20y, current_pe)
    print(format_percentile_result(f"最近 20 年（{cutoff_20y.date()} 至今）", stats_20y))

    # 最近 10 年
    cutoff_10y = datetime.now() - pd.DateOffset(years=10)
    pe_10y = pe_df[pe_df["Date"] >= cutoff_10y]["PE"].values
    stats_10y = compute_percentiles(pe_10y, current_pe)
    print(format_percentile_result(f"最近 10 年（{cutoff_10y.date()} 至今）", stats_10y))

    # 最近 5 年
    cutoff_5y = datetime.now() - pd.DateOffset(years=5)
    pe_5y = pe_df[pe_df["Date"] >= cutoff_5y]["PE"].values
    stats_5y = compute_percentiles(pe_5y, current_pe)
    print(format_percentile_result(f"最近 5 年（{cutoff_5y.date()} 至今）", stats_5y))

    # 6. 汇总
    print(f"\n{'=' * 50}")
    print("  汇总")
    print(f"{'=' * 50}")
    print(f"  当前 S&P 500 PE:        {current_pe:.2f}")
    print(f"  {'范围':<25} {'分位':>10}")
    print(f"  {'-' * 35}")
    for label, stats in [
        ("全部历史", all_time_stats),
        ("最近 20 年", stats_20y),
        ("最近 10 年", stats_10y),
        ("最近 5 年", stats_5y),
    ]:
        if stats:
            pct = stats["percentile_rank"]
            bar_len = int(pct / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  {label:<20} {pct:>6.1f}%  {bar}")

    # 7. 输出 LaTeX 表格（供文档使用）
    print(f"\n{'=' * 50}")
    print("  LaTeX 表格")
    print(f"{'=' * 50}")
    latex_lines = [
        "\\begin{table}[h]",
        "\\centering",
        "\\begin{tabular}{lcccccc}",
        "\\toprule",
        "范围 & 数据点数 & 最小值 & 最大值 & 平均值 & 中位数 & 历史分位 \\\\",
        "\\midrule",
    ]
    for label, stats in [
        ("全部历史", all_time_stats),
        ("最近 20 年", stats_20y),
        ("最近 10 年", stats_10y),
        ("最近 5 年", stats_5y),
    ]:
        if stats:
            latex_lines.append(
                f"{label} & {stats['count']} & {stats['min']:.1f} & {stats['max']:.1f} "
                f"& {stats['mean']:.1f} & {stats['median']:.1f} & {stats['percentile_rank']:.1f}\\% \\\\"
            )
    latex_lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        f"\\caption{{S\\&P 500 PE 历史分位分析（当前 PE = {current_pe:.2f}，{datetime.now().strftime('%Y-%m-%d')}）}}",
        "\\end{table}",
    ])
    print("\n".join(latex_lines))

    print("\n✅ 分析完成！")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="标普500 PE 数据下载与历史分位分析")
    args = parser.parse_args()
    run_analysis()
