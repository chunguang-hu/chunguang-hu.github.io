"""从 ORCID 公共 API v3.0 同步个人资料与成果清单。

数据源（公开、无需认证、允许程序化访问）：
  GET https://pub.orcid.org/v3.0/{ORCID}/record
  GET https://pub.orcid.org/v3.0/{ORCID}/works
  GET https://pub.orcid.org/v3.0/{ORCID}/work/{put-code}

输出（中间数据，供 build_data.py 合并）：
  data/_orcid_profile.json
  data/_orcid_works.json

用法：
  python -m scripts.sync_orcid
  python -m scripts.sync_orcid --skip-details   # 不抓逐篇详情，速度更快
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from .lib.common import DATA, ensure_dirs, now_iso, write_json
from .lib.http_client import get_json

API = "https://pub.orcid.org/v3.0"
DEFAULT_ORCID = "0009-0003-6832-3957"
ACCEPT = {"Accept": "application/json"}


# ---------------------------------------------------------------- 工具函数
def _val(node, *keys, default=""):
    cur = node
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    if isinstance(cur, dict) and "value" in cur:
        return cur.get("value") or default
    return cur or default


def _year(node, *keys):
    cur = node
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    if isinstance(cur, dict) and isinstance(cur.get("value"), str):
        try:
            return int(cur["value"])
        except ValueError:
            return None
    return None


def _date_str(node):
    if not isinstance(node, dict):
        return ""
    out = []
    for k in ("year", "month", "day"):
        v = _val(node, k)
        if v:
            out.append(str(v))
    return "-".join(out)


def _external_ids(container) -> dict[str, str]:
    result: dict[str, str] = {}
    node = (container or {}).get("external-ids") or {}
    for item in node.get("external-id", []) or []:
        t = (item.get("external-id-type") or "").lower()
        v = item.get("external-id-value")
        if t and v:
            result.setdefault(t, v)
    return result


NON_ARTICLE_PATTERNS = re.compile(
    r"call for papers|call for paper|research topic|special issue|invitation to|"
    r"call for abstracts|frontiers in .* research topics",
    re.I,
)


def classify(title: str, work_type: str, doi: str) -> str:
    """区分正式论文与 ORCID 中混入的征稿/专刊/RG 占位条目。"""
    if work_type in {"journal-issue", "conference-abstract", "newsletter-article"}:
        return "non-article"
    if doi.lower().startswith("10.13140/rg"):
        return "non-article"
    if NON_ARTICLE_PATTERNS.search(title or ""):
        return "non-article"
    return "article"


TYPE_LABELS = {
    "journal-article": "期刊论文",
    "conference-paper": "会议论文",
    "book-chapter": "专著章节",
    "book": "专著",
    "preprint": "预印本",
    "report": "研究报告",
    "dissertation": "学位论文",
    "database": "数据集",
    "software": "软件",
    "patent": "专利",
    "journal-issue": "专刊",
    "other": "其他",
}


# ---------------------------------------------------------------- 个人资料
def fetch_profile(orcid: str) -> dict:
    print(f"[ORCID] 读取公开记录 {orcid} ...")
    rec = get_json(f"{API}/{orcid}/record", headers=ACCEPT, cache_ns="orcid", cache_key=f"record-{orcid}", cache_days=3)
    person = rec.get("person") or {}
    acts = rec.get("activities-summary") or {}

    name = _val(person, "name", "given-names"), _val(person, "name", "family-name")
    full_name = " ".join(x for x in name if x).strip()

    emails = []
    for e in ((person.get("emails") or {}).get("email") or []):
        if e.get("visibility") == "public" and e.get("email"):
            emails.append(e["email"])

    links = []
    for u in ((person.get("researcher-urls") or {}).get("researcher-url", []) or []):
        if u.get("visibility") == "public":
            links.append({"label": u.get("url-name") or "Link", "url": _val(u, "url")})

    def affiliations(section: str) -> list[dict]:
        out = []
        group = (acts.get(section) or {}).get("affiliation-group") or []
        for g in group:
            for s in g.get("summaries") or []:
                body = s.get(f"{section[:-1]}-summary") or {}
                org = body.get("organization") or {}
                out.append({
                    "organization": org.get("name", ""),
                    "department": body.get("department-name"),
                    "role": body.get("role-title"),
                    "start": _date_str(body.get("start-date")),
                    "end": _date_str(body.get("end-date")),
                    "city": (org.get("address") or {}).get("city"),
                    "country": (org.get("address") or {}).get("country"),
                })
        return out

    fundings = []
    for g in (acts.get("fundings") or {}).get("group") or []:
        for s in g.get("funding-summary") or []:
            org = (s.get("organization") or {}).get("name", "")
            fundings.append({
                "title": _val(s, "title", "title"),
                "type": s.get("type"),
                "organization": org,
                "start": _date_str(s.get("start-date")),
                "end": _date_str(s.get("end-date")),
            })

    services = []
    for g in (acts.get("services") or {}).get("affiliation-group") or []:
        for s in g.get("summaries") or []:
            b = s.get("service-summary") or {}
            services.append({
                "role": b.get("role-title"),
                "organization": (b.get("organization") or {}).get("name", ""),
                "start": _date_str(b.get("start-date")),
                "end": _date_str(b.get("end-date")),
            })

    peer_reviews = (acts.get("peer-reviews") or {}).get("peer-review-group") or []

    return {
        "orcid": orcid,
        "orcid_url": f"https://orcid.org/{orcid}",
        "given_name": name[0],
        "family_name": name[1],
        "full_name": full_name or "Chunguang Hu",
        "biography": person.get("biography") or None,
        "emails": emails,
        "researcher_urls": links,
        "keywords": [k.get("content") for k in ((person.get("keywords") or {}).get("keyword") or [])],
        "employment": affiliations("employments"),
        "education": affiliations("educations"),
        "fundings": fundings,
        "services": services,
        "peer_review_count": len(peer_reviews),
        "works_count": len((acts.get("works") or {}).get("group") or []),
        "last_modified": rec.get("history", {}).get("last-modified-date", {}).get("value"),
        "source": f"{API}/{orcid}/record",
        "fetched_at": now_iso(),
    }


# ---------------------------------------------------------------- 成果清单
def fetch_works(orcid: str, with_details: bool = True) -> dict:
    print(f"[ORCID] 读取成果清单 {orcid} ...")
    payload = get_json(f"{API}/{orcid}/works", headers=ACCEPT, cache_ns="orcid", cache_key=f"works-{orcid}", cache_days=1)
    groups = payload.get("group") or []

    summaries = []
    for g in groups:
        ws = (g.get("work-summary") or [])
        if not ws:
            continue
        s = ws[0]
        ids = _external_ids(g) or _external_ids(s)
        doi = (ids.get("doi") or "").lower()
        title = _val(s, "title", "title")
        wtype = s.get("type") or "other"
        put_code = s.get("put-code")
        year = _year(s, "publication-date", "year") or _year(s, "created-date", "year")
        if not year:
            m = re.search(r"(19|20)\d{2}", title or "")
            year = int(m.group()) if m else None

        summaries.append({
            "put_code": put_code,
            "title": title,
            "subtitle": _val(s, "title", "subtitle"),
            "year": year,
            "date": _date_str(s.get("publication-date")),
            "journal": _val(s, "journal-title"),
            "type": wtype,
            "type_label": TYPE_LABELS.get(wtype, wtype),
            "doi": doi,
            "doi_url": f"https://doi.org/{doi}" if doi else "",
            "url": _val(s, "url") or (f"https://doi.org/{doi}" if doi else ""),
            "external_ids": ids,
            "short_description": s.get("short-description") or "",
            "kind": classify(title, wtype, doi),
            "authors": [],
            "abstract": "",
        })

    print(f"  共 {len(summaries)} 条记录，其中正式成果 {sum(1 for x in summaries if x['kind']=='article')} 条")

    if with_details:
        print("[ORCID] 抓取逐篇详情（作者 / 摘要 / 期刊），首次较慢，结果会缓存 ...")
        targets = [x for x in summaries if x["put_code"]]

        def one(item):
            key = f"work-{orcid}-{item['put_code']}"
            try:
                d = get_json(
                    f"{API}/{orcid}/work/{item['put_code']}",
                    headers=ACCEPT, timeout=25, retries=2,
                    cache_ns="orcid", cache_key=key, cache_days=30,
                )
            except RuntimeError as exc:
                return item["put_code"], None, str(exc)
            authors = []
            for c in ((d.get("contributors") or {}).get("contributor") or []):
                n = _val(c, "credit-name")
                if n:
                    authors.append(n)
            return item["put_code"], {
                "authors": authors,
                "abstract": d.get("short-description") or "",
                "journal": _val(d, "journal-title") or item["journal"],
            }, None

        done, failed = 0, 0
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(one, it): it for it in targets}
            for fut in as_completed(futures):
                put_code, detail, err = fut.result()
                if detail is None:
                    failed += 1
                    continue
                for it in summaries:
                    if it["put_code"] == put_code:
                        it.update(detail)
                        break
                done += 1
                if done % 20 == 0:
                    print(f"  ... {done}/{len(targets)}")
        print(f"  详情完成 {done} 条，失败 {failed} 条（失败项不影响构建）")

    summaries.sort(key=lambda x: (-(x["year"] or 0), x["title"].lower()))
    return {
        "orcid": orcid,
        "source": f"{API}/{orcid}/works",
        "fetched_at": now_iso(),
        "count": len(summaries),
        "items": summaries,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orcid", default=os.environ.get("ORCID_ID", DEFAULT_ORCID))
    ap.add_argument("--skip-details", action="store_true", help="跳过逐篇详情请求")
    args = ap.parse_args()

    ensure_dirs()
    try:
        profile = fetch_profile(args.orcid)
        works = fetch_works(args.orcid, with_details=not args.skip_details)
    except RuntimeError as exc:
        print(f"[ORCID] 同步失败：{exc}", file=sys.stderr)
        print("[ORCID] 保留已有数据，不影响站点构建。", file=sys.stderr)
        return 1

    write_json(DATA / "_orcid_profile.json", profile)
    write_json(DATA / "_orcid_works.json", works)
    print(f"[ORCID] 完成：{profile['full_name']}，{works['count']} 条记录")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
