"""从已同步的学术数据自动生成可下载的 CV PDF（纯标准库，零第三方依赖）。

说明：PDF 使用内置的 Helvetica 字体（无需嵌入字体文件），因此内容以
ASCII 英文为主，中文会自动转写为拼音/省略以保证 PDF 合法可读。

本脚本每次同步都会重新生成 `static/downloads/cv.pdf`，使其随学术数据更新。
若你有排版更精美的正式 CV，请**不要**覆盖 cv.pdf：把文件另存为
`static/downloads/cv-official.pdf`，并把 `data/site.json` 的 `cv_file`
改为 `/downloads/cv-official.pdf`。这两个位置都不会被同步脚本覆盖。

用法：
  python -m scripts.generate_cv
  python -m scripts.generate_cv --force   # 同义，保留参数以兼容旧调用
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from .lib.common import DOWNLOADS, read_json, DATA, now_iso

OUT = DOWNLOADS / "cv.pdf"


def ascii_only(text: str) -> str:
    """把非拉丁字符替换为空格，避免 PDF 内置字体无法编码。"""
    out = []
    for ch in str(text or ""):
        if 32 <= ord(ch) < 127:
            out.append(ch)
        elif ch in "–—−":
            out.append("-")
        elif ch in "‘’“”":
            out.append("'")
        elif ch == "·":
            out.append("/")
        else:
            out.append(" ")
    return re.sub(r" {2,}", " ", "".join(out)).strip()


def esc(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def wrap(text: str, width: int = 96) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [""]


class Pdf:
    """极简 PDF 1.4 生成器（单列文本，多页，Helvetica/Helvetica-Bold）。"""

    W, H = 595, 842          # A4 points
    LEFT, TOP, BOTTOM = 54, 790, 54

    def __init__(self):
        self.pages: list[list[tuple]] = []
        self.cur: list[tuple] = []
        self.y = self.TOP
        self.new_page()

    def new_page(self):
        if self.cur:
            self.pages.append(self.cur)
        self.cur = []
        self.y = self.TOP

    def _space(self, needed: int):
        if self.y - needed < self.BOTTOM:
            self.new_page()

    def line(self, text: str, *, size: float = 10, bold: bool = False,
             gap: int = 4, color: tuple[float, float, float] = (0.12, 0.16, 0.2)):
        leading = size + gap
        self._space(leading)
        self.cur.append(("text", self.y, self.LEFT, size, bold, ascii_only(text), color))
        self.y -= leading

    def heading(self, text: str):
        self._space(30)
        self.y -= 8
        self.cur.append(("rule", self.y, self.LEFT, self.W - self.LEFT, (0.72, 0.78, 0.84)))
        self.y -= 12
        self.line(text, size=12, bold=True, gap=6, color=(0.09, 0.37, 0.65))
        self.y -= 3

    def para(self, text: str, *, size: float = 9.5, indent: int = 0):
        for ln in wrap(text, width=int((self.W - self.LEFT * 2 - indent) / (size * 0.5))):
            self._space(size + 4)
            self.cur.append(("text", self.y, self.LEFT + indent, size, False, ln, (0.24, 0.29, 0.35)))
            self.y -= size + 4

    def spacer(self, h: int = 8):
        self.y -= h

    def _page_stream(self, ops: list[tuple]) -> str:
        parts = []
        for op in ops:
            if op[0] == "rule":
                _, y, x, w, c = op
                parts.append(f"{c[0]:.2f} {c[1]:.2f} {c[2]:.2f} RG 0.6 w {x} {y} m {w} {y} l S")
            else:
                _, y, x, size, bold, text, c = op
                font = "F2" if bold else "F1"
                parts.append(
                    f"BT /{font} {size} Tf 1 0 0 1 {x} {y} Tm "
                    f"{c[0]:.2f} {c[1]:.2f} {c[2]:.2f} rg ({esc(text)}) Tj ET"
                )
        return "\n".join(parts)

    def build(self) -> bytes:
        self.pages.append(self.cur)
        self.cur = []
        objects: list[bytes] = []

        def add(obj: bytes) -> int:
            objects.append(obj)
            return len(objects)

        # 1 Catalog, 2 Pages, 3 Font F1, 4 Font F2
        catalog_id = add(b"<< /Type /Catalog /Pages 2 0 R >>")
        pages_id = add(b"")  # 占位，稍后填 Kids
        font1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        font2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

        page_ids = []
        for ops in self.pages:
            stream = self._page_stream(ops).encode("latin-1", "replace")
            content_id = add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
            page_id = add(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.W} {self.H}] "
                f"/Resources << /Font << /F1 {font1} 0 R /F2 {font2} 0 R >> >> "
                f"/Contents {content_id} 0 R >>".encode()
            )
            page_ids.append(page_id)

        kids = " ".join(f"{i} 0 R" for i in page_ids)
        objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for i, obj in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objects) + 1}\n".encode()
        out += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            out += f"{off:010d} 00000 n \n".encode()
        out += (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
        return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="保留参数以兼容旧调用；默认每次都重新生成")
    args = ap.parse_args()

    p = read_json(DATA / "profile.json", {}) or {}
    pubs = read_json(DATA / "publications.json", {"items": []}) or {}
    timeline = read_json(DATA / "timeline.json", {}) or {}
    metrics = read_json(DATA / "metrics.json", {}) or {}
    site = read_json(DATA / "site.json", {}) or {}

    pdf = Pdf()
    pdf.line(ascii_only(p.get("full_name") or "Chunguang Hu"), size=20, bold=True, gap=8)
    pdf.line(ascii_only(p.get("tagline") or site.get("tagline") or ""), size=11, gap=6, color=(0.09, 0.37, 0.65))
    pdf.line(f"{ascii_only(p.get('affiliation') or '')}  |  {ascii_only(p.get('location') or '')}", size=10)
    pdf.line(f"Email: {ascii_only(p.get('email') or '')}   ORCID: {ascii_only(p.get('orcid') or '')}", size=9.5)
    for l in p.get("links", [])[:4]:
        pdf.line(f"{ascii_only(l.get('label'))}: {ascii_only(l.get('url'))}", size=8.5, color=(0.35, 0.42, 0.5))
    pdf.spacer(6)

    pdf.heading("RESEARCH INTERESTS")
    pdf.para(ascii_only(p.get("headline") or site.get("headline") or ""), size=9.5)

    pdf.heading("EDUCATION")
    for e in timeline.get("education", []):
        bits = [ascii_only(e.get("organization")), ascii_only(e.get("role")), ascii_only(e.get("department"))]
        pdf.para(" - " + " / ".join(b for b in bits if b))

    pdf.heading("APPOINTMENTS")
    for e in timeline.get("employment", []):
        pdf.para(" - " + " / ".join(b for b in [ascii_only(e.get("organization")), ascii_only(e.get("role"))] if b))

    if timeline.get("fundings"):
        pdf.heading("GRANTS & PROJECTS")
        for f in timeline["fundings"]:
            pdf.para(f" - {ascii_only(f.get('title'))} ({ascii_only(f.get('organization'))}, {f.get('start','')}-{f.get('end','')})")

    if timeline.get("services"):
        pdf.heading("ACADEMIC SERVICE")
        for s in timeline["services"]:
            pdf.para(f" - {ascii_only(s.get('role'))}, {ascii_only(s.get('organization'))} ({s.get('start','')}-{s.get('end') or 'present'})")
        pdf.para(f" - Peer review records: {timeline.get('peer_review_count', 0)} (ORCID public record)")

    oa = metrics.get("openalex") or {}
    if oa.get("available"):
        pdf.heading("BIBLIOMETRICS (OpenAlex, auto-synced)")
        pdf.para(f"Total citations: {oa.get('total_citations')}   h-index: {oa.get('h_index')}   "
                 f"i10-index: {oa.get('i10_index')}   Works: {oa.get('works_count')}")
        pdf.para("Source: OpenAlex API, matched by ORCID, duplicate author profiles deduplicated by DOI. "
                 "Google Scholar metrics are maintained manually on the website.")

    articles = [i for i in pubs.get("items", []) if i.get("kind") == "article"]
    pdf.heading(f"PUBLICATIONS ({len(articles)} journal/conference items; most recent 25 shown)")
    for i, a in enumerate(articles[:25], start=1):
        authors = ", ".join(ascii_only(x) for x in (a.get("authors") or [])[:6])
        if len(a.get("authors") or []) > 6:
            authors += ", et al."
        head = f"[{i}] {authors}. {ascii_only(a.get('title'))}."
        pdf.para(head, size=9)
        tail = " ".join(x for x in [ascii_only(a.get("journal")), str(a.get("year") or ""),
                                    f"doi:{a.get('doi')}" if a.get("doi") else ""] if x)
        if tail:
            pdf.para("     " + tail, size=8.5, indent=10)

    pdf.spacer(10)
    pdf.line(f"Auto-generated from ORCID / OpenAlex public data on {now_iso()}. "
             f"Full list: https://chunguang-hu.pages.dev/publications/", size=8, color=(0.45, 0.5, 0.56))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = pdf.build()
    OUT.write_bytes(data)
    print(f"[CV] 生成 {OUT.relative_to(OUT.parents[2])} ({len(data)} bytes, {len(pdf.pages)} 页)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
