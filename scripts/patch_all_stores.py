# -*- coding: utf-8 -*-
"""对 shanghai_bichi_saojie_2026.html 的 ALL_STORES 做定点修补。

用法：
  1) 编辑本文件下方 AVG / FIX 两个字典
  2) python3 scripts/patch_all_stores.py
脚本会原地重写 HTML 中的 ALL_STORES 字面量，并做一致性自检。
"""
import json
import re
import sys

HTML = "shanghai_bichi_saojie_2026.html"

# ---------------------------------------------------------------- 具体人均（元）
# key -> 整数人均。来源：大众点评店铺页「¥XX/人」，逐条核对过才写入。
# 未亲自核实的，一律不写（脚本会把 avg 重置为 null，页面渲染「人均待核实」）。
AVG = {
    # --- 已从大众点评店铺页直接读到 ---
    "both_lailai_xiaolong": 58,      # m.dianping.com/shop/1948870  ¥58/人
    "both_huxi_laolongtang": 40,     # m.dianping.com/shop/93431005 ¥40/人
    "both_renheguan": 170,           # m.dianping.com/shop/17182037 ¥170/人
    "bichi_laozhengxing": 149,       # m.dianping.com/shop/500368   ¥149/人
    "bichi_chilong_niuca": 48,       # m.dianping.com/shop/923044589 ¥48/人
    "saojie_guangmingcun": 79,       # 去哪儿 ¥79 / 携程 ¥79
    # --- 双榜门店（自查核实） ---
    "both_weihuang_guangfu": 116,    # m.dianping.com/shop/38338297  ¥116/人
    "both_miheliang": 128,           # m.dianping.com/shop/121466563 ¥128/人
    "both_hongziji_fenghuanglou": 150,  # m.dianping.com/shop/885613757 ¥150/人
    "both_chilis": 145,              # m.dianping.com/shop/131955258 ¥145/人
    "both_nongjiacai_laoda": 107,    # m.dianping.com/shop/3341992  ¥107/人（松江店）
    # --- 扫街榜门店（自查核实） ---
    "saojie_nanmen_shuanrou": 132,   # m.dianping.com/shop/43596947  ¥132/人
    "saojie_jinqiang_niuroumian": 37,    # m.dianping.com/shop/623329407 ¥37/人
    "saojie_gongyan": 579,           # m.dianping.com/shop/1098699544 ¥579/人
    "saojie_haifuduo_gongfu": 223,   # m.dianping.com/shop/1722184283 ¥223/人
    "saojie_shangshangqian": 105,    # m.dianping.com/shop/1120118405 ¥105/人（已闭店）
    "saojie_shendacheng": 37,        # m.dianping.com/shop/500689   ¥37/人
    "saojie_haiwanhui": 328,         # m.dianping.com/shop/1208048081 ¥328/人
    "saojie_guojifandian_xibingwu": 49,  # m.dianping.com/shop/569170 ¥49/人
    "saojie_sijiminfu_kaoya": 190,   # m.dianping.com/shop/1819827228 ¥190/人
    "saojie_huangyou_mianbao": 46,   # m.dianping.com/shop/1897418461 ¥46/人
    "saojie_henjiuyiqian_yangrouchuan": 100,  # m.dianping.com/shop/646163941 ¥100/人
    "saojie_huoshaoyun": 103,        # m.dianping.com/shop/1863935697 ¥103/人
    # --- 必吃榜门店（自查核实） ---
    "bichi_homes_benbangcai": 168,   # m.dianping.com/shop/504464   ¥168/人
    "bichi_lanxin": 90,              # m.dianping.com/shop/503165   ¥90/人
    "bichi_lubolang": 163,           # m.dianping.com/shop/500395   ¥163/人
    "bichi_nanxiang_mantoudian": 90, # m.dianping.com/shop/75199513 ¥90/人
    "bichi_dahuchun": 27,            # m.dianping.com/shop/32643953 ¥27/人
    "bichi_yangzhoufandian": 128,    # m.dianping.com/shop/504812   ¥128/人
    "bichi_rongxiaoguan": 207,       # 大众点评 shop/G5fkD33G5aLyFJWb 用户反馈 ¥207/人
    "bichi_chenglonghang_xiewangfu": 324,  # m.dianping.com/shop/500102 ¥324/人（暂停营业）
    "bichi_linhu_sushi": 108,        # m.dianping.com/shop/96738324 ¥108/人
    "bichi_longhua_suzhai": 33,      # m.dianping.com/shop/5339502 ¥33/人
    "bichi_yulixiang": 78,           # m.dianping.com/shop/1483756340 ¥78/人
    "bichi_zheyuan_guangzhou": 110,  # 携程（大众点评用户反馈） 徐家汇店 ¥110/人
    "bichi_alimentari_grande": 165,  # m.dianping.com/shop/1732863225 ¥165/人
    "bichi_omills": 142,             # m.dianping.com/shop/98698727 ¥142/人
    "bichi_awuluo_yueyong": 226,     # m.dianping.com/shop/113888298 ¥226/人
    "bichi_bingcheng_laoyujia": 78,  # m.dianping.com/shop/16814740 ¥78/人
    "bichi_ruilite_tai": 178,        # m.dianping.com/shop/1710213982 ¥178/人
    "saojie_diandude": 104,          # m.dianping.com/shop/108335942 ¥104/人
    "bichi_hengyuexuan": 295,        # m.dianping.com/shop/506354   ¥295/人
    "bichi_simiantai": 156,          # m.dianping.com/shop/987615586 ¥156/人
    "bichi_xiji_gangjiu": 130,       # m.dianping.com/shop/1891546343 ¥130/人
    "bichi_xianggang_chiziji": 38,   # m.dianping.com/shop/2662798 ¥38/人
    "bichi_xinyuan_sifangcai": 118,  # m.dianping.com/shop/3381850 ¥118/人
    "bichi_xuji_haixian": 290,       # m.dianping.com/shop/1764626853 ¥290/人
    "bichi_siji_nongpu": 220,        # m.dianping.com/shop/1116969084 ¥220/人
    "bichi_jinri_niushi": 130,       # m.dianping.com/shop/22465085 ¥130/人
    "bichi_yijiayiyan": 160,         # m.dianping.com/shop/637315467 ¥160/人
    "bichi_yunli_mixian": 43,        # m.dianping.com/shop/1501394718 ¥43/人
    "bichi_huiting_jingcui": 169,    # m.dianping.com/shop/98069737 ¥169/人
    "bichi_dongbei_sijijiaoziwang": 71,  # m.dianping.com/shop/501379 ¥71/人
    "bichi_gucheng_yan": 47,         # m.dianping.com/shop/1000293082 ¥47/人
    "bichi_ningguo_suzhai": 58,      # 携程（大众点评用户反馈） ¥58/人
    "bichi_yishanfang_octave": 216,  # 大众点评精选页 意膳坊 ¥216/人
    "bichi_dianweiyuan_mixian": 48,  # m.dianping.com/shop/131010788 ¥48/人
    "bichi_gongdelin": 78,           # 百度地图参考价 ¥78（大众点点 shop/500211）
}

# ---------------------------------------------------------------- 删除条目
# 经核实「上海不存在」的门店，直接从 ALL_STORES 移除。
REMOVE = {
    # 张功馆所有门店均在杭州（景芳店/石桥路店/永福店/钱潮店），上海无分店
    "saojie_zhanggongguan",
}

# ---------------------------------------------------------------- 字段修正
# key -> 要覆盖的字段。仅用于「已核实为错」的条目。
FIX = {
    # 连续 8 年上榜的是定西路店（长宁），不是广东路店
    "both_huxi_laolongtang": {
        "name": "沪西老弄堂面馆（定西路店）",
        "address": "长宁区定西路（近愚园路）",
        "coords": [31.220100, 121.418200],
        "mnemonic": "2/11号线江苏路站步行约10分钟，定西路近愚园路",
        "note": "连续8年上榜 · 坐标为近似",
        "district_hint": "长宁区",
    },
    # 官方名单写法为「人和馆·上海菜（徐汇店）」
    "both_renheguan": {
        "name": "人和馆·上海菜（徐汇店）",
        "note": "米其林一星 · 连续5年摘星 · 双榜交叉",
    },
    # 官方名单写法为「威皇广福和小海鲜（襄阳南路店）」
    "both_weihuang_guangfu": {
        "name": "威皇广福和小海鲜（襄阳南路店）",
        "address": "徐汇区襄阳南路（近复兴中路）",
        "coords": [31.213500, 121.459500],
        "mnemonic": "1/10/12号线陕西南路站步行约8分钟，襄阳南路近复兴中路",
    },
    # 灵馄实际在静安区常德路（同乐坊/江宁路一带），不是黄浦老城厢
    "bichi_linghun_huntun": {
        "address": "静安区常德路（同乐坊一带）",
        "coords": [31.233500, 121.442000],
        "mnemonic": "7号线昌平路站步行约8分钟，常德路近余姚路",
        "note": "2026 新上榜 · 榜单常客 · 坐标为近似",
    },
    # 该店现名为「方友赤龙·牛杂」
    "bichi_chilong_niuca": {
        "name": "方友赤龙·牛杂（淡水路店）",
        "address": "黄浦区淡水路（近淮海中路）",
        "cuisine": "牛杂小吃",
        "note": "2025 上榜 · 坐标为近似",
    },
}


def load_stores(html: str):
    m = re.search(r"const ALL_STORES = \[(.*?)\n\];", html, re.S)
    if not m:
        sys.exit("找不到 ALL_STORES 字面量")
    return json.loads("[" + m.group(1) + "]"), m


def dump_stores(stores) -> str:
    lines = ["const ALL_STORES = ["]
    for i, r in enumerate(stores):
        lines.append(" {")
        for k in ("key", "name"):
            lines.append(f'  "{k}": {json.dumps(r[k], ensure_ascii=False)},')
        for k in ("bichi", "saojie", "michelin"):
            lines.append(f'  "{k}": {json.dumps(r[k], ensure_ascii=False)},')
        lines.append(f'  "avg": {json.dumps(r.get("avg"), ensure_ascii=False)},')
        lines.append(f'  "coords": [{r["coords"][0]:.6f}, {r["coords"][1]:.6f}],')
        for k in ("cuisine", "address", "price", "desc", "mnemonic", "icon", "note"):
            lines.append(f'  "{k}": {json.dumps(r[k], ensure_ascii=False)},')
        lines.append(f'  "isNew": {json.dumps(r["isNew"], ensure_ascii=False)}')
        lines.append(" }" + ("," if i < len(stores) - 1 else ""))
    lines.append("];")
    return "\n".join(lines)


def main():
    html = open(HTML, encoding="utf-8").read()
    stores, _ = load_stores(html)
    by_key = {r["key"]: r for r in stores}

    unknown = set(AVG) - set(by_key)
    if unknown:
        sys.exit(f"AVG 里有不存在的 key：{unknown}")
    unknown = set(FIX) - set(by_key)
    if unknown:
        sys.exit(f"FIX 里有不存在的 key：{unknown}")
    # REMOVE 是幂等的：已删过就跳过，不再报错
    if REMOVE:
        missing = set(REMOVE) - set(by_key)
        if missing:
            print(f"（REMOVE 中 {len(missing)} 条已删除，跳过）")
        stores = [r for r in stores if r["key"] not in REMOVE]
        by_key = {r["key"]: r for r in stores}

    fixed = 0
    for k, patch in FIX.items():
        for field, val in patch.items():
            if field == "district_hint":
                continue
            by_key[k][field] = val
            fixed += 1

    priced = 0
    # 先把所有 avg 重置为 null（保证从 AVG 移除的 key 会被真正清掉），再逐条写入
    for r in stores:
        r["avg"] = None
    for k, v in AVG.items():
        by_key[k]["avg"] = v
        priced += 1

    new_block = dump_stores(stores)
    out, n = re.subn(r"const ALL_STORES = \[.*?\n\];", lambda _: new_block, html, count=1, flags=re.S)
    assert n == 1, n
    open(HTML, "w", encoding="utf-8").write(out)

    have = sum(1 for r in stores if r.get("avg"))
    print(f"共 {len(stores)} 家 | 已修正字段 {fixed} 处 | 已填人均 {priced} 家 | 人均覆盖 {have}/{len(stores)}")


if __name__ == "__main__":
    main()
