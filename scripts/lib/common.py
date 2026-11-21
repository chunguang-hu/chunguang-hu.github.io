"""公共工具：路径、JSON 读写、原子写入、字符串规范化。

零第三方依赖，仅使用 Python 标准库，便于在 GitHub Actions /
Cloudflare Pages / 本地任意环境直接运行。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CACHE = ROOT / "scripts" / ".cache"
STATIC = ROOT / "static"
DOWNLOADS = STATIC / "downloads"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    for p in (DATA, CACHE, DOWNLOADS):
        p.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  ! 无法读取 {path.name}: {exc}，使用默认值")
        return default


def write_json(path: Path, payload) -> None:
    """原子写入，避免同步中途失败留下半截 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)
    print(f"  -> {path.relative_to(ROOT)}")


def cache_path(namespace: str, key: str) -> Path:
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    d = CACHE / namespace
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.json"


def read_cache(namespace: str, key: str, max_age_days: int | None = None):
    p = cache_path(namespace, key)
    if not p.exists():
        return None
    if max_age_days is not None:
        age = datetime.now(timezone.utc).timestamp() - p.stat().st_mtime
        if age > max_age_days * 86400:
            return None
    return read_json(p)


def write_cache(namespace: str, key: str, payload) -> None:
    p = cache_path(namespace, key)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "untitled"


def norm_doi(doi: str | None) -> str:
    if not doi:
        return ""
    d = doi.strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = re.sub(r"^doi:\s*", "", d)
    return d.strip()


def norm_title(text: str | None) -> str:
    """用于跨数据源按标题匹配（Scholar CSV ↔ ORCID）。"""
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text).lower()
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def stable_id(*parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def as_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
