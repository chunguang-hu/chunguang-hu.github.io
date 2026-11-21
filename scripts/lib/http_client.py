"""极简 HTTP 客户端：带超时、重试、缓存与礼貌 User-Agent。

ORCID / OpenAlex 均为公开 API，无需密钥；请通过 POLITE_EMAIL
环境变量提供联系邮箱，以便进入 OpenAlex 的 polite pool。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .common import read_cache, write_cache

UA_BASE = "academic-homepage-sync/1.0 (+https://github.com/; mailto:{email})"


def _ua() -> str:
    email = os.environ.get("POLITE_EMAIL", "admin@example.com")
    return UA_BASE.format(email=email)


def get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 3,
    cache_ns: str | None = None,
    cache_key: str | None = None,
    cache_days: int | None = None,
) -> Any:
    """GET 一个 JSON 端点；失败重试；可选磁盘缓存。"""
    if cache_ns and cache_key and cache_days:
        hit = read_cache(cache_ns, cache_key, cache_days)
        if hit is not None:
            return hit

    hdr = {
        "Accept": "application/json",
        "User-Agent": _ua(),
        "Accept-Encoding": "identity",
    }
    if headers:
        hdr.update(headers)

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdr, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
            if cache_ns and cache_key:
                write_cache(cache_ns, cache_key, data)
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"请求失败（已重试 {retries} 次）: {url}\n  原因: {last_err}")


def with_query(base: str, **params) -> str:
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    # OpenAlex 的 filter 值含 '|'、':' 等字符，需保留语义，仅做最小编码
    if not clean:
        return base
    return base + "?" + urllib.parse.urlencode(clean, safe=":|/-.")


def polite_url(base: str) -> str:
    """为 OpenAlex 追加 api_key（若提供），提升每日额度。"""
    key = os.environ.get("OPENALEX_API_KEY")
    if not key:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}api_key={urllib.parse.quote(key)}"
