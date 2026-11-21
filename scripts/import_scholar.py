"""Google Scholar / ResearchGate 的可维护替代更新方案（不抓取、不违反服务条款）。

事实与限制
----------
* Google Scholar 没有公开 API，robots.txt 与 ToS 禁止自动抓取，且有 CAPTCHA
  与 IP 封禁；ResearchGate 对程序化请求直接返回 403。因此本项目**不做**
  任何对这两个站点的自动抓取。
* 引用与 h-index 的自动部分由 ORCID（成果清单）+ OpenAlex（被引/h-index）
  提供；Scholar 数据通过下面两种「人工导出 / 人工填写」方式维护，页面会
  明确标注数据来源与更新时间，绝不把估算值伪装成官方数据。

支持的输入（放在 data/imports/ 下，均为可选）
--------------------------------------------
1) scholar.csv —— Publish or Perish 导出的 CSV（推荐）
   必需列（大小写不敏感，也兼容中文列名）：
     Title / 标题, Authors / 作者, Year / 年份, Cited by / 被引次数
   可选列：DOI, Journal / 期刊, URL, Source
   导出路径：Publish or Perish → 检索作者 → File → Export as → CSV

2) scholar.bib —— Google Scholar「引用 → 导出 BibTeX」或任意 BibTeX
   用于补充 ORCID 未收录的成果（BibTeX 本身不含被引数）。

3) data/scholar_manual.json —— 手动记录的 Scholar 总览指标
   从 Scholar 个人主页抄录「引用 / h-index / i10-index」，填好后运行本脚本，
   会在网站「论文与引用」页作为独立卡片展示，并带上 last_updated 日期。

输出：data/_scholar.json（供 build_data.py 合并）
用法：python -m scripts.import_scholar
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from .lib.common import DATA, ensure_dirs, norm_doi, norm_title, now_iso, write_json

IMPORTS = DATA / "imports"
MANUAL = DATA / "scholar_manual.json"

MANUAL_TEMPLATE = {
    "profile_url": "https://scholar.google.com/citations?user=XJVXW4YAAAAJ&hl=zh-CN",
    "citations": None,
    "h_index": None,
    "i10_index": None,
    "last_updated": None,
    "note": "从 Google Scholar 个人主页人工抄录后填写；填 null 表示暂不展示。",
}

CSV_FIELDS = {
    "title": ("title", "标题", "document title", "publication title"),
    "authors": ("authors", "author", "作者"),
    "year": ("year", "年份", "publication year"),
    "citations": ("cited by", "citations", "citedby", "被引次数", "cites", "times cited"),
    "doi": ("doi", "digital object identifier"),
    "journal": ("journal", "venue", "publication", "期刊", "source", "journal title"),
    "url": ("url", "link", "链接"),
}


def _pick(row: dict, names: tuple[str, ...], default=""):
    lowered = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for n in names:
        if n in lowered and lowered[n] not in (None, ""):
            return str(lowered[n]).strip()
    return default


def parse_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        title = _pick(row, CSV_FIELDS["title"])
        if not title:
            continue
        try:
            cites = int(re.sub(r"[^0-9]", "", _pick(row, CSV_FIELDS["citations"], "0")) or 0)
        except ValueError:
            cites = 0
        out.append({
            "title": title,
            "authors": [a.strip() for a in re.split(r";|, and | and ", _pick(row, CSV_FIELDS["authors"])) if a.strip()],
            "year": int(re.sub(r"[^0-9]", "", _pick(row, CSV_FIELDS["year"], "0")) or 0) or None,
            "citations": cites,
            "doi": norm_doi(_pick(row, CSV_FIELDS["doi"])),
            "journal": _pick(row, CSV_FIELDS["journal"]),
            "url": _pick(row, CSV_FIELDS["url"]),
        })
    return out


def parse_bibtex(text: str) -> list[dict]:
    """轻量 BibTeX 解析：只取常用字段，足够用于补充展示条目。"""
    out = []
    for block in re.findall(r"@\w+\s*\{(.*?)\n\}", text, re.S | re.I):
        fields = dict(re.findall(r"(\w+)\s*=\s*[{\"](.*?)[\"}]", block, re.S))
        title = re.sub(r"[{}]", "", fields.get("title", "")).strip()
        if not title:
            continue
        y = re.search(r"(19|20)\d{2}", fields.get("year", ""))
        out.append({
            "title": title,
            "authors": [a.strip() for a in re.split(r"\s+and\s+", fields.get("author", "")) if a.strip()],
            "year": int(y.group()) if y else None,
            "citations": None,
            "doi": norm_doi(fields.get("doi", "")),
            "journal": re.sub(r"[{}]", "", fields.get("journal", "") or fields.get("booktitle", "")).strip(),
            "url": fields.get("url", ""),
        })
    return out


def main() -> int:
    ensure_dirs()
    IMPORTS.mkdir(parents=True, exist_ok=True)

    if not MANUAL.exists():
        write_json(MANUAL, MANUAL_TEMPLATE)
        print("[Scholar] 已生成 data/scholar_manual.json 模板，请人工填写后重新运行。")

    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    items: list[dict] = []
    sources: list[str] = []

    csv_path = IMPORTS / "scholar.csv"
    if csv_path.exists():
        parsed = parse_csv(csv_path)
        items.extend(parsed)
        sources.append(f"scholar.csv ({len(parsed)} 条)")
        print(f"[Scholar] 导入 Publish or Perish CSV: {len(parsed)} 条")

    for bib in sorted(IMPORTS.glob("*.bib")):
        parsed = parse_bibtex(bib.read_text(encoding="utf-8", errors="replace"))
        items.extend(parsed)
        sources.append(f"{bib.name} ({len(parsed)} 条)")
        print(f"[Scholar] 导入 BibTeX {bib.name}: {len(parsed)} 条")

    # 按标题归一去重
    seen: dict[str, dict] = {}
    for it in items:
        key = norm_doi(it["doi"]) or norm_title(it["title"])
        if key in seen:
            old = seen[key]
            if (it.get("citations") or 0) > (old.get("citations") or 0):
                seen[key] = it
        else:
            seen[key] = it

    result = {
        "fetched_at": now_iso(),
        "method": "manual-export",
        "reason": "Google Scholar / ResearchGate 无公开 API 且禁止自动抓取，改用人工导出 + 人工填写",
        "profile_url": manual.get("profile_url"),
        "metrics": {
            "citations": manual.get("citations"),
            "h_index": manual.get("h_index"),
            "i10_index": manual.get("i10_index"),
            "last_updated": manual.get("last_updated"),
        },
        "sources": sources,
        "items": list(seen.values()),
    }
    write_json(DATA / "_scholar.json", result)
    print(f"[Scholar] 完成：导入条目 {len(result['items'])} 条；"
          f"手动指标 citations={result['metrics']['citations']}, h={result['metrics']['h_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
