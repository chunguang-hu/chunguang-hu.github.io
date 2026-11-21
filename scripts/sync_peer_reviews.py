"""从 ORCID 公开记录同步「作为审稿人审阅过的期刊」。

ORCID 的 peer-review 记录只给出期刊 ISSN（review-group-id 形如 issn:0360-1323），
不含期刊名。本脚本：

  1. GET {ORCID}/peer-reviews（磁盘缓存 7 天）
  2. 只保留 reviewer-role == "reviewer" 的记录（排除编辑等其他角色）
  3. 按 ISSN 聚合：审阅次数、年份范围、召集机构（出版社）
  4. 用 Crossref /journals/{issn} 解析期刊名与出版社（缓存 90 天）；
     Crossref 查不到时回退 OpenAlex /sources；仍失败则保留 ISSN 并标记 unresolved
  5. 叠加 data/review_journals_override.json 的人工修正与隐藏（不会被自动同步覆盖）

输出 data/_orcid_peer_reviews.json，由 build_data.py 汇总成
data/review_journals.json 供 Hugo 模板读取。

用法：
  python -m scripts.sync_peer_reviews
  python -m scripts.sync_peer_reviews --no-resolve   # 只取 ORCID，不查期刊名
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from .lib.common import DATA, ensure_dirs, now_iso, read_json, write_json
from .lib.http_client import get_json

ORCID_API = "https://pub.orcid.org/v3.0"
CROSSREF = "https://api.crossref.org/journals"
OPENALEX_SOURCES = "https://api.openalex.org/sources"
DEFAULT_ORCID = "0009-0003-6832-3957"
ACCEPT = {"Accept": "application/json"}

OVERRIDE_TEMPLATE = {
    "hidden_issns": [],
    "names": {},
    "notes": "names 用 ISSN 覆盖期刊显示名；hidden_issns 可隐藏个别期刊。修改后重跑 build_data 即可。",
}


# ---------------------------------------------------------------- 小工具
def _norm_issn(value: str) -> str:
    v = (value or "").strip()
    v = re.sub(r"(?i)^issn:\s*", "", v)
    return v.upper()


def _year_of(summary: dict) -> int | None:
    node = (summary.get("completion-date") or {})
    for key in ("year", "month", "day"):
        pass
    y = (node.get("year") or {}).get("value")
    if y and str(y).isdigit():
        return int(y)
    created = (summary.get("created-date") or {}).get("value")
    if isinstance(created, (int, float)):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(created / 1000, tz=timezone.utc).year
    return None


def _initials(name: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name or "") if w]
    if not words:
        return "—"
    if len(words) == 1:
        w = words[0]
        return (w[:1].upper() + w[1:2].lower()) if len(w) > 1 else w.upper()
    return "".join(w[0].upper() for w in words[:2])


def _public_issns(group: dict, summary: dict) -> str:
    for e in ((group.get("external-ids") or {}).get("external-id") or []):
        if (e.get("external-id-type") or "").lower() == "peer-review":
            v = _norm_issn(e.get("external-id-value") or "")
            if v:
                return v
    return _norm_issn(summary.get("review-group-id") or "")


# ---------------------------------------------------------------- ORCID 聚合
def aggregate(payload: dict) -> dict:
    """把一个 ORCID peer-reviews 响应聚合成按期刊分组的统计。"""
    buckets: dict[str, dict] = {}
    total = 0
    skipped_roles = 0

    for group in payload.get("group") or []:
        for pg in group.get("peer-review-group") or []:
            for s in pg.get("peer-review-summary") or []:
                role = (s.get("reviewer-role") or "").strip().lower()
                if role and role != "reviewer":
                    skipped_roles += 1
                    continue
                issn = _public_issns(group, s)
                key = issn or "UNKNOWN"
                b = buckets.get(key)
                if b is None:
                    b = {"issn": issn, "reviews": 0, "years": [], "orgs": {}}
                    buckets[key] = b
                b["reviews"] += 1
                total += 1
                y = _year_of(s)
                if y:
                    b["years"].append(y)
                org = ((s.get("convening-organization") or {}).get("name")
                       or ((s.get("source") or {}).get("source-name") or {}).get("value") or "")
                org = org.strip()
                if org:
                    b["orgs"][org] = b["orgs"].get(org, 0) + 1

    items = []
    for b in buckets.values():
        years = sorted(set(b["years"]))
        org = ""
        if b["orgs"]:
            org = sorted(b["orgs"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        items.append({
            "issn": b["issn"],
            "name": "",
            "publisher": org,
            "reviews": b["reviews"],
            "first_year": years[0] if years else None,
            "last_year": years[-1] if years else None,
            "years": years,
        })

    items.sort(key=lambda x: (-x["reviews"], x["issn"]))
    return {"items": items, "total_reviews": total, "skipped_roles": skipped_roles}


# ---------------------------------------------------------------- 期刊名解析
def resolve_crossref(issn: str) -> dict | None:
    email = os.environ.get("POLITE_EMAIL", "admin@example.com")
    url = f"{CROSSREF}/{issn}?mailto={email}"
    try:
        d = get_json(url, headers=ACCEPT, timeout=20, retries=2,
                     cache_ns="crossref", cache_key=f"journal-{issn}", cache_days=90)
    except RuntimeError:
        return None
    m = d.get("message") or {}
    title = re.sub(r"<[^>]+>", "", (m.get("title") or "")).strip()
    if not title:
        return None
    publisher = re.sub(r"<[^>]+>", "", (m.get("publisher") or "")).strip()
    return {
        "name": title,
        "publisher": publisher,
        "url": m.get("URL") or "",
        "resolved_by": "Crossref",
    }


def resolve_openalex(issn: str) -> dict | None:
    url = f"{OPENALEX_SOURCES}?filter=issn:{issn}&per-page=1"
    try:
        d = get_json(url, headers=ACCEPT, timeout=20, retries=1,
                     cache_ns="openalex", cache_key=f"source-{issn}", cache_days=90)
    except RuntimeError:
        return None
    results = d.get("results") or []
    if not results:
        return None
    r = results[0]
    return {
        "name": (r.get("display_name") or "").strip(),
        "publisher": (r.get("publisher") or "").strip(),
        "url": r.get("homepage_url") or "",
        "resolved_by": "OpenAlex",
    }


def resolve(issn: str) -> dict:
    if not issn or issn == "UNKNOWN":
        return {"resolved": False}
    meta = resolve_crossref(issn) or resolve_openalex(issn)
    if not meta or not meta.get("name"):
        return {"resolved": False}
    meta["resolved"] = True
    return meta


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orcid", default=os.environ.get("ORCID_ID", DEFAULT_ORCID))
    ap.add_argument("--no-resolve", action="store_true", help="不查询期刊名，仅统计 ISSN")
    args = ap.parse_args()

    ensure_dirs()
    ov_path = DATA / "review_journals_override.json"
    if not ov_path.exists():
        write_json(ov_path, OVERRIDE_TEMPLATE)
    override = read_json(ov_path, OVERRIDE_TEMPLATE) or OVERRIDE_TEMPLATE
    hidden = {_norm_issn(x) for x in (override.get("hidden_issns") or [])}
    name_map = {_norm_issn(k): v for k, v in (override.get("names") or {}).items()}

    print(f"[PeerReview] 读取 ORCID 审稿记录 {args.orcid} ...")
    try:
        payload = get_json(
            f"{ORCID_API}/{args.orcid}/peer-reviews",
            headers=ACCEPT, timeout=40, retries=3,
            cache_ns="orcid", cache_key=f"peer-reviews-{args.orcid}", cache_days=7,
        )
    except RuntimeError as exc:
        print(f"[PeerReview] 同步失败：{exc}", file=sys.stderr)
        print("[PeerReview] 保留已有数据，站点构建不受影响。", file=sys.stderr)
        return 1

    agg = aggregate(payload)
    items = agg["items"]
    print(f"  记录 {agg['total_reviews']} 条审稿（跳过非 reviewer 角色 {agg['skipped_roles']} 条），"
          f"涉及 {len(items)} 个期刊")

    if not args.no_resolve and items:
        print("[PeerReview] 解析期刊名（Crossref 优先，OpenAlex 兜底）...")
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(resolve, it["issn"]): it for it in items}
            done = 0
            for fut in as_completed(futures):
                it = futures[fut]
                meta = fut.result()
                if meta.get("resolved"):
                    it["name"] = meta.get("name") or it["issn"]
                    it["publisher"] = it.get("publisher") or meta.get("publisher") or ""
                    it["url"] = meta.get("url") or ""
                    it["resolved_by"] = meta.get("resolved_by") or ""
                done += 1
                if done % 15 == 0:
                    print(f"  ... {done}/{len(items)}")

    # 人工覆盖（最高优先级）
    for it in items:
        if it["issn"] in name_map:
            it["name"] = name_map[it["issn"]]
        if not it.get("name"):
            it["name"] = it["issn"] or "未标注期刊"
        # Crossref 对部分 MDPI 期刊把 publisher 标为 Clarivate（上游元数据问题），
        # 为避免展示错误信息，可疑出版社置空，仅保留期刊名与 ISSN。
        if "clarivate" in (it.get("publisher") or "").lower():
            it["publisher"] = ""
        it["resolved"] = bool(it.get("resolved_by"))
        it["initials"] = _initials(it["name"])

    before = len(items)
    items = [it for it in items if it["issn"] not in hidden]
    if before != len(items):
        print(f"  按 override 隐藏 {before - len(items)} 个期刊")

    years = [y for it in items for y in it.get("years") or []]
    resolved_n = sum(1 for it in items if it.get("resolved"))
    payload_out = {
        "orcid": args.orcid,
        "source": f"{ORCID_API}/{args.orcid}/peer-reviews",
        "fetched_at": now_iso(),
        "available": bool(items) and agg["total_reviews"] > 0,
        "total_reviews": agg["total_reviews"],
        "journal_count": len(items),
        "resolved_count": resolved_n,
        "year_from": min(years) if years else None,
        "year_to": max(years) if years else None,
        "items": items,
    }
    write_json(DATA / "_orcid_peer_reviews.json", payload_out)
    print(f"[PeerReview] 完成：{len(items)} 个期刊 / {agg['total_reviews']} 次审阅，"
          f"其中 {resolved_n} 个期刊名已解析")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
