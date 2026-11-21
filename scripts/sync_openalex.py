"""从 OpenAlex 开放 API 同步引用指标与单篇被引数。

数据源（开放、免费、无需密钥，可选 API Key 提升额度）：
  GET /authors?filter=orcid:{ORCID}
  GET /works?filter=author.id:A|B|C&per-page=200&cursor=*
  GET /works?filter=doi:doi1|doi2|...

重要：OpenAlex 可能对同一位学者建立多个重复作者档案（本项目实测为 3 个，
均指向同一 ORCID）。本脚本按 ORCID 找出全部档案，再按 DOI 去重合并，避免
把不同档案的同一篇论文重复计入引用与 h-index。

输出（中间数据）：data/_openalex.json
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

from .lib.common import DATA, ensure_dirs, norm_doi, now_iso, write_json
from .lib.http_client import get_json, polite_url, with_query

API = "https://api.openalex.org"
SELECT_WORK = "id,doi,title,publication_year,cited_by_count,type,primary_location,authorships"


def find_author_ids(orcid: str) -> list[dict]:
    url = polite_url(with_query(f"{API}/authors", filter=f"orcid:{orcid}", **{"per-page": 50}))
    data = get_json(url, cache_ns="openalex", cache_key=f"authors-{orcid}", cache_days=7)
    out = []
    for a in data.get("results") or []:
        stats = a.get("summary_stats") or {}
        out.append({
            "id": (a.get("id") or "").rsplit("/", 1)[-1],
            "url": a.get("id"),
            "name": a.get("display_name"),
            "cited_by_count": a.get("cited_by_count") or 0,
            "works_count": a.get("works_count") or 0,
            "h_index": stats.get("h_index") or 0,
            "i10_index": stats.get("i10_index") or 0,
            "institutions": [i.get("display_name") for i in (a.get("last_known_institutions") or [])],
            "counts_by_year": a.get("counts_by_year") or [],
        })
    return out


def fetch_all_works(author_ids: list[str]) -> list[dict]:
    """按多个作者 ID 拉取全部作品并分页（cursor）。"""
    if not author_ids:
        return []
    filt = "author.id:" + "|".join(author_ids)
    cursor = "*"
    collected: dict[str, dict] = {}
    page = 0
    while cursor:
        url = polite_url(with_query(
            f"{API}/works",
            filter=filt,
            select=SELECT_WORK,
            **{"per-page": 200, "cursor": cursor},
        ))
        data = get_json(url, timeout=40)
        for w in data.get("results") or []:
            doi = norm_doi(w.get("doi"))
            key = doi or (w.get("id") or "").rsplit("/", 1)[-1]
            cited = w.get("cited_by_count") or 0
            # 同一 DOI 出现在多个作者档案时，取最大的被引数，不重复累加
            if key not in collected or cited > collected[key]["cited_by_count"]:
                collected[key] = {
                    "key": key,
                    "doi": doi,
                    "title": w.get("title") or "",
                    "year": w.get("publication_year"),
                    "cited_by_count": cited,
                    "type": w.get("type"),
                    "openalex_id": w.get("id"),
                }
        cursor = (data.get("meta") or {}).get("next_cursor")
        page += 1
        if page > 20:
            break
    return list(collected.values())


def doi_citation_lookup(dois: list[str]) -> dict[str, int]:
    """按 DOI 批量查询单篇被引数（OpenAlex filter 支持 | 作为 OR）。"""
    out: dict[str, int] = {}
    clean = [d for d in dict.fromkeys(dois) if d]
    for i in range(0, len(clean), 40):
        chunk = clean[i:i + 40]
        filt = "doi:" + "|".join(chunk)
        url = polite_url(with_query(f"{API}/works", filter=filt, select="doi,cited_by_count,title", **{"per-page": 50}))
        try:
            data = get_json(url, timeout=40, retries=2)
        except RuntimeError as exc:
            print(f"  ! DOI 批量查询跳过一段: {exc}")
            continue
        for w in data.get("results") or []:
            d = norm_doi(w.get("doi"))
            if d:
                out[d] = w.get("cited_by_count") or 0
    return out


def h_index(citations: list[int]) -> int:
    s = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(s, start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orcid", default=os.environ.get("ORCID_ID", "0009-0003-6832-3957"))
    ap.add_argument("--author-ids", default=os.environ.get("OPENALEX_AUTHOR_IDS", ""),
                    help="手动指定 OpenAlex 作者 ID（逗号分隔），覆盖自动查找，用于消除同名歧义")
    ap.add_argument("--dois", default="", help="额外要查询单篇被引的 DOI，逗号分隔")
    args = ap.parse_args()

    ensure_dirs()
    try:
        if args.author_ids.strip():
            ids = [x.strip() for x in args.author_ids.split(",") if x.strip()]
            authors = [{"id": x, "url": f"{API}/authors/{x}", "name": "", "cited_by_count": 0,
                        "works_count": 0, "h_index": 0, "i10_index": 0,
                        "institutions": [], "counts_by_year": []} for x in ids]
            print(f"[OpenAlex] 使用手动指定的作者档案: {ids}")
        else:
            print(f"[OpenAlex] 按 ORCID {args.orcid} 查找作者档案 ...")
            authors = find_author_ids(args.orcid)
            print(f"  找到 {len(authors)} 个关联档案: {[a['id'] for a in authors]}")
            if len(authors) > 1:
                print("  ! 检测到重复作者档案，将按 DOI 去重合并（不重复计引）")

        works = fetch_all_works([a["id"] for a in authors])
        citations = [w["cited_by_count"] for w in works]

        # 逐年引用：合并各档案的 counts_by_year（同一年可能来自不同档案的作品，求和）
        by_year: dict[int, dict] = defaultdict(lambda: {"year": 0, "works": 0, "citations": 0})
        for a in authors:
            for row in a.get("counts_by_year") or []:
                y = row.get("year")
                if not y:
                    continue
                by_year[y]["year"] = y
                by_year[y]["works"] += row.get("works_count") or 0
                by_year[y]["citations"] += row.get("cited_by_count") or 0

        # 单篇被引：优先用本作者作品集，再按 DOI 批量补齐
        per_doi = {w["doi"]: w["cited_by_count"] for w in works if w["doi"]}
        extra = [x.strip() for x in args.dois.split(",") if x.strip()]
        if extra:
            per_doi.update(doi_citation_lookup([norm_doi(d) for d in extra]))

        result = {
            "orcid": args.orcid,
            "source": API,
            "fetched_at": now_iso(),
            "authors": authors,
            "deduplication": "按 DOI 去重，多个重复作者档案中同一论文只计一次",
            "works_count": len(works),
            "total_citations": sum(citations),
            "h_index": h_index(citations),
            "i10_index": sum(1 for c in citations if c >= 10),
            "max_citations": max(citations) if citations else 0,
            "citations_by_year": sorted(by_year.values(), key=lambda r: r["year"]),
            "per_doi_citations": per_doi,
            "works": sorted(works, key=lambda w: (-(w.get("year") or 0), w.get("title") or "")),
        }
    except RuntimeError as exc:
        print(f"[OpenAlex] 同步失败：{exc}", file=sys.stderr)
        print("[OpenAlex] 保留已有数据，不影响站点构建。", file=sys.stderr)
        return 1

    write_json(DATA / "_openalex.json", result)
    print(f"[OpenAlex] 完成：{result['works_count']} 篇去重作品，"
          f"总被引 {result['total_citations']}，h-index {result['h_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
