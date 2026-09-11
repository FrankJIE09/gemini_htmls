"""
标普500指数市盈率(PE)历史分位数测算
====================================
数据源:
  - 标普500月度PE历史: multpl.com (免费公开数据，1871年至今)
  - 最新PE确认: yfinance 读取 ^GSPC 实时收盘价，与 multpl 最新PE交叉验证

时间范围: 最近20年 (月度数据)
标的: ^GSPC (标普500指数)

关键计算:
  - 分位数 = (小于当前PE的样本数量 ÷ 区间总样本数) × 100
  - 输出4个区间: 全部历史 / 近5年 / 近10年 / 近20年

依赖安装: pip install yfinance pandas numpy matplotlib requests beautifulsoup4
"""

import pandas as pd
import numpy as np
import warnings
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

# ============================================================
# 第一部分：数据获取
# ============================================================

# --- Multpl 标普500月度PE数据 ---
MULTPL_PE_URL = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"


def fetch_multpl_pe_data():
    """
    从 multpl.com 抓取标普500月度PE数据。
    该数据集覆盖 1871年至今，是量化分析中常用的免费PE数据源。

    返回:
      pd.DataFrame, 列: ['pe'], index: datetime (月末)
    """
    print(f"正在从 multpl.com 获取标普500月度PE数据...")
    print(f"  数据源: {MULTPL_PE_URL}")

    try:
        resp = requests.get(MULTPL_PE_URL, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"网络请求失败，无法获取 multpl.com 数据: {e}")

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tr")
    except Exception as e:
        raise RuntimeError(f"页面解析失败: {e}")

    if not rows or len(rows) < 2:
        raise RuntimeError("未找到PE数据表格，页面结构可能已变更。")

    records = []
    for row in rows[1:]:  # 跳过表头
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        date_str = cells[0].get_text(strip=True)
        pe_str = cells[1].get_text(strip=True).replace("†", "").replace(",", "")
        try:
            pe_val = float(pe_str)
        except ValueError:
            continue  # 跳过无法转换的行
        records.append((date_str, pe_val))

    if not records:
        raise RuntimeError("表格解析成功但未提取到有效数据。")

    # 日期解析: "Jun 26, 2026" -> datetime
    df = pd.DataFrame(records, columns=["date_str", "pe"])
    df["date"] = pd.to_datetime(df["date_str"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.set_index("date").sort_index()

    print(f"  成功获取 {len(df)} 条月度PE数据")
    print(f"  时间范围: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")

    return df[["pe"]]


def fetch_recent_price_from_yfinance():
    """
    用 yfinance 获取 ^GSPC 最新收盘价，与 multpl PE 交叉验证。
    如果 yfinance 不可用，不影响主流程。
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker("^GSPC")
        hist = ticker.history(period="5d")
        if hist.empty:
            return None, None
        latest_close = hist["Close"].iloc[-1]
        latest_date = hist.index[-1]
        return latest_close, latest_date
    except Exception:
        return None, None


# ============================================================
# 第二部分：数据切片与清洗
# ============================================================

def slice_latest_20years(df):
    """
    截取最近20年的月度数据。
    同时保留完整历史用于参考。
    """
    now = pd.Timestamp.now()
    cutoff = now - pd.DateOffset(years=20)
    df_20y = df[df.index >= cutoff].copy()
    print(f"\n截取最近20年数据: {df_20y.index[0].strftime('%Y-%m')} ~ {df_20y.index[-1].strftime('%Y-%m')}")
    print(f"  月度样本数: {len(df_20y)}")
    return df_20y


def clean_pe_data(df):
    """
    数据清洗：
      1. 剔除 PE > 200 的极端异常
      2. 剔除 PE < 0 的无效值
      3. 剔除 PE 为空的行
      4. 线性插值填充少量空值
    """
    df = df.copy()
    n_before = len(df)

    # 剔除异常值
    df = df[df["pe"] > 0]
    df = df[df["pe"] <= 200]

    n_after = len(df)
    print(f"  清洗: 剔除异常样本 {n_before - n_after} 个 (PE≤0 或 PE>200)")

    # 插值填充NaN
    before_interp = df["pe"].isna().sum()
    df["pe"] = df["pe"].interpolate(method="linear")
    after_interp = df["pe"].isna().sum()
    filled = before_interp - after_interp
    if filled > 0:
        print(f"  插值填充空值: {filled} 个")

    return df


# ============================================================
# 第三部分：分位数计算（核心逻辑）
# ============================================================

def compute_percentile(current_value, historical_values):
    """
    计算当前值在历史分布中的分位数。

    公式: 分位 = (小于当前值的样本数量 ÷ 总样本数) × 100

    参数:
      current_value: 当前PE值 (标量)
      historical_values: 历史PE序列 (array-like)

    返回:
      percentile: 保留2位小数的百分数 (如 85.50 表示 85.50%)
    """
    count_less = np.sum(historical_values < current_value)
    total = len(historical_values)
    percentile = (count_less / total) * 100
    return round(percentile, 2)


def calculate_all_percentiles(df_full, df_20y):
    """
    计算全部四个区间的分位数指标：

    ① 全部历史样本分位 —— 完整数据集（1871年至今）全部样本
    ② 近5年区间分位    —— 仅筛选最近5年样本
    ③ 近10年区间分位   —— 仅筛选最近10年样本
    ④ 近20年区间分位   —— 最近20年全部样本

    分位计算逻辑:
      对每个区间，取该区间所有PE样本，计算：
        分位 = (小于当前PE的样本数 / 区间总样本数) × 100

    参数:
      df_full: 完整历史数据集（含20年以前的数据），用于计算①全部历史分位
      df_20y:  最近20年数据集，用于计算②③④

    返回: dict 包含各区间统计结果
    """
    df_full = df_full.sort_index()
    df_20y = df_20y.sort_index()

    # 从20年数据中获取当期PE（最新一期）
    latest_date = df_20y.index[-1]
    current_pe = round(df_20y["pe"].iloc[-1], 2)
    pe_full_all = df_full["pe"].values  # 全部历史PE数组
    pe_20y_all = df_20y["pe"].values    # 近20年PE数组

    print(f"\n{'='*60}")
    print(f"  当前最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
    print(f"  当前PE (current_pe): {current_pe}")
    print(f"{'='*60}")

    now = pd.Timestamp.now()

    # ── ① 全部历史样本分位（1871年至今完整样本） ──
    p_all = compute_percentile(current_pe, pe_full_all)
    print(f"\n  [全部历史]   样本数={len(pe_full_all)}, 当前PE分位={p_all}%")

    # ── ② 近5年区间分位 ──
    mask_5y = df_20y.index >= (now - pd.DateOffset(years=5))
    pe_5y = df_20y.loc[mask_5y, "pe"].values
    p_5y = compute_percentile(current_pe, pe_5y) if len(pe_5y) > 0 else None
    print(f"  [近5年]      样本数={len(pe_5y)}, 当前PE分位={p_5y}%")

    # ── ③ 近10年区间分位 ──
    mask_10y = df_20y.index >= (now - pd.DateOffset(years=10))
    pe_10y = df_20y.loc[mask_10y, "pe"].values
    p_10y = compute_percentile(current_pe, pe_10y) if len(pe_10y) > 0 else None
    print(f"  [近10年]     样本数={len(pe_10y)}, 当前PE分位={p_10y}%")

    # ── ④ 近20年区间分位（仅20年样本） ──
    p_20y = compute_percentile(current_pe, pe_20y_all)
    print(f"  [近20年]     样本数={len(pe_20y_all)}, 当前PE分位={p_20y}%")

    # 组合统计结果
    stats = {
        "全部历史": _build_stats_entry(current_pe, pe_full_all, p_all),
        "近5年": _build_stats_entry(current_pe, pe_5y, p_5y),
        "近10年": _build_stats_entry(current_pe, pe_10y, p_10y),
        "近20年": _build_stats_entry(current_pe, pe_20y_all, p_20y),
    }

    return stats


def _build_stats_entry(current_pe, pe_array, percentile):
    """构建单个区间的统计字典"""
    entry = {
        "样本数": len(pe_array),
        "当前PE": current_pe,
        "分位(%)": percentile,
    }
    if len(pe_array) > 0:
        entry.update({
            "最小PE": round(np.min(pe_array), 2),
            "25%分位": round(np.percentile(pe_array, 25), 2),
            "50%分位(中位数)": round(np.percentile(pe_array, 50), 2),
            "75%分位": round(np.percentile(pe_array, 75), 2),
            "最大PE": round(np.max(pe_array), 2),
        })
    else:
        entry.update({
            "最小PE": "N/A",
            "25%分位": "N/A",
            "50%分位(中位数)": "N/A",
            "75%分位": "N/A",
            "最大PE": "N/A",
        })
    return entry


# ============================================================
# 第四部分：格式化输出
# ============================================================

def print_results_table(stats):
    """以对齐表格形式打印全部分位数测算结果"""
    print("\n" + "=" * 90)
    print("  标普500 市盈率(PE) 历史分位数测算结果")
    print("=" * 90)

    header = (
        f"{'区间':<18} {'样本数':<8} {'当前PE':<10} {'分位(%)':<10} "
        f"{'最小PE':<8} {'25%分位':<8} {'中位数':<10} {'75%分位':<8} {'最大PE':<8}"
    )
    print(header)
    print("-" * 90)

    for interval_name, data in stats.items():
        pct = data["分位(%)"]
        pct_str = f"{pct}%" if pct is not None else "  N/A  "
        row = (
            f"{interval_name:<18} "
            f"{data['样本数']:<8} "
            f"{data['当前PE']:<10} "
            f"{pct_str:<10} "
            f"{str(data['最小PE']):<8} "
            f"{str(data['25%分位']):<8} "
            f"{str(data['50%分位(中位数)']):<10} "
            f"{str(data['75%分位']):<8} "
            f"{str(data['最大PE']):<8}"
        )
        print(row)

    print("-" * 90)

    # 估值水平判定
    curr_pe = stats["全部历史"]["当前PE"]
    all_pct = stats["全部历史"]["分位(%)"]

    if all_pct <= 20:
        level = "低估区间 (分位≤20%)"
    elif all_pct <= 40:
        level = "偏低区间 (20%<分位≤40%)"
    elif all_pct <= 60:
        level = "中等区间 (40%<分位≤60%)"
    elif all_pct <= 80:
        level = "偏高区间 (60%<分位≤80%)"
    else:
        level = "高估区间 (分位>80%)"

    print(f"\n  综合判定: 当前PE={curr_pe}，处于全部历史 {all_pct}% 分位 → {level}")
    print(f"  说明: 分位越低表示当前估值越便宜，越高表示越贵。")
    print("=" * 90)


# ============================================================
# 第五部分：可视化
# ============================================================

def plot_pe_history(df, stats):
    """
    绘制20年PE走势图，包含：
      - PE历史曲线
      - 当前PE水平线标注
      - 5年/10年/全部区间上下限
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("\n⚠️ matplotlib 未安装，跳过可视化。可运行: pip install matplotlib")
        return

    df = df.sort_index()
    fig, ax = plt.subplots(figsize=(15, 7))

    # ── 主曲线：全部PE ──
    ax.plot(df.index, df["pe"], color="#1976D2", linewidth=1.5, label="PE (月度)", alpha=0.85)

    # ── 当前PE水平线 ──
    current_pe = stats["全部历史"]["当前PE"]
    ax.axhline(y=current_pe, color="#D32F2F", linestyle="--", linewidth=2, label=f"当前PE = {current_pe}", zorder=5)

    # 当前PE数值标注
    ax.annotate(
        f"当前PE: {current_pe}",
        xy=(df.index[-1], current_pe),
        xytext=(df.index[-1], current_pe * 1.15),
        fontsize=11,
        fontweight="bold",
        color="#D32F2F",
        ha="center",
        va="bottom",
        arrowprops=dict(arrowstyle="->", color="#D32F2F", lw=1.8),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#D32F2F", alpha=0.9),
    )

    # ── 绘制5年/10年区间上下限标注 ──
    now = pd.Timestamp.now()
    intervals = [
        ("近5年", now - pd.DateOffset(years=5), "#388E3C"),
        ("近10年", now - pd.DateOffset(years=10), "#F57C00"),
        ("近20年", df.index[0], "#1976D2"),
    ]

    plotted_labels = set()

    for label, start_date, color in intervals:
        sub_df = df[df.index >= start_date]
        if sub_df.empty:
            continue
        sub_pe = sub_df["pe"]
        p_min, p_max = sub_pe.min(), sub_pe.max()

        # 透明区域渲染区间
        ax.fill_between(
            sub_df.index, p_min, p_max,
            alpha=0.06, color=color, zorder=1,
        )

        # 标注区间上下限
        label_text = f"{label}: [{p_min:.1f} ~ {p_max:.1f}]"
        if label_text not in plotted_labels:
            plotted_labels.add(label_text)
            mid_idx = len(sub_df) // 2
            mid_x = sub_df.index[mid_idx]
            ax.annotate(
                label_text,
                xy=(mid_x, p_max),
                xytext=(mid_x, p_max * 1.30),
                fontsize=9, color=color, ha="center", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=color, alpha=0.85),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.2, alpha=0.7),
            )

    # ── 图表装饰 ──
    ax.set_title(
        "标普500指数 市盈率(PE)月度走势 及 历史分位区间",
        fontsize=15, fontweight="bold", pad=15,
    )
    ax.set_xlabel("日期", fontsize=12)
    ax.set_ylabel("市盈率 (PE Ratio)", fontsize=12)
    ax.legend(loc="upper left", fontsize=10, framealpha=0.9)
    ax.grid(True, alpha=0.25, linestyle="--")

    # X轴格式
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.autofmt_xdate()

    plt.tight_layout()
    plt.show()
    print("\n📊 PE走势图已显示。")


# ============================================================
# 第六部分：主流程
# ============================================================

def main():
    """主函数：串联数据获取→清洗→分位数计算→输出→可视化"""
    print("=" * 60)
    print("  标普500 PE 历史分位数测算工具")
    print("  数据源: multpl.com (公开PE数据) + yfinance (价格验证)")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ── Step 1: 获取 Multpl PE 数据 ──
    try:
        df_full = fetch_multpl_pe_data()
    except RuntimeError as e:
        print(f"\n❌ 数据获取失败: {e}")
        print("  请检查网络连接后重试。")
        return

    # ── Step 1.5: yfinance 价格交叉验证 ──
    try:
        price, price_date = fetch_recent_price_from_yfinance()
        if price is not None:
            latest_pe = df_full["pe"].iloc[-1]
            implied_price = latest_pe  # PE ratio 本身不需要价格验证
            print(f"\n  yfinance 交叉验证: ^GSPC 最新收盘价 ≈ {price:.2f} ({price_date.strftime('%Y-%m-%d')})")
            print(f"  Multpl 最新PE = {latest_pe:.2f}")
    except Exception:
        pass  # yfinance 验证非关键，静默处理

    # ── Step 2: 截取最近20年 ──
    df_20y = slice_latest_20years(df_full)

    # ── Step 3: 数据清洗 ──
    df_20y = clean_pe_data(df_20y)

    if len(df_20y) < 12:
        print("❌ 有效月度样本不足12个，无法进行有意义的分析。")
        return

    print(f"\n  数据时间范围: {df_20y.index[0].strftime('%Y-%m-%d')} ~ {df_20y.index[-1].strftime('%Y-%m-%d')}")
    print(f"  有效月度样本: {len(df_20y)} 个")

    # ── Step 4: 计算分位数（传入完整历史和20年数据集） ──
    stats = calculate_all_percentiles(df_full, df_20y)

    # ── Step 5: 表格输出 ──
    print_results_table(stats)

    # ── Step 6: 可视化 ──
    plot_pe_history(df_20y, stats)

    print("\n✅ 分析完成。")


if __name__ == "__main__":
    main()
