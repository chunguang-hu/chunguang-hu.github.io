# Chunguang Hu · 个人学术网站

基于 **Hugo 静态站点** 的个人学术主页，免费托管在 **GitHub Pages**。
零服务器、零数据库、零运行时费用；自动 HTTPS、移动端适配与 SEO，无任何访问门槛。

> **已上线**：https://chunguang-hu.github.io/ （用户站点，无 sharecode、无 Cookie 门槛，可直接访问并被搜索引擎收录）

- 论文清单：**ORCID 公共 API** 自动同步（61 条记录 → 58 篇正式成果，征稿/专刊通告已自动排除）
- 引用指标：**OpenAlex 开放 API** 自动同步（去重后 50 篇、总被引 1123、h-index 20）
- 审稿期刊：**ORCID peer-review 记录** 自动聚合（63 个期刊、316 次审阅；期刊名按 ISSN 经 Crossref 解析）
- Google Scholar / ResearchGate：**不抓取**，采用可维护的人工导出 / 人工填写方案
- 自动更新：GitHub Actions 每周同步数据 → push → 自动重新构建并部署

> 数据口径、来源与更新时间均在页面上明确标注，绝不把估算值伪装成官方数据。

---

## 0. 当前状态与发布前检查

| 检查项 | 状态 |
|---|---|
| 占位 / 测试内容 | 已清除（无「待补充」「示例数据」「TODO」） |
| 本地路径 / 私有路径 | 页面产物中无 `127.0.0.1`、`C:\Users`、`file://` |
| 维护说明外泄 | `static/downloads/README.md` 已删除；`data/*.json` 只参与构建、不会输出到 `public/` |
| 隐私数据 | 页面邮箱来自 ORCID 公开记录，可发布；如不愿公开，删 `data/profile.json` 的 `email` 后重建 |
| 数据源标注 | 每处指标均标注 ORCID / OpenAlex 来源与口径 |
| canonical / OG / sitemap | 由部署工作流按 Pages 实际地址自动回写 |
| 站内链接 | 已做「子路径安全」改造（见 §1.1），项目站点下也不会 404 |
| **结论** | **已上线**：`https://chunguang-hu.github.io/`（用户站点，Source 已设为 GitHub Actions） |

**过渡期的内置发布链接**（可并存，非必需）：
`https://chunguang-hu.app.workbuddy.host/?sharecode=UJN6QBDSI3`

- 这是**定向分享**链接：必须发完整链接（含 `?sharecode=`）并用**独立浏览器标签页**打开。
  在 WorkBuddy 预览面板、微信内置浏览器等 iframe 环境中，第三方 Cookie 被拦截 → 表现为
  「能进首页、点链接就 403」。这不是网站损坏，改用独立浏览器即可。
- GitHub Pages 版本**没有 sharecode、没有 Cookie 门槛**，任何人可直接访问，也可被搜索引擎收录。
- 确认 GitHub Pages 正常后，可在平台里下线内置发布。

---

## 1. 首次发布到 GitHub Pages

### 1.1 选仓库名（决定网址）

| 方案 | 仓库名 | 网址 | 网址含姓名 |
|---|---|---|---|
| **A 用户站点**（本项目已采用） | `chunguang-hu.github.io` | `https://chunguang-hu.github.io/` | 用户名即姓名拼音 |
| **B 项目站点** | `<仓库名>`（任意） | `https://chunguang-hu.github.io/<仓库名>/` | 含姓名，但带路径 |
| **C 自定义域名**（最正式） | 任意 | `https://chunguang-hu.com/` | 完全自有的姓名域名 |

> **本项目已做「子路径安全」改造**：所有 CSS、图片、导航、下载链接都用 Hugo `relURL`
> 生成，canonical / OG / sitemap 用 `absURL` 与 `.Permalink`。因此 A / B / C 三种部署方式
> 都能正常加载，不会出现「首页能开、点链接 404」。
> 这也是上一轮「链接打不开」问题的根治点——托管平台的鉴权与子路径是两类不同原因。

### 1.2 创建仓库并推送

在 GitHub 新建**空**仓库：不要勾选 *Add a README file* / *.gitignore* / *license*（避免与本地首次提交冲突），
Visibility 建议选 **Public**（便于搜索引擎收录；私有仓库也能发布，但自定义域名等能力受限）。

本地已完成 `git init` 与首个提交，直接执行：

```bash
cd academic-site
git remote add origin https://github.com/<用户名>/<仓库名>.git
git branch -M main
git push -u origin main
```

> SSH 方式：`git remote add origin git@github.com:<用户名>/<仓库名>.git`
> 首次推送若提示登录，用 Personal Access Token 或 `gh auth login` 完成认证。

### 1.3 ⚠️ 必做：把 Pages 的 Source 改成 GitHub Actions

`Settings → Pages → Build and deployment → Source` → 选择 **GitHub Actions**。

> 这是最容易漏的一步。默认值是 *Deploy from a branch*；不选的话工作流会显示成功，
> 但站点不会真正发布，Pages 页面也不会出现访问地址。

### 1.4 触发与验证

push 后 Actions 里的「部署到 GitHub Pages」会自动运行（也可在 Actions 页手动 *Run workflow*），约 1–2 分钟完成。

验证清单：

- [ ] 首页样式、配图、导航、移动端菜单正常
- [ ] 8 个页面（首页 / 简介 / 研究方向 / 论文 / 项目 / 教学服务 / CV / 联系）均可打开
- [ ] CV PDF 与 BibTeX 可下载
- [ ] `sitemap.xml` 与页面 `<link rel="canonical">` 中的域名是 GitHub Pages 实际地址
- [ ] 无浏览器无痕窗口 / 无 sharecode 也能直接访问（说明已真正公开）

### 1.5 绑定自定义域名（可选，网址含姓名）

1. 购买域名（`.com` / `.me` / `.name`，约 ¥60–150/年）。
2. DNS 配置（以 GitHub 官方文档为准）：
   - 根域名用 **A 记录**指向 `185.199.108.153`、`185.199.109.153`、`185.199.110.153`、`185.199.111.153`；
   - 或子域名（如 `www`）用 **CNAME** 指向 `<用户名>.github.io`。
3. `Settings → Pages → Custom domain` 填入域名，DNS 生效后勾选 **Enforce HTTPS**（证书由 GitHub 自动签发，免费）。
4. `Settings → Secrets and variables → Actions → Variables → New repository variable`，
   新建 `CUSTOM_DOMAIN`，值为该域名。
5. 重新运行「部署到 GitHub Pages」工作流。它会自动写 `public/CNAME`，并用该域名作为 `baseURL`
   生成 canonical / OG / sitemap。

### 1.6 「网址能不能是我的姓名？」——结论

- 本项目的用户名 `chunguang-hu` 即姓名拼音 → **方案 A** 即 `https://chunguang-hu.github.io/`，免费且含姓名。
- 若用户名不是姓名 → **方案 B** 用姓名做仓库名，或 **方案 C** 自定义域名（最正式、最易记忆）。
- 平台内置发布链接的第一段 `chunguang-hu` 也是姓名，但属于平台子域名，且带 sharecode 门槛；
  GitHub Pages 才是无门槛、可被搜索引擎收录的公开地址。

---

## 2. 自动更新链路（免费）

```
GitHub Actions 每周一 UTC 03:17（或手动触发）
   ↓  python -m scripts.sync_all
   ↓  ORCID + OpenAlex 公开 API（无需密钥）
   ↓  合并写入 data/*.json，自动生成 CV PDF 与 BibTeX
   ↓  仅当数据有变化才 git commit & push（commit 不含 [skip ci]）
   ↓
push 触发 deploy-gh-pages.yml
   ↓  hugo --gc --minify（baseURL 由 configure-pages 自动注入）
   ↓  actions/deploy-pages 发布到 GitHub Pages
```

> `sync-data.yml` 的提交信息**不能带 `[skip ci]`**，否则 GitHub 会跳过 push 触发的工作流，
> 数据更新了但网站不会重新部署。这一处已在迁移时修正。

| 数据 | 来源 | 接口 | 频率 |
|---|---|---|---|
| 成果清单、作者、期刊、DOI、年份 | ORCID Public API v3.0 | `/works` + `/work/{put-code}` | 每次同步 |
| 姓名、任职、教育、基金、公开邮箱 | ORCID Public API | `/record` | 每次同步 |
| 总被引、h-index、i10、逐年引用、单篇被引 | OpenAlex API | `/authors?filter=orcid:` + `/works` | 每次同步 |
| 审稿期刊、审阅次数、年份跨度 | ORCID + Crossref | `/peer-reviews` → ISSN 聚合 → `/journals/{issn}` | 每次同步 |

**同名歧义处理**：实测 OpenAlex 中存在 3 个指向同一 ORCID 的重复作者档案
（`A5103083652` / `A5126642634` / `A5136674440`）。脚本按 ORCID 找出全部档案，再按 DOI 去重合并。
如自动匹配有误，可用 `OPENALEX_AUTHOR_IDS` 手动指定。

**无法直接同步的部分**：Google Scholar 无公开 API、ToS 禁止抓取且实测被 CAPTCHA 拦截；
ResearchGate 对程序化请求返回 403。因此提供三种可维护替代方案（详见 `docs/SCHOLAR-IMPORT.md`）：

1. **人工填写官方数值**：编辑 `data/scholar_manual.json`（`citations` / `h_index` / `i10_index` / `last_updated`），
   运行 `python -m scripts.import_scholar && python -m scripts.build_data`；填 `null` 则不展示。
2. **导入 Publish or Perish 导出 CSV**：放到 `data/imports/scholar.csv`，运行 `python -m scripts.import_scholar`。
3. **导入 BibTeX 补充成果**：`.bib` 放进 `data/imports/`，由脚本解析合并。

---

## 3. 本地预览与构建

```bash
cd academic-site
hugo server -D                 # http://localhost:1313
hugo --gc --minify             # 生成 public/
```

模拟项目站点子路径（验证用）：

```bash
hugo --gc --minify --baseURL "https://<用户名>.github.io/<仓库名>/"
```

> `data/*.json` 已随仓库提交，构建**不需要 Python、不需要联网**。
> Python 只用于「更新数据」，不是构建依赖，这正是该方案在免费托管上稳定的原因。
> Windows 安装 Hugo：`winget install Hugo.Hugo.Extended`；macOS：`brew install hugo`。
>
> 若仍需更新 §0 提到的**过渡期内置发布链接**，用旧域名单独构建后再发布即可（链接不变）：
> `hugo --gc --minify --baseURL "https://chunguang-hu.app.workbuddy.host/"`。

---

## 4. 目录结构

```
academic-site/
├── hugo.yaml                       # 站点配置：baseURL、导航、SEO、菜单、输出
├── .gitignore                      # 忽略 public/、resources/、缓存等
├── .github/workflows/
│   ├── deploy-gh-pages.yml         # ★ 主部署：Hugo 构建 → GitHub Pages
│   ├── sync-data.yml               # 每周同步学术数据 → push 触发重新部署
│   └── deploy-pages.yml            # 备用：Cloudflare Pages（仅手动触发）
├── wrangler.toml                   # Cloudflare Pages 备用配置
├── package.json                    # 可选：本地 wrangler 部署脚本
├── .env.example                    # 可选环境变量模板
├── scripts/                        # 自动同步脚本（仅 Python 标准库）
│   ├── sync_all.py                 # 一键编排入口
│   ├── sync_orcid.py               # ORCID 公共 API → 成果 / 个人资料
│   ├── sync_peer_reviews.py        # ORCID 审稿记录 → 期刊聚合（Crossref 解析刊名）
│   ├── sync_openalex.py            # OpenAlex → 引用指标 / 单篇被引
│   ├── import_scholar.py           # Scholar 人工导出导入（CSV / BibTeX）
│   ├── build_data.py               # 合并所有来源 → Hugo data/*.json
│   ├── generate_cv.py              # 由数据生成可下载 CV PDF（纯标准库）
│   └── lib/                        # HTTP 客户端与通用工具
├── data/                           # 只参与构建，不输出到 public/
│   ├── site.json                   # ★ 手工维护：简介、研究方向、项目、教学、链接
│   ├── overrides.json              # ★ 手工维护：精选/隐藏/中文标题/PDF/补充条目
│   ├── scholar_manual.json         # ★ 手工维护：Google Scholar 官方引用数值
│   ├── review_journals_override.json  # ★ 手工维护：审稿期刊显示名 / 隐藏
│   ├── imports/                    # ★ 可选：scholar.csv / *.bib 人工导出文件
│   └── *.json                      # 其余为自动生成（勿手改）
├── content/                        # 8 个页面（front matter 指定 layout）
├── layouts/                        # 模板：首页、各页面、SEO、学术条目（均为 relURL 安全）
├── static/
│   ├── css/main.css                # 响应式样式（含深色模式 / 打印样式）
│   ├── js/main.js                  # 移动端菜单、成果搜索与筛选、回到顶部
│   ├── images/                     # 配图：hero 主视觉、研究方向横幅、monogram、OG 封面
│   ├── favicon.svg
│   ├── _headers                    # Cloudflare Pages 专用（GitHub Pages 不读取）
│   └── downloads/
│       ├── cv.pdf                  # 自动生成的 CV（可覆盖为正式版）
│       └── publications.bib        # 自动生成的 BibTeX
├── docs/                           # 维护文档（不输出到 public/）
└── public/                         # 构建产物（已 gitignore）
```

带 ★ 的文件由你维护，**不会被自动同步覆盖**；其余 JSON 由脚本生成。

---

## 5. 数据维护速查

| 我想做的事 | 改哪里 |
|---|---|
| 改姓名、头衔、单位、邮箱、社交链接 | `data/site.json` |
| 改研究方向、项目、动态 | `data/site.json` |
| 补录课程教学 | `data/site.json` 的 `teaching` 数组；留空时页面自动隐藏该板块 |
| 修正或隐藏某个审稿期刊的显示名 | `data/review_journals_override.json` |
| 设置代表性成果 / 隐藏征稿类条目 | `data/overrides.json` 的 `featured` / `hidden` |
| 给论文加中文标题、PDF、标签、备注 | `data/overrides.json` 的 `items`（按 DOI 索引） |
| 补充 ORCID 未收录的成果 | `data/overrides.json` 的 `extra_items` |
| 填 Google Scholar 官方引用数 | `data/scholar_manual.json` |
| 批量导入 Scholar 成果与被引 | `data/imports/scholar.csv` + `python -m scripts.import_scholar` |
| 换正式 CV | 另存为 `static/downloads/cv-official.pdf`，并把 `data/site.json` 的 `cv_file` 改指向它 |
| 换头像 | 覆盖 `static/images/avatar.svg` |
| 改站点标题 / 描述 / 关键词 / 菜单 | `hugo.yaml` |
| 改线上域名 | 无需改 `hugo.yaml`；由工作流自动注入。自定义域见 §1.5 |

---

## 6. 已实现的功能

- 页面：首页、个人简介、研究方向、论文与引用、项目、教学与学术服务、CV/下载、联系方式
- 审稿期刊：ORCID peer-review 按 ISSN 聚合，首页标签云 + 学术服务页完整排行；无数据时整块自动隐藏
- 视觉：主题配图（WebP）、内联矢量图标、衬线标题 + 无衬线正文、明暗双主题
- 学术条目：按年份倒序分组、作者（本人加粗）、期刊、DOI、全文/PDF、被引徽标、类型标签、精选标记
- 交互：移动端汉堡菜单、成果关键词搜索、年份/类型筛选、回到顶部、滚动阴影
- SEO：canonical、description、Open Graph、Twitter Card、`sitemap.xml`、`robots.txt`、
  `schema.org` Person / ProfilePage JSON-LD、Google Scholar 兼容的 `citation_*` 元信息
- 响应式 / 可访问性：≤760px 单列、深色模式、跳转主内容链接、aria 标签、语义化标题
- 下载：自动生成的 CV PDF（3 页）与全量 BibTeX；打印样式可直接另存为 PDF

---

## 7. GitHub Pages 特有注意事项

| 类别 | 说明 |
|---|---|
| `_headers` | `static/_headers` 是 Cloudflare Pages 专用；GitHub Pages 不读取自定义响应头，该文件仅作为普通静态文件存在，安全头由 GitHub 统一提供 |
| 容量 / 带宽 | 建议站点 < 1 GB、软带宽 100 GB/月；个人学术站远低于此 |
| 仓库可见性 | 建议 Public；私有仓库也能发布，但自定义域名与搜索引擎收录受限 |
| 构建 | 免费、按需触发；`sync-data.yml` 每周一次，不会触顶 |
| 自定义域 HTTPS | GitHub 自动签发证书，免费；DNS 生效后勾选 Enforce HTTPS |
| CDN 缓存 | 更新后强制刷新（Ctrl+F5）确认 |
| 隐私 | 页面邮箱来自 ORCID 公开记录；不想公开可删 `data/profile.json` 的 `email` 并重建 |
| 维护注释 | `data/*.json` 不输出到 `public/`，其字段注释不会出现在网页上 |
| 数据准确性 | ORCID 记录由本人维护；征稿/专刊通告（3 条）已自动排除；OpenAlex 与 Scholar 口径不同 |
| 配图 | 插画为 AI 生成后处理的示意图，仅用于版式说明，不代表数据结果 |

---

## 8. 备用方案：Cloudflare Pages

`wrangler.toml` 与 `.github/workflows/deploy-pages.yml` 保留为备用（已改为**仅手动触发**，
避免每次 push 因缺少 `CLOUDFLARE_*` secrets 而报错）。需要时：

- **Git 集成**：Cloudflare Dashboard → Workers & Pages → Create → Pages → Connect to Git，
  Framework preset `Hugo`，Build command `hugo --gc --minify`，输出目录 `public`，
  环境变量 `HUGO_VERSION=0.170.0`。
- **wrangler 直传**：配置 Secrets `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` 后，
  在 Actions 手动运行「部署到 Cloudflare Pages（备用）」。

切换托管平台时，线上 `baseURL` 由对应平台的构建命令注入，源码无需改动。

---

## 9. 常见问题

**Q：脚本会抓取 Google Scholar 吗？**
不会。无公开 API、ToS 禁止、且实测被拦截。请用人工填写或 Publish or Perish 导出。

**Q：为什么引用数与 Google Scholar 不一致？**
OpenAlex 与 Scholar 收录范围不同，且本项目对重复作者档案按 DOI 去重。页面已分别标注来源与口径。

**Q：同步失败会不会导致网站挂掉？**
不会。脚本对单个数据源失败会保留上次成功的数据，构建只读取已提交的 `data/*.json`，不依赖网络。

**Q：为什么 push 后 Actions 成功但站点没更新？**
九成是漏了 §1.3：Pages 的 Source 没设成 **GitHub Actions**。另外确认 `sync-data.yml`
的提交信息没有 `[skip ci]`。

**Q：项目站点（带 `/仓库名/`）下 CSS 或导航会 404 吗？**
不会。模板已全部改用 `relURL`，并针对子路径修正了 `citation_*` 元信息与导航高亮的判断。
可用 §3 的子路径构建命令自行验证。

**Q：如何手动触发一次更新？**
GitHub → Actions → 「同步学术数据」或「部署到 GitHub Pages」→ Run workflow。

**Q：换 ORCID / 换人怎么用？**
`python -m scripts.sync_all --orcid 0000-0000-0000-0000`，并同步修改 `hugo.yaml`、`data/site.json` 与链接。
