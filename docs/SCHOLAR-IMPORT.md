# 把人工导出的文件放在这里（可选）

本目录用于 Google Scholar / ResearchGate 的**可维护替代更新方案**。
这两个平台无公开 API 且禁止自动抓取，因此本站不抓取，改用人工导出。

## 1. scholar.csv（推荐，Publish or Perish 导出）

导出路径：Publish or Perish → 检索作者 → `File` → `Export as` → `CSV`
另存为 `data/imports/scholar.csv`。

识别列名（大小写不敏感，兼容中文）：

| 必需列 | 可接受的列名 |
|---|---|
| 标题 | `Title`、`标题`、`Document Title` |
| 作者 | `Authors`、`Author`、`作者` |
| 年份 | `Year`、`年份`、`Publication Year` |
| 被引次数 | `Cited by`、`Citations`、`被引次数`、`Times Cited` |
| DOI | `DOI`（可选） |
| 期刊 | `Journal`、`Venue`、`Source`、`期刊`（可选） |
| 链接 | `URL`、`Link`（可选） |

示例（可直接另存为 CSV 试用）：

```csv
Title,Authors,Year,Cited by,DOI,Journal
"Cooling varies with green space characteristics","Chunguang Hu; et al.",2026,26,10.1016/J.EIAR.2026.108401,Environmental Impact Assessment Review
```

## 2. *.bib（BibTeX）

把 Google Scholar「引用 → 导出 BibTeX」或任意 `.bib` 文件放在本目录，
`import_scholar.py` 会解析 `title / author / year / journal / doi / url` 作为补充条目。
BibTeX 不含被引次数，因此只补条目不覆盖引用数。

## 3. 运行

```bash
python -m scripts.import_scholar     # 解析本目录
python -m scripts.sync_all --build-only   # 重新合并并刷新页面数据 / CV / BibTeX
```

## 4. 只想填总引用数？

编辑 `../scholar_manual.json`，填入 `citations / h_index / i10_index / last_updated`，
页面会出现独立的 Google Scholar 指标卡并标注更新日期。

> 所有人工导入的数据都会在页面上标注来源，与 ORCID / OpenAlex 的自动数据分开显示。
