# -*- coding: utf-8 -*-
"""读取大众点评移动端店铺页，抽取「人均 / 营业时间 / 品类 / 地址片段」。

用法：
    python3 scripts/dianping_probe.py 512257664 512257664 ...
    python3 scripts/dianping_probe.py --json 512257664

输出为制表符分隔，便于汇总。未能取到的字段输出 "-"。
仅用于人工核对的辅助读取，不写入数据；入库前需人工确认店铺与地址匹配。
"""
import json
import re
import sys
import time
import urllib.request

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


class Blocked(RuntimeError):
    """被美团风控拦截（spiderindefence / 验证中心），而非店铺不存在。"""


def fetch(shop_id: str, timeout: int = 25) -> str:
    url = f"https://m.dianping.com/shop/{shop_id}"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://m.dianping.com/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        # 被风控时会 302 到 verify.meituan.com，urlopen 默认跟随，
        # 于是拿到的是「验证中心」页而不是店铺页 —— 必须显式识别，
        # 否则各字段会静默取成 "-"，看起来像店铺数据缺失。
        final = resp.geturl()
        html = resp.read().decode("utf-8", errors="ignore")
    if "verify.meituan.com" in final or "spiderindefence" in final \
            or "验证中心" in html[:3000]:
        raise Blocked(
            "被美团风控拦截（spiderindefence）。请降低请求频率、稍后重试，"
            "或改用浏览器会话读取。注意：curl/urllib 高频访问后本机 IP "
            "通常会被临时封禁，连浏览器一并受影响。"
        )
    return html


def first(pattern: str, text: str, default="-"):
    m = re.search(pattern, text)
    if not m:
        return default
    val = m.group(1)
    return val.replace("\\n", " / ").strip()


def probe(shop_id: str) -> dict:
    try:
        html = fetch(shop_id)
    except Exception as exc:  # noqa: BLE001
        return {"id": shop_id, "error": f"{type(exc).__name__}: {exc}"}

    title = first(r"<title>【(.{0,80}?)】", html)
    return {
        "id": shop_id,
        "title": title,
        "avg": first(r'"avgPrice":(\d+)', html),
        "hours": first(r'"value":"([^"]{0,120})","name":"营业时间"', html),
        "category": first(r'"categoryName":"([^"]{1,24})"', html),
        "region": first(r'"regionName":"([^"]{1,30})"', html),
        "addr_masked": first(r'"address":"([^"]{1,80})"', html),
        "status": first(r'"bizStatus":"([^"]{1,16})"', html),
        "score": first(r'"score":([\d.]+)', html),
    }


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    out = []
    for i, sid in enumerate(args):
        out.append(probe(sid))
        if i < len(args) - 1:
            time.sleep(1.2)  # 控制请求频率
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    for r in out:
        if "error" in r:
            print(f"{r['id']}\tERROR\t{r['error']}")
            continue
        print("\t".join([
            r["id"], r["title"], r["avg"], r["category"], r["region"],
            r["hours"], r["status"], r["score"], r["addr_masked"],
        ]))


if __name__ == "__main__":
    main()
