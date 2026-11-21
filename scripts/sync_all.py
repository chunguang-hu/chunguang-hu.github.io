"""一键同步：ORCID + OpenAlex（自动） → Scholar 导入（人工） → 合并构建。

本地使用：
    python -m scripts.sync_all                 # 完整同步
    python -m scripts.sync_all --skip-details # 跳过逐篇作者详情（更快）
    python -m scripts.sync_all --build-only   # 只用已有缓存重新合并，不联网

定时任务（GitHub Actions）默认执行本脚本，随后若 data/ 有变化会提交，
进而触发 Cloudflare Pages 的 Git 集成自动构建与部署。

单个数据源失败不会中断流程：会保留上一次成功的数据继续构建站点。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("sync_orcid", "sync_peer_reviews", "sync_openalex", "import_scholar", "build_data")


def run(module: str, args: list[str]) -> int:
    print(f"\n{'=' * 60}\n>>> python -m scripts.{module} {' '.join(args)}\n{'=' * 60}")
    return subprocess.call([sys.executable, "-m", f"scripts.{module}", *args], cwd=ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-details", action="store_true")
    ap.add_argument("--build-only", action="store_true", help="不联网，仅用现有数据重新合并")
    ap.add_argument("--orcid", default="")
    ap.add_argument("--author-ids", default="")
    args = ap.parse_args()

    if args.build_only:
        run("build_data", [])
        run("generate_cv", [])
        return 0

    orcid_args = ["--orcid", args.orcid] if args.orcid else []
    if args.skip_details:
        orcid_args.append("--skip-details")

    oa_args = []
    if args.orcid:
        oa_args += ["--orcid", args.orcid]
    if args.author_ids:
        oa_args += ["--author-ids", args.author_ids]

    results = {
        "sync_orcid": run("sync_orcid", orcid_args),
        "sync_openalex": run("sync_openalex", oa_args),
        "import_scholar": run("import_scholar", []),
    }
    for name, code in results.items():
        print(f"  {name}: {'OK' if code == 0 else 'FAILED (保留旧数据)'}")

    code = run("build_data", [])
    if code != 0:
        print("[sync_all] 合并失败", file=sys.stderr)
        return 1
    run("generate_cv", [])
    print("\n[sync_all] 全部完成。若使用 Git 集成，提交 data/ 即会自动发布。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
