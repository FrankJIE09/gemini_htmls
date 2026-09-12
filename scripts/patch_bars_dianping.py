# -*- coding: utf-8 -*-
"""把大众点评核实到的人均 / 营业时间 / 营业状态补进 shanghai_bars_livehouse_2026.html。

数据来源与核实日期见每条 NOTE 结尾；停业结论另经独立来源交叉核实
（SmartShanghai / That's Shanghai / 好奇心日报 / 36氪 等）。

用法：
    python3 scripts/patch_bars_dianping.py           # 写回 HTML
    python3 scripts/patch_bars_dianping.py --dry     # 只打印差异，不改文件
"""
import re
import sys

HTML = "shanghai_bars_livehouse_2026.html"
DP = "https://m.dianping.com/shop/"
SRC_DATE = "2026-09-12"

# ---------------------------------------------------------------- 人均 / 打烊 / 营业日 / 状态
# avg=None 表示未取得具体人均（不是 0）。close 为「最晚打烊时间」。
UPDATES = {
    "beer_aunt": dict(avg=98, close="02:00", open_days="周一–周日 11:00–02:00"),
    "daga":      dict(avg=None, close=None, open_days="已停业", status="closed"),
    "kaiba":     dict(avg=None, close=None, open_days="已停业", status="closed"),
    "ponyup":    dict(avg=187, close="02:00", open_days="周一–周四、周日 13:00–01:00；周五–周六 13:00–02:00"),
    "coa":       dict(avg=202, close="02:30", open_days="周二–周四、周日 18:30–01:30；周五–周六 18:30–02:30"),
    "speaklow":  dict(avg=203, close="02:30", open_days="周一–周四、周日 18:00–01:30；周五–周六 18:00–02:30"),
    "sober":     dict(avg=363, close="02:00", open_days="周一–周日 12:00–02:00"),
    "utc":       dict(avg=173, close="02:00", open_days="周一–周日 18:00–02:00"),
    "mining":    dict(avg=155, close="02:00", open_days="周一–周日 20:00–02:00"),
    "laizhou":   dict(avg=177, close="01:30", open_days="周一–周四、周日 11:00–24:00；周五–周六 11:00–01:30"),
    "jz":        dict(avg=173, close="01:30",
                      open_days="周一 20:00–00:30；周二–周四 19:00–24:00；周五–周六 18:30–01:30；周日 18:30–00:30"),
    "jalc":      dict(avg=209, close="02:00", open_days="周一–周二 14:00–24:00；周三–周日 14:00–02:00"),
    "heyday":    dict(avg=223, close="02:00", open_days="周二–周日 19:30–02:00"),
    "yyt_park":  dict(avg=None, close=None, open_days="已暂停营业（2026-09-01 起）"),
    "specters":  dict(avg=88, close="04:00", open_days="周一–周四、周日 20:00–02:00；周五–周六 20:00–04:00"),
    "ark":       dict(close="01:00", open_days="周一–周四、周日 18:00–24:00；周五–周六 18:00–01:00"),
    "pearl":     dict(avg=232, close="01:00",
                      open_days="周三–周四 18:00–23:00；周五–周六 18:00–01:00；周日 17:00–20:00"),
    "chihong":   dict(avg=134, close="02:00", open_days="周一–周日 20:00–02:00"),
    "exit":      dict(avg=169, close="04:00", open_days="周五–周六 22:00–04:00；周日 22:00–02:00"),
    "potent":    dict(avg=159, close="05:00", open_days="周五–周六 22:00–05:00",
                      addr="淮海中路523号 TX淮海年轻力中心3楼（近成都南路）"),
    "cultureclub": dict(avg=156, close="05:00", open_days="周三–周日 22:00–05:00"),
    "kezee":     dict(avg=330, close="04:00", open_days="周一–周日 20:00–04:00"),
    "barrouge":  dict(avg=None, close=None, open_days="已停业", status="closed"),
    "poproof":   dict(avg=398, close="22:00",
                      open_days="周一–周五 11:30–14:00、17:00–22:00；周六–周日 11:30–14:30、17:00–22:00"),
    "m2":        dict(avg=None, close=None, open_days="已停业", status="closed"),
}

# ---------------------------------------------------------------- 备注（整条替换）
NOTE = {
    "beer_aunt": "“24 小时便利店式”自助选酒，瓶装种类多。人均 ¥98、11:00–02:00 据大众点评店铺页（2026-09-12 核实）；坐标为街道近似点。",
    "daga": "⛔ 已停业（约 2019–2020 年）。点评标「永久关门」，并获 SmartShanghai、That’s Shanghai、Untappd 三处独立印证；原址复兴西路 100 号后由「毛辣果 Maolago」接手。本页保留供对照，勿按此安排行程。",
    "kaiba": "⛔ 已停业（2018-04）。好奇心日报 2018-04-27 与 36氪 报道百威英博关停开巴全部 8 家门店，That’s Shanghai 亦标 closed；原「城市惠／品牌100」页面为旧数据。本页保留供对照，勿按此安排行程。",
    "ponyup": "Asia’s 50 Best Bars 2026 主榜 #19，上海唯一入主榜且为 New Entry；美式 diner 风格，饭点与深夜均热闹。点评人均 ¥187；周一–周四、周日 13:00–01:00，周五–周六 13:00–02:00。",
    "coa": "Asia’s 50 Best Bars 2026 扩展榜（51–100）#95；四层概念（Taqueria / Cantina / Salón / Mezcaleria），龙舌兰与梅斯卡尔近 300 款。点评人均 ¥202。⚠️ 主榜 #24 的「Coa」为 Coa 香港，与上海店不是同一家。",
    "speaklow": "藏在酒具店暗门后的日式 speakeasy，四层各自成概念。点评人均 ¥203；周一–周四、周日 18:00–01:30，周五–周六 18:00–02:30。周末排队久，建议预约。⚠️ 仅有 C 级来源及参考源，本页待核实。",
    "sober": "SG Group（Speak Low 同门）旗下，两层四概念：1F 咖啡+鸡尾酒、2F 主吧 Tipsy。点评人均 ¥363、12:00–02:00，其地址片段「雁荡路10******」与 109 号吻合，可佐证 109 号一说；⚠️ 本页仍并列保留「99 号」两说。",
    "utc": "2014 年开业的美式社区酒吧，酒单每季更换。点评人均 ¥173、18:00–02:00，其地址片段「衡山路30******」与衡山路 306 号吻合，可佐证该店已由汾阳路旧址迁出。",
    "mining": "威士忌品鉴 + 现场音乐的小型空间。点评人均 ¥155、周一–周日 20:00–02:00（富民路 83 号）；现场演出排期待核实，坐标为街道近似点。",
    "laizhou": "崃州蒸馏厂首家品牌体验餐酒吧，主打中国威士忌与城市限定特调。点评人均 ¥177；周一–周四、周日 11:00–24:00，周五–周六 11:00–01:30。",
    "jz": "2005 年创立、JZ Festival 发起方；常年爵士/蓝调/放克/世界音乐现场与 Jam Session。点评人均 ¥173；周一 20:00–00:30、周二–周四 19:00–24:00、周五–周六 18:30–01:30、周日 18:30–00:30。坐标为高德 POI 精确点。",
    "jalc": "常设座位制、需预约，常规场 19:30 开演，周五/六加开 21:30 场。点评人均 ¥209；周一–周二 14:00–24:00、周三–周日 14:00–02:00。",
    "heyday": "小体量复古爵士吧，桌椅围绕中央树形舞台。点评人均 ¥223、周二–周日 19:30–02:00。门票：周一/二免票、周三/四/日 ¥50、周五/六 ¥80（聚合/参考源，待核实）；吧台无低消、卡座有低消。",
    "yyt_park": "⛔ 官方公告自 2026-09-01 起暂停营业，场地整体转让合作中；本页保留供对照，请勿按此安排行程。大众点评仍显示「营业中」（周三–周日 18:00–23:00、人均 ¥104），属未同步，故本页人均与打烊时间一并清零，以店方公告为准。",
    "specters": "育音堂系摇滚/朋克据点，黑红色 dive bar 气质，新址两层、比愚园路旧址更大。点评人均 ¥88；周一–周四、周日 20:00–02:00，周五–周六 20:00–04:00。容量待核实。",
    "ark": "2021 年开业，集合餐饮 / 咖啡 / 酒吧与沉浸式音乐剧、驻场演出；以坐席为主。⚠️ 点评标「已关门」与 2026 上半年演出事实不符；驻演《Little Jack 小杰克》2026-06-28 收官后未查到新排期，是否续办待核实。",
    "pearl": "1931 年石库门建筑改建，现场乐队 + 音乐剧 + 复古主题之夜，通常有着装要求。点评人均 ¥232；周三–周四 18:00–23:00、周五–周六 18:00–01:00、周日 17:00–20:00。",
    "chihong": "金桥 EKA·天物园区内的演出场地，偏摇滚/金属现场。点评人均 ¥134、周一–周日 20:00–02:00；容量与排期待核实。",
    "exit": "电子/地下音乐俱乐部，以音响与先锋阵容著称。点评人均 ¥169；周五–周六 22:00–04:00、周日 22:00–02:00。⚠️ 据 SmartShanghai 2026-09 报道，该址 2026 年 8 月大部分时间关闭、拟更名「Doop」重开；截至 2026-09-12 票务仍以「Exit Club」售票，更名是否已生效待核实。",
    "potent": "淮海路商圈地下电音俱乐部，常邀国内外 DJ 驻场。地址经 SmartShanghai 与大众点评双向核实为「淮海中路 523 号 TX 淮海年轻力中心 3 楼」；点评人均 ¥159、周五–周六 22:00–05:00。",
    "cultureclub": "INS 多楼层夜生活综合体内的舞厅，流行舞曲为主、LGBTQ 友好。点评人均 ¥156、周三–周日 22:00–05:00。",
    "kezee": "面积超 4500㎡、层高 13 m 的剧院式夜店，含主舞台/舞池/两层包厢。点评店名作「KZ Shanghai」，人均 ¥330、周一–周日 20:00–04:00；散台低消约 ¥500（平日）–¥1000（周末，编辑估算），人数容量未公开。",
    "barrouge": "⛔ 已停业（2022-07-29 告别派对，2022-12-01 正式闭店）。外滩 18 号 7 楼现为 KEV，SmartShanghai 2026-09 夜店指南仍以「Bar Rouge 旧址的 KEV」描述。本页保留供对照。",
    "poproof": "外滩三号顶层露台，正对陆家嘴江景。点评店名作「POP 露台西餐厅·望江阁」，人均 ¥398、11:30–14:00 与 17:00–22:00（周末午市至 14:30）；以餐酒社交为主，驻场 DJ 与夜场时间待核实。",
    "m2": "⛔ 已停业。点评标「已关门」，并经 SmartShanghai 独立印证：淮海中路 283 号香港广场 4F 的 M2 约 2017 年底由 MYST 接替；淮海中路 1 号 6 楼的 M2 于 2019 秋改名 Wann，Wann 亦已停业。本页保留供对照。",
    "mao": "2000 年代起的老牌 Livehouse，层高 5.3 m、几乎覆盖所有风格；容量因大/小厅而异，公开资料 520–1000 人不等。⚠️ 点评店铺页标「已关门」为误标：2026-09 至 10 月仍有大量已开票演出（2026-09-19、09-26、10-24、10-31 等），本页按正常营业收录。",
    "tap19": "以 19 个酒头生啤为特色，偏资深酒友；大众点评未检索到该店店铺页，人均与营业时间仍来自聚合站（待核实），坐标近似。",
    "muchbeer": "精酿老店，酒单每周轮换；大众点评未检索到独立店铺页，门牌地址与人均均未查到权威来源，且打烊较早，夜猫子请早。",
    "phase": "2023 年开业的独立音乐现场，三层空间（1F 吧台站立区 / 2F 阶梯坐席 / 3F 观演区）。⚠️ 点评仅存在无法读取的演出场馆条目，店名与地址未获直证，本页待核实。",
    "parkhere": "百年马厩改造、沿街全开窗；以精酿为基酒做创意特调，酒单按季度更新。大众点评未检索到店铺页，人均待核实。",
    "neotopia": "“日咖夜酒”，白咖啡夜调酒，街边梧桐位；特调约 18 度、以花香系为主。大众点评未检索到店铺页，人均待核实。",
}

# ---------------------------------------------------------------- 追加来源
# key -> (等级, [url…])；等级为 C 时表示平台/媒体一手页
SRC_ADD = {
    "beer_aunt": ("C", [DP + "94013890"]),
    "daga": ("C", ["https://www.smartshanghai.com/venue/12843/daga_brewpub_fuxing_lu",
                   "https://www.thatsmags.com/shanghai/directory/18697/daga-brewpub-fu-xing-xi-lu"]),
    "kaiba": ("C", ["https://www.thatsmags.com/shanghai/directory/5723/kaibawu-ding-lu",
                    "https://www.qdaily.org/articles/52475/"]),
    "ponyup": ("C", [DP + "512257664"]),
    "coa": ("C", [DP + "1530753991"]),
    "speaklow": ("C", [DP + "18515105"]),
    "sober": ("C", [DP + "894450358"]),
    "utc": ("C", [DP + "GaC7fyEEg0CDu3Je"]),
    "mining": ("C", [DP + "1108460006"]),
    "laizhou": ("C", [DP + "1483564296"]),
    "jz": ("C", [DP + "505502"]),
    "jalc": ("C", [DP + "979182076"]),
    "heyday": ("C", [DP + "21971463"]),
    "yyt_park": ("C", [DP + "107761768"]),
    "specters": ("C", [DP + "98707007"]),
    "ark": ("C", [DP + "675808130"]),
    "pearl": ("C", [DP + "k5bV22gAMQVTanYz"]),
    "chihong": ("C", [DP + "1420330646"]),
    "exit": ("C", [DP + "1950460472"]),
    "potent": ("C", [DP + "HaQCIVGYAJr94QBz"]),
    "cultureclub": ("C", [DP + "1684361613"]),
    "kezee": ("C", [DP + "1506191974"]),
    "barrouge": ("C", ["https://www.smartshanghai.com/venue/473/Bar_Rouge_shanghai",
                       "https://www.smartshanghai.com/venue/29701/kev"]),
    "poproof": ("C", [DP + "22200756"]),
    "m2": ("C", ["https://www.smartshanghai.com/venue/15038/myst_huaihai_zhong_lu",
                 DP + "59933113"]),
    "mao": ("C", ["https://www.showstart.com/venue/58068742"]),
    "starz": ("C", [DP + "79285864"]),
}


def find_block(body: str, key: str):
    pat = re.compile(r"\{key:'" + re.escape(key) + r"'.*?updated:'[0-9-]+'\}", re.S)
    m = pat.search(body)
    if not m:
        raise SystemExit(f"找不到 venue: {key}")
    return m.start(), m.end()


def set_scalar(block: str, field: str, value) -> str:
    """替换标量字段（字符串用单引号，None 写 null，数字直接写）。"""
    if value is None:
        lit = "null"
    elif isinstance(value, int):
        lit = str(value)
    else:
        lit = "'" + value + "'"
    new, n = re.subn(r"\b" + field + r":(?:null|\d+|'[^']*')", field + ":" + lit, block, count=1)
    if n != 1:
        raise SystemExit(f"字段 {field} 替换失败（匹配 {n} 次）")
    return new


def append_src(block: str, tier: str, urls) -> str:
    m = re.search(r"src_tier:\[([^\]]*)\]", block)
    tiers = re.findall(r"'([^']+)'", m.group(1))
    for t in tier.split("/"):
        if t not in tiers:
            tiers.append(t)
    block = block[:m.start()] + "src_tier:[" + ",".join("'" + t + "'" for t in tiers) + "]" + block[m.end():]

    m = re.search(r"src_url:\[([^\]]*)\]", block)
    cur = re.findall(r"'([^']+)'", m.group(1))
    for u in urls:
        if u not in cur:
            cur.append(u)
    return block[:m.start()] + "src_url:[" + ",".join("'" + u + "'" for u in cur) + "]" + block[m.end():]


def main() -> None:
    dry = "--dry" in sys.argv
    src = open(HTML, encoding="utf-8").read()
    i = src.index("const VENUES = [")
    j = src.index("/* ================= 派生分类")
    body, changed = src[i:j], 0

    for key, upd in UPDATES.items():
        s, e = find_block(body, key)
        block = body[s:e]
        before = block
        for field, value in upd.items():
            block = set_scalar(block, field, value)
        if key in NOTE:
            block, n = re.subn(r"note:'.*?'(?=,\s*uneasy:)", "note:'" + NOTE[key] + "'", block, count=1, flags=re.S)
            if n != 1:
                raise SystemExit(f"{key} 的 note 替换失败")
        if key in SRC_ADD:
            tier, urls = SRC_ADD[key]
            block = append_src(block, tier, urls)
        if "'" in block.replace("'", "", 0) and block.count("'") % 2:
            raise SystemExit(f"{key} 单引号不成对，请检查备注文本")
        if block != before:
            changed += 1
        body = body[:s] + block + body[e:]

    print(f"已更新 {changed} 家")
    if dry:
        print("（--dry 模式，未写回文件）")
        return
    open(HTML, "w", encoding="utf-8").write(src[:i] + body + src[j:])
    print("已写回", HTML)


if __name__ == "__main__":
    main()
