"""把 ORCID / OpenAlex / Scholar 的中间数据合并为 Hugo 直接可用的 data/*.json。

优先级与合并规则
----------------
成果清单  : ORCID（权威、自动） → Scholar 导入补充（无 DOI 的按标题匹配）
单篇被引  : OpenAlex 自动值 → Scholar CSV 值（若提供，覆盖并标注来源）
引用总览  : OpenAlex 自动计算（去重后）；Scholar 手动值单独并列展示
人工覆盖  : data/overrides.json 拥有最高优先级，可隐藏/置顶/补中文标题/PDF
             /追加自定义条目/修正作者，且不会被自动同步覆盖

输出：
  data/publications.json   首页与论文页的条目
  data/metrics.json        引用指标（OpenAlex 自动 + Scholar 手动并列）
  data/profile.json        个人资料
  data/timeline.json       学术时间线（任职/教育/基金/服务）
  static/downloads/publications.bib   可下载 BibTeX
"""
from __future__ import annotations

import json
from pathlib import Path

from .lib.common import (
    DATA, DOWNLOADS, ensure_dirs, norm_doi, norm_title, now_iso,
    read_json, stable_id, write_json,
)

OVERRIDES_TEMPLATE = {
    "hidden": [],
    "featured": [],
    "items": {},
    "extra_items": [],
    "notes": "按 DOI（小写）或标题作为 key。可用字段: title_zh, authors, featured, hidden, pdf_url, note, tags, year, journal",
}
SITE_TEMPLATE = {
    "name": "Chunguang Hu",
    "tagline": "城市热环境与可持续城市研究",
    "headline": "城市热环境 · 城市形态 · 蓝绿基础设施 · 生态韧性",
    "affiliation": "Peking University",
    "affiliation_zh": "北京大学",
    "location": "Beijing, China",
    "email": "chunguangh@foxmail.com",
    "email_alt": "huchunguang@stu.pku.edu.cn",
    "avatar": "/images/avatar.svg",
    "cv_file": "/downloads/cv.pdf",
    "cv_note": "把正式 CV 另存为 static/downloads/cv-official.pdf，并把此处 cv_file 指向它；cv.pdf 由脚本自动生成",
    "links": [
        {"label": "ORCID", "url": "https://orcid.org/0009-0003-6832-3957", "icon": "orcid"},
        {"label": "Google Scholar", "url": "https://scholar.google.com/citations?user=XJVXW4YAAAAJ&hl=zh-CN", "icon": "scholar"},
        {"label": "ResearchGate", "url": "https://www.researchgate.net/profile/Chunguang-Hu-2", "icon": "rg"},
        {"label": "OpenAlex", "url": "https://openalex.org/authors/A5103083652", "icon": "openalex"},
    ],
    "research": [
        {
            "title": "城市热环境与热舒适",
            "title_en": "Urban Thermal Environment & Thermal Comfort",
            "description": "基于遥感与多源城市数据，刻画城市热岛、热暴露风险网络与居民热舒适的时空分异，识别热/冷核心的演化模式与驱动机制。",
            "keywords": ["城市热岛", "热暴露风险", "地表温度", "局地气候区"],
        },
        {
            "title": "2D/3D 城市形态与气候响应",
            "title_en": "2D/3D Urban Morphology & Climate Response",
            "description": "量化建筑高度、建筑足迹、城市形态异质性对地表温度与热环境的影响，揭示跨城乡梯度与城市功能区的空间非平稳性。",
            "keywords": ["城市形态", "建筑足迹", "空间异质性", "机器学习"],
        },
        {
            "title": "蓝绿基础设施与城市降温",
            "title_en": "Blue–Green Infrastructure & Urban Cooling",
            "description": "评估城市绿地、水体与蓝绿空间的降温效应及其非线性阈值，构建参数化量化框架，服务于气候适应型规划。",
            "keywords": ["蓝绿基础设施", "降温效应", "非线性阈值", "自然解决方案"],
        },
        {
            "title": "土地利用变化与生态韧性",
            "title_en": "Land Use Change & Ecological Resilience",
            "description": "研究土地利用/覆被变化、国土空间碳中和路径、生态韧性与城乡梯度上的生态公平问题。",
            "keywords": ["土地利用", "生态韧性", "碳中和", "环境公平"],
        },
        {
            "title": "遥感与地理空间人工智能",
            "title_en": "Remote Sensing & GeoAI",
            "description": "融合多时相遥感、高时空分辨率 NDVI 与可解释机器学习/深度学习方法，开展城市环境监测与预测建模。",
            "keywords": ["遥感", "可解释 AI", "时空融合", "目标检测"],
        },
        {
            "title": "城市大气污染与暴露",
            "title_en": "Urban Air Pollution & Exposure",
            "description": "分析 PM2.5 与气溶胶污染的空间分异、地理屏障效应以及城市绿地的调节作用。",
            "keywords": ["PM2.5", "大气污染", "暴露评估", "绿地调节"],
        },
    ],
    "projects": [
        {
            "title": "基于网络模型的流域聚落热暴露风险识别与精准缓解",
            "title_en": "Identification and Targeted Mitigation of Heat Exposure Risk in Watershed Settlements Based on Network Models",
            "role": "主持 / 承担",
            "funding": "中国矿业大学（Contract）",
            "period": "2025.11 – 2026.12",
            "status": "在研",
            "description": "以网络模型识别流域聚落的热暴露风险格局并提出靶向缓解策略。数据来源：ORCID 公开记录。",
            "tags": ["热暴露风险", "网络分析", "气候适应"],
        },
    ],
    # 留空则「课程教学」板块自动隐藏；补录真实课程后会自动显示，无需改模板
    "teaching": [],
    "service": "auto",
    "news": [
        {"date": "2026", "text": "担任 Discover Cities、Asian Journal of Water, Environment and Pollution 等期刊客座编辑。"},
    ],
}


def _ensure_manual_files():
    if not (DATA / "site.json").exists():
        write_json(DATA / "site.json", SITE_TEMPLATE)
    if not (DATA / "overrides.json").exists():
        write_json(DATA / "overrides.json", OVERRIDES_TEMPLATE)


def _bibtex_key(item: dict) -> str:
    first = (item.get("authors") or ["Anonymous"])[0].split()[-1] if item.get("authors") else "Anonymous"
    return f"{norm_title(first).replace(' ', '')}{item.get('year') or 'nd'}{stable_id(item.get('title', ''))[:5]}"


def write_bibtex(items: list[dict]) -> None:
    lines = []
    for it in items:
        if it.get("kind") != "article":
            continue
        key = _bibtex_key(it)
        lines.append(f"@article{{{key},")
        lines.append(f"  title   = {{{{{it.get('title', '')}}}}},")
        if it.get("authors"):
            lines.append("  author  = {" + " and ".join(it["authors"]) + "},")
        if it.get("journal"):
            lines.append(f"  journal = {{{{{it['journal']}}}}},")
        if it.get("year"):
            lines.append(f"  year    = {{{{{it['year']}}}}},")
        if it.get("doi"):
            lines.append(f"  doi     = {{{{{it['doi']}}}}},")
        if it.get("url"):
            lines.append(f"  url     = {{{{{it['url']}}}}},")
        lines.append("}")
        lines.append("")
    (DOWNLOADS / "publications.bib").write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> {(DOWNLOADS / 'publications.bib').relative_to(DATA.parent)}")


def main() -> int:
    ensure_dirs()
    _ensure_manual_files()

    orcid_works = read_json(DATA / "_orcid_works.json", {"items": [], "orcid": ""})
    orcid_profile = read_json(DATA / "_orcid_profile.json", {})
    openalex = read_json(DATA / "_openalex.json", {})
    scholar = read_json(DATA / "_scholar.json", {"items": [], "metrics": {}})
    site = read_json(DATA / "site.json", SITE_TEMPLATE)
    ov = read_json(DATA / "overrides.json", OVERRIDES_TEMPLATE)

    hidden = set(norm_doi(x) or norm_title(x) for x in (ov.get("hidden") or []))
    featured = set(norm_doi(x) or norm_title(x) for x in (ov.get("featured") or []))
    per_doi = openalex.get("per_doi_citations") or {}

    # Scholar 导入：按 DOI，其次按标题归一匹配
    sch_by_doi = {i["doi"]: i for i in scholar.get("items", []) if i.get("doi")}
    sch_by_title = {norm_title(i["title"]): i for i in scholar.get("items", []) if i.get("title")}

    items: list[dict] = []
    for raw in orcid_works.get("items", []):
        doi = norm_doi(raw.get("doi"))
        title = raw.get("title") or ""
        key = doi or norm_title(title)
        sch = sch_by_doi.get(doi) or sch_by_title.get(norm_title(title))

        cites = per_doi.get(doi)
        cite_src = "OpenAlex" if cites is not None else None
        if sch and sch.get("citations") is not None:
            cites = sch["citations"]
            cite_src = "Google Scholar (导出)"

        item = {
            "id": stable_id(doi or title, str(raw.get("put_code") or "")),
            "doi": doi,
            "title": title,
            "title_zh": "",
            "authors": raw.get("authors") or [],
            "year": raw.get("year"),
            "journal": raw.get("journal") or "",
            "type": raw.get("type"),
            "type_label": raw.get("type_label") or "其他",
            "kind": raw.get("kind") or "article",
            "url": raw.get("url") or "",
            "doi_url": raw.get("doi_url") or "",
            "pdf_url": "",
            "citations": cites,
            "citations_source": cite_src,
            "featured": key in featured,
            "hidden": key in hidden or (ov.get("items", {}).get(doi or title, {}).get("hidden", False)),
            "note": "",
            "tags": [],
            "source": "ORCID",
        }
        # 人工覆盖（含按标题或 DOI 索引）
        patch = ov.get("items", {}).get(doi) or ov.get("items", {}).get(title) or {}
        for k in ("title_zh", "authors", "pdf_url", "note", "tags", "year", "journal", "kind", "featured", "hidden"):
            if k in patch:
                item[k] = patch[k]
        if item["featured"] or key in featured:
            item["featured"] = True
        items.append(item)

    for extra in ov.get("extra_items") or []:
        e = dict(extra)
        e.setdefault("id", stable_id(norm_doi(e.get("doi", "")) or e.get("title", "")))
        e.setdefault("kind", "article")
        e.setdefault("type_label", "其他")
        e.setdefault("authors", [])
        e.setdefault("source", "手动添加")
        e.setdefault("hidden", False)
        e.setdefault("featured", False)
        items.append(e)

    items.sort(key=lambda x: (-(x.get("year") or 0), x.get("title", "").lower()))
    # 只展示正式成果：ORCID 中混入的征稿/专刊通告（kind=non-article）默认不展示。
    # 如需展示某条，可在 overrides.items 里把它的 kind 覆盖为 "article"。
    visible = [i for i in items if not i.get("hidden") and i.get("kind") == "article"]

    # 预分组：避免在 Hugo 模板里对混合类型做排序，渲染更可靠
    by_year: dict[str, list[dict]] = {}
    for it in visible:
        y = str(it.get("year") or "未标注")
        by_year.setdefault(y, []).append(it)
    year_keys = sorted((k for k in by_year if k != "未标注"), key=int, reverse=True)
    if "未标注" in by_year:
        year_keys.append("未标注")
    groups = [{"year": k, "label": k if k != "未标注" else "年份未标注", "items": by_year[k]} for k in year_keys]
    types = sorted({i.get("type_label") for i in visible if i.get("type_label")})

    pub_payload = {
        "generated_at": now_iso(),
        "orcid": orcid_works.get("orcid") or site.get("links", [{}])[0].get("url", ""),
        "total": len(visible),
        "articles": sum(1 for i in visible if i.get("kind") == "article"),
        "sources": ["ORCID 公共 API", "OpenAlex API", "Google Scholar 人工导出 / 人工填写"],
        "years": year_keys,
        "types": types,
        "groups": groups,
        "items": visible,
    }
    write_json(DATA / "publications.json", pub_payload)

    metrics = {
        "generated_at": now_iso(),
        "openalex": {
            "available": bool(openalex),
            "works_count": openalex.get("works_count"),
            "total_citations": openalex.get("total_citations"),
            "h_index": openalex.get("h_index"),
            "i10_index": openalex.get("i10_index"),
            "max_citations": openalex.get("max_citations"),
            "citations_by_year": openalex.get("citations_by_year", []),
            "author_count": len(openalex.get("authors", [])),
            "deduplication": openalex.get("deduplication", ""),
            "source": "OpenAlex API（按 ORCID 自动同步，重复档案已按 DOI 去重）",
        },
        "scholar": {
            "available": any(v is not None for v in (scholar.get("metrics") or {}).values()),
            **(scholar.get("metrics") or {}),
            "profile_url": scholar.get("profile_url"),
            "source": "Google Scholar 个人主页人工抄录（无公开 API，禁止自动抓取）",
        },
        "orcid": {
            "works_count": orcid_works.get("count"),
            "source": "ORCID 公共 API",
        },
    }
    write_json(DATA / "metrics.json", metrics)

    profile = dict(orcid_profile)
    site_fields = ("name", "name_zh", "tagline", "headline", "affiliation", "affiliation_zh",
                   "location", "email", "email_alt", "avatar", "cv_file", "cv_note", "links")
    profile.update({k: site[k] for k in site_fields if k in site})
    profile["full_name"] = site.get("name") or profile.get("full_name") or "Chunguang Hu"
    profile.setdefault("emails", [])
    if site.get("email") and site["email"] not in profile["emails"]:
        profile["emails"].insert(0, site["email"])
    profile["teaching"] = site.get("teaching") or []
    write_json(DATA / "profile.json", profile)

    # 审稿期刊：ORCID peer-review 记录 → 按 ISSN 聚合 → Crossref/OpenAlex 解析期刊名
    reviews_raw = read_json(DATA / "_orcid_peer_reviews.json", {}) or {}
    review_items = reviews_raw.get("items") or []
    max_reviews = max((i.get("reviews") or 0 for i in review_items), default=0)
    for it in review_items:
        it["share"] = round((it.get("reviews") or 0) * 100 / max_reviews) if max_reviews else 0
    review_payload = {
        "generated_at": now_iso(),
        "available": bool(reviews_raw.get("available")) and bool(review_items),
        "total_reviews": reviews_raw.get("total_reviews", 0),
        "journal_count": reviews_raw.get("journal_count", len(review_items)),
        "resolved_count": reviews_raw.get("resolved_count", 0),
        "year_from": reviews_raw.get("year_from"),
        "year_to": reviews_raw.get("year_to"),
        "max_reviews": max_reviews,
        "items": review_items,
        "source": "ORCID 公共 API（peer-review 记录）+ Crossref / OpenAlex 期刊名解析",
        "override_file": "data/review_journals_override.json",
    }
    write_json(DATA / "review_journals.json", review_payload)

    timeline = {
        "employment": orcid_profile.get("employment", []),
        "education": orcid_profile.get("education", []),
        "fundings": orcid_profile.get("fundings", []),
        "services": orcid_profile.get("services", []),
        "peer_review_count": review_payload["total_reviews"] or orcid_profile.get("peer_review_count", 0),
        "review_journal_count": review_payload["journal_count"],
    }
    write_json(DATA / "timeline.json", timeline)

    write_bibtex(visible)
    print(f"[build_data] 完成：{pub_payload['total']} 条展示成果"
          f"（正式论文 {pub_payload['articles']} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
