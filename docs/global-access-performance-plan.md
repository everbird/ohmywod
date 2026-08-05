---
document_id: ohmywod-global-access-performance-plan
schema_version: 1
document_status: draft
source_of_truth_for: "domestic and international access performance risks, improvement order, and non-regression guardrails"
language: zh-CN
created_at: "2026-08-04"
last_updated: "2026-08-05"
review_commit: "uncommitted"
review_worktree: "Wave 0..2 (GAP-001..007) applied; GAP-004 CF rule live; GAP-007 FA subset deferred; uncommitted"
next_item_id: "GAP-008"
---

# 国内与海外访问性能改进计划

> 本文基于 2026-08-04 对生产响应、Globalping 中国探针和 `ohmywod` repo 的扫描结果。它补充 [CDN 改进计划](cdn-improvement-plan.md)，重点是把会拖慢国内加载的跨境/第三方资源找出来，同时明确不为了国内网络而显著牺牲海外用户体验。

## 1. 目标与边界

目标：

- 减少首屏和阅读页对国内不稳定域名的依赖。
- 降低所有用户的冷启动下载体积，尤其是首屏图片、字体和重复 CSS。
- 只缓存公开、响应一致、低变更频率的内容，避免登录态或 metadata 串内容。
- 改动应同时改善国内与海外，或至少对海外保持中性。

非目标：

- 不在当前阶段引入大陆 CDN、Cloudflare China Network、ICP 备案或多地域源站。
- 不做基于用户地理位置的双模板/双资源分流，除非有明确数据证明简单全局优化不够。
- 不缓存登录、上传、搜索、点赞、收藏、个人目录和可变 metadata 页面。
- 不为了少数国内链路绕路而把海外用户强制切到国内供应商或更慢镜像。

## 2. 当前证据

### 2.1 生产网络基线

- `wod.everbird.me` 已走 Cloudflare 橙云，响应有 `server: cloudflare`、`cf-ray`、HTTP/3 `alt-svc`。
- 中国公共 DNS 解析仍是普通 Cloudflare Anycast 地址，例如 `104.21.50.50`、`172.67.157.29`、`188.114.96.3`，不是中国大陆专用链路。
- 2026-08-04 Globalping 中国探针：
  - 首页 `/`：广州腾讯云约 `1061ms`，`CF-RAY ...-AMS`。
  - `static/img/logo.png`：北京腾讯云约 `907ms`，`956467 bytes`，`CF-Cache-Status: REVALIDATED`，`CF-RAY ...-AMS`。
  - 公开 raw 战报 HEAD：北京腾讯云约 `1044ms`，`Cache-Control: private, no-cache`，`CF-Cache-Status: DYNAMIC`，`CF-RAY ...-AMS`。
  - `delta.world-of-dungeons.org/wod/javascript/wod_standard.js`：深圳阿里云约 `1610ms`，其中 DNS 约 `866ms`，源 IP `136.243.45.117`。
- 从美国侧访问本站边缘 TTFB 约 `0.16-0.18s`，说明应用并非普遍慢；国内慢主要来自 Cloudflare 全球网络路径、动态回源、第三方域名和冷下载体积。

### 2.2 Repo 扫描发现

| 风险 | 位置 | 影响 | 海外影响 |
|---|---|---|---|
| Google Fonts `@import` | `ohmywod/static/css/bootstrap.min.css` | `fonts.googleapis.com` 在国内常慢；CSS `@import` 位于渲染关键路径 | 移除或本地化通常也减少海外 DNS/TLS |
| Google tag | `ohmywod/templates/base.html` | `googletagmanager.com` 国内可能长时间 pending | `async`，海外影响较小；延迟加载会轻微延后统计但不伤页面 |
| unpkg FilePond CSS | `templates/root.html`、`templates/category.html` | 国内 `unpkg.com` 不稳定；`category.html` 同时加载本地 `filepond.css`，重复 | 去掉重复外链可减少海外请求 |
| reader 依赖 WoD 德国站 | `templates/report_reader.html`、`templates/layout.html` | `delta.world-of-dungeons.org` CSS/JS 从德国 Apache 返回，国内 DNS/TLS 慢 | 本地镜像可减少海外第三方连接；需验证功能等价 |
| 大 logo | `static/img/logo.png` | 1024x1024 PNG，`956467 bytes`，每个普通页面侧边栏加载 | 减重直接改善所有地区冷加载 |
| raw 战报不共享缓存 | `views/report.py::_report_raw_response` | 公开 raw 每次动态回源东京/JuiceFS，国内重复访问慢 | 边缘 HIT 同样减少海外回源 |
| base 页面动态且发 session cookie | `templates/base.html` + Flask session/CSRF | 首页/列表/详情 `Vary: Cookie`，不适合整页共享缓存 | 保持动态避免串用户状态；不强行 Cache Everything |
| 通用 JS/CSS 偏重 | `base.html`、`category.html` | 每页加载 jQuery、Bootstrap、Font Awesome、Popper；上传页加载 FilePond 437KB | 减少重复/按页加载可改善所有地区，但风险高于资源本地化 |

## 3. 决策原则

1. 优先做“全局减少请求、减少字节、去掉重复外链”的改动。
2. 国内优化不得引入海外慢镜像；如果要替换第三方源，优先本地静态资源，由本站 Cloudflare 统一分发。
3. 不用地理位置判断决定核心资源 URL；这会增加缓存碎片、测试矩阵和误判风险。
4. 动态 HTML 保持不共享缓存；公开 raw 战报可以单独加 Cloudflare 专用缓存头。
5. 第三方统计、捐赠、外站跳转只能作为增强能力，不能阻塞首屏可读内容。
6. 每个上线项至少比较国内探针和美国/欧洲侧响应，确认没有明显海外回归。

## 4. 建议推进顺序

```text
Wave 0: 去掉阻塞/重复第三方资源 + logo 减重
  GAP-001 Google Fonts
  GAP-002 unpkg FilePond CSS
  GAP-003 logo

Wave 1: 公开内容边缘缓存 + reader 第三方资源本地化
  GAP-004 raw 战报 Cloudflare 缓存
  GAP-005 reader WoD CSS/JS 本地镜像

Wave 2: 低风险加载策略与资源瘦身
  GAP-006 Google tag 延迟/开关
  GAP-007 通用 JS/CSS 按页加载与 Font Awesome 瘦身
```

Wave 0 和 Wave 1 完成后先复测，不自动进入大陆 CDN 或多地域源站。

## 5. 工作项

### GAP-001 — 移除 Google Fonts 渲染关键路径依赖

- 状态：`done`
- 优先级：`P0`
- 依赖：无

问题与影响：`bootstrap.min.css` 开头有 `@import url(https://fonts.googleapis.com/css2?family=Lato:...)`。这个请求在国内常卡住；因为它由 CSS 触发，容易影响样式/字体渲染。海外用户也要额外 DNS/TLS 到 Google Fonts。

方向：

- 首选：移除 `@import`，把 Bootstrap 的 `--bs-font-sans-serif` 从 `Lato,...` 改为系统字体栈。
- 备选：若必须保留 Lato 视觉，下载 self-hosted `woff2` 并使用 `font-display: swap`；但这会增加静态文件和维护成本，当前不优先。

完成判断：

- 全仓无 `fonts.googleapis.com` / `fonts.gstatic.com`。
- 首页和常见页面视觉无明显问题。
- 国内探针不再出现 Google Fonts 请求；海外首屏请求数减少。

### GAP-002 — 删除 unpkg FilePond CSS 外链

- 状态：`done`
- 优先级：`P0`
- 依赖：无

问题与影响：`root.html` 和 `category.html` 引用 `https://unpkg.com/filepond@^4/dist/filepond.css`；`category.html` 同时加载本地 `static/css/filepond.css`，形成重复 CSS。`unpkg.com` 对国内不稳定，对海外也多一次连接。

方向：

- `category.html` 删除 unpkg CSS，只保留本地 `filepond.css`。
- `root.html` 没有上传控件，确认页面不需要 FilePond CSS 后直接删除外链。

完成判断：

- 全仓模板无 `unpkg.com`。
- 分类页上传控件显示和交互正常。
- 全部目录页视觉不回归。

### GAP-003 — 缩小普通页面 logo 下载字节

- 状态：`done`
- 优先级：`P1`
- 依赖：无

问题与影响：`static/img/logo.png` 为 `956467 bytes`，页面显示最大约 256px。国内探针下载该图约 `907ms`，即使 Cloudflare 缓存也被字节数和远端边缘拖累。

方向：

- 生成 512px 或 256px 展示版 PNG/WebP，优先使用新文件名，例如 `logo-512.png`。
- `base.html` 普通页面侧边栏使用轻量版本。
- OG 图片是否继续用原图由实际预览质量决定；不为 OG 牺牲每页首屏。

完成判断：

- 普通页面实际加载 logo 小于 `250KB`，目标小于 `120KB`。
- 桌面、移动和高 DPI 无明显模糊。
- 部署后新 URL Cloudflare 命中正常，不依赖 purge 同名旧缓存。

### GAP-004 — 为公开 raw 战报增加 Cloudflare 边缘缓存

- 状态：`done`（应用层 + 生产 Cache Rule 均完成，已实测 `HIT`；国内/海外探针对比为建议后续项）
- 优先级：`P1`
- 依赖：Cloudflare Cache Rule 修改授权、生产发布授权

生产配置实况（重要坑）：`Cache-Control: private, no-cache` 会让 Cloudflare 在 Edge TTL「respect origin」（"Use cache-control header if present..."）模式下直接 `BYPASS`，即使 origin 同时发了 `Cloudflare-CDN-Cache-Control: public, max-age=86400`（该头会被 CF 消费后从返回给客户端的响应里删除，`curl` 看不到，无法据此判断 origin 是否发了）。最终解决办法是不依赖 header 覆盖：把这条 Cache Rule 的 **Edge TTL 改为 "Ignore cache-control header and use this TTL" = 1 day**，**Browser TTL 保持 respect origin**。这样边缘强制缓存 24h、浏览器仍拿 `private, no-cache` 继续 revalidate。app 里的 `Cloudflare-CDN-Cache-Control` 头在此模式下闲置但保留（自文档 + 备用）。实测同一 raw URL 第二次请求 `cf-cache-status: HIT`（带 `age`），浏览器头不变。

问题与影响：`/r/raw/*` 是公开且基本不可变的战报 HTML，但当前响应为 `Cache-Control: private, no-cache` 和 `CF-Cache-Status: DYNAMIC`。国内访问需要动态回源东京，热门战报重复访问无法利用边缘。

方向沿用 [CDN-001](cdn-improvement-plan.md#cdn-001--为公开且基本不可变的-raw-战报增加-cloudflare-边缘缓存)：

- 浏览器继续 `Cache-Control: private, no-cache`。
- 增加 `Cloudflare-CDN-Cache-Control: public, max-age=86400`。
- Cloudflare Cache Rule 只匹配 `wod.everbird.me` 的 `/r/raw/*`。
- 不缓存 `/r/report/*`、reader、列表、搜索、登录或互动接口。

完成判断：

- 单元测试覆盖 200/304 的 CSP、ETag、浏览器缓存头和 Cloudflare 专用缓存头。
- 真实 raw 连续请求出现 `HIT`；动态页面仍为 `DYNAMIC` / `BYPASS`。
- 国内和海外探针重复访问都有改善，且无用户态串内容。

### GAP-005 — reader 页 WoD 德国站 CSS/JS 本地镜像

- 状态：`done`（代码完成并测试；建议部署后做浏览器功能回归：tooltip/皮肤/跳转）
- 优先级：`P1`
- 依赖：功能兼容验证

问题与影响：`report_reader.html` 依赖：

- `https://delta.world-of-dungeons.org/wod/javascript/wod_standard.js?1662631467`
- `https://delta.world-of-dungeons.org/wod/css/layout.css?1662631467`
- `https://delta.world-of-dungeons.org/wod/css//skins/skin-4/skin-cn.css?1662631467`

中国探针测 `wod_standard.js` 总耗时约 `1610ms`，DNS 约 `866ms`。这些资源也让海外用户多连接一个德国源站。

方向：

- 把当前固定版本的 JS/CSS 保存到本站 `static/wod/` 下，模板改成本地 URL。
- 保留外站跳转链接本身，不代理真实 WoD 游戏页面。
- 给镜像文件记录来源 URL、抓取日期和版本 query，避免未来不知为何存在。
- 若本地镜像导致 tooltip、跳转、皮肤显示不兼容，回滚该项，不做运行时双源 fallback；双源 fallback 可能在慢网下反而拖更久。

完成判断：

- reader 页无 `delta.world-of-dungeons.org` 的静态 CSS/JS 请求。
- tooltip、技能/物品链接、浮窗、移动端阅读控件正常。
- 国内探针 reader 首屏减少至少一个慢 DNS/TLS 链路；海外请求数不增加。

### GAP-006 — Google tag 改为非阻塞增强能力

- 状态：`done`（配置开关 + 延迟加载；已测试。建议部署后确认 GA 仍能收到数据）
- 优先级：`P2`
- 依赖：是否仍需要 Google Analytics 数据

实现方式：GA4 measurement id 抽成模块级常量 `config.py::GOOGLE_ANALYTICS_ID`（默认保留现有 `G-TYGCT601XW`，置空即完全关闭），经 `app.py` context processor 注入为 `google_analytics_id`。`base.html` 仅在其非空时渲染；且不再在 `<head>` 里硬加载 `<script async src=...gtag/js>`，改为在 `load` 事件后经 `requestIdleCallback`（无则 `setTimeout` 兜底）动态插入 gtag，彻底移出首屏关键路径。

问题与影响：`base.html` 全站加载 `https://www.googletagmanager.com/gtag/js?id=G-TYGCT601XW`。它是 `async`，通常不阻塞 DOM，但国内网络会长时间 pending，影响浏览器连接队列和开发者工具观感。

方向：

- 若统计价值不高：直接移除 Google tag。
- 若仍需要统计：改为生产配置开关；默认关闭，或在 `load`/`requestIdleCallback` 后延迟加载。
- 不引入国内统计 SDK 作为替代，避免为了国内增加新的海外/隐私/合规负担。

完成判断：

- 首屏 HTML 不再立即请求 `googletagmanager.com`，或可由配置关闭。
- 页面功能不依赖 tag 成功加载。
- 若保留统计，确认海外数据缺口可接受。

### GAP-007 — 通用 JS/CSS 按页加载与图标瘦身

- 状态：`partial`（Popper 去重 + FilePond 按拥有者加载已完成并测试；Font Awesome 瘦身按计划推迟）
- 优先级：`P3`
- 依赖：Wave 0/1 复测后仍有明显资源瓶颈

已完成：
- 确认 `bootstrap.bundle.min.js`（v5.2.2）已内置 Popper（供侧边栏 dropdown 使用），且没有任何继承 `base.html` 的页面直接用全局 `Popper`，故从 `base.html` 删除多余的 `popper-v2.11.6.js`。`report_reader.html` 是独立页且直接用全局 `Popper.createPopper`，保留自带的那份。
- `category.html` 的 `filepond.css`、`filepond.js`（437KB）、`filepond.jquery.js` 全部改为仅在 `current_user.username == category.owner` 时加载；匿名/非拥有者浏览公开目录不再下载上传相关 JS/CSS。

推迟：
- Font Awesome subset / 换 inline SVG：风险与工作量较高，计划明确「不放前面」，留待 Wave 0/1/2 部署复测后仍有明显字节瓶颈时再评估。

问题与影响：`base.html` 每页加载 `jquery-3.3.1.js`、`bootstrap.bundle.min.js`、`js.cookie`、`popper-v2.11.6.js`、Font Awesome 全量 CSS 和 webfonts。分类页额外加载 `filepond.js` `437217 bytes`。这些资源多数能缓存，但冷启动和远端 Cloudflare PoP 下仍有成本。

方向：

- 先确认 `bootstrap.bundle.min.js` 是否已包含 Popper；若包含，删除额外 `popper-v2.11.6.js`。
- FilePond 只在目录拥有者且显示上传控件时加载；非拥有者/公开目录不加载上传 JS。
- Font Awesome 可在后续评估 subset 或改用少量 inline/local SVG；这项风险和工作量较高，不放前面。
- 不在当前阶段上 bundler，除非已有简单构建链；避免为了瘦身引入部署复杂度。

完成判断：

- 常见匿名页面冷启动 JS/CSS 字节减少。
- 登录、上传、sidebar toggle、AJAX CSRF、布局切换全部正常。
- 海外首屏不变慢，缓存命中行为不变差。

## 6. 暂不做或需重新评估

- 大陆 CDN / Cloudflare China Network：只有 Wave 0/1 完成后，国内真实用户仍明显慢，且愿意承担 ICP、供应商、证书和缓存规则维护时再评估。
- 动态 HTML Cache Everything：当前页面有 `Vary: Cookie`、匿名 session cookie、CSRF、登录态和 metadata，不值得承担串内容风险。
- 国内外资源域名分流：先用本站本地静态资源解决；分流会增加缓存碎片、调试成本和误判。
- Afdian API 请求链路优化：`/thanks` 有 Redis fresh/last-good 缓存，普通首页只提供链接；当前不是主要瓶颈。

## 7. 验证矩阵

每个完成项至少执行：

- 本地测试：相关单元测试或模板渲染测试；涉及静态资源时检查全仓无旧外链。
- 生产响应头：`curl -I` 看 `Cache-Control`、`CF-Cache-Status`、`Content-Encoding`。
- 国内探针：Globalping 中国至少 1 个节点，记录总耗时、DNS/TCP/TLS/firstByte、`CF-RAY` 后缀。
- 海外探针：美国或欧洲至少 1 个节点，确认请求数/总耗时没有明显回归。
- 浏览器检查：匿名首页、全部目录、公开目录、报告详情、reader、登录页、拥有者上传页。

## 8. Changelog

### WAVE-20260805-03 — Wave 2 落地（GAP-006 / GAP-007 部分）

- 日期：2026-08-05
- Drive AI：Claude
- Review AI：`unassigned`
- 关联事项：GAP-006 → `done`；GAP-007 → `partial`
- 改动：
  - GAP-006：新增 `config.py::GOOGLE_ANALYTICS_ID`（模块级常量，默认 `G-TYGCT601XW`，置空即关闭）+ `app.py` context processor `inject_google_analytics_id`；`base.html` 改为条件渲染 + `load`/`requestIdleCallback` 延迟加载 gtag，移除 `<head>` 里的阻塞式 `<script async ...gtag/js>`。
  - GAP-007：`base.html` 删除多余 `popper-v2.11.6.js`（bootstrap.bundle 已内置 Popper，无页面用全局 Popper；reader 独立页保留自带）；`category.html` 把 `filepond.css/js/jquery.js` 收进 `owner` 判断，非拥有者/匿名不再下载 437KB 上传 JS。
- 关键取舍：GA 用配置开关（模块级常量，和 `AFDIAN_URL` 同套路，能到达生产 `local_config.py`），不引入国内统计 SDK。Font Awesome 瘦身按计划推迟。未上 bundler。
- 验证：`pytest tests/`（144 passed）。新增测试：GA 延迟加载/不硬加载、base 页无 `popper-v2.11.6.js`、category 拥有者加载 FilePond、非拥有者不加载 FilePond。
- 下一步（建议，非阻塞）：部署后浏览器回归——GA 是否仍上报、侧边栏 dropdown/上传/AJAX CSRF/布局切换正常、公开目录确无 FilePond 请求。

### WAVE-20260805-02 — GAP-004 生产 Cache Rule 上线并实测 HIT

- 日期：2026-08-05
- Drive AI：Claude
- Review AI：`unassigned`
- 关联事项：GAP-004 由 `in-progress` 改为 `done`
- 改动：在 Cloudflare zone `everbird.me` 增加 Cache Rule `raw-report-edge-cache`，匹配 `http.host eq "wod.everbird.me" and starts_with(http.request.uri.path, "/r/raw/")`，Cache eligibility = Eligible for cache。
- 关键取舍与坑：最初按计划把 Edge TTL 设为「respect origin」，期望 `Cloudflare-CDN-Cache-Control: public, max-age=86400` 覆盖浏览器的 `Cache-Control: private`，但实测持续 `BYPASS`——CF 在该模式下认了 `private`。排查确认响应无 `Set-Cookie`、无 `Vary`（排除串内容）。最终改为 **Edge TTL = "Ignore cache-control header and use this TTL" = 1 day**、**Browser TTL = respect origin**，绕开 header 覆盖不生效的问题。app 的 CDN 头保留不动。
- 验证：同一 raw URL 连续请求 `cf-cache-status` 由 `MISS` → `HIT`（带 `age`），浏览器仍收到 `cache-control: private, no-cache`。
- 下一步（建议，非阻塞）：按 §7 用 Globalping 做国内/海外探针的前后对比并记录；确认 `/r/report/*`、`/r/category/*` 等动态页仍为 `DYNAMIC`/`BYPASS`。

### WAVE-20260805-01 — Wave 1 落地（GAP-004 应用层 / GAP-005）

- 日期：2026-08-05
- Drive AI：Claude
- Review AI：`unassigned`
- 关联事项：GAP-004 改为 `in-progress`（应用层完成，待生产 Cache Rule/发布/复测）；GAP-005 改为 `done`
- 改动：
  - GAP-004：`views/report.py::_report_raw_response` 在保留浏览器 `Cache-Control: private, no-cache` 的同时新增 `Cloudflare-CDN-Cache-Control: public, max-age=86400`，仅对公开 raw 战报（`/r/raw/*`，蓝图前缀 `/r`）开启共享边缘缓存。测试：扩展 `test_report_raw_revalidates_without_reading_body` 断言 200/304/替换后 200 三种情况都带该 CDN 头且浏览器头不变；新增 `test_dynamic_report_page_has_no_cdn_cache_header` 确认 `/r/report/*`、`/r/category/*` 动态页不发该头（守护 DYNAMIC/BYPASS）。
  - GAP-005：把 reader 固定版本（`?1662631467`）的 `wod_standard.js`、`layout.css`、`skin-cn.css` 及其 `@import` 的 `ajax.css`/`news.css` 共 5 个文件镜像到 `static/wod/`；`report_reader.html` 三处外链改为本地 `url_for('static', ...)`。CSS 内 106 处相对 `url()` 图片引用改写为绝对 delta URL（图片非渲染阻塞，故仍走 delta，满足“无 delta CSS/JS 请求”判断）；`@import` 保持本地。每个镜像文件加了来源 URL / 抓取日期 / 版本 query 注释头。保留 `wodInitialize('delta.world-of-dungeons.org',...)` 运行时 host 与 `/wod/spiel/` 外站跳转链接。测试：新增 `test_reader_uses_local_wod_mirror_not_delta`、`test_wod_mirror_static_files_are_served`。
- 关键取舍：
  - GAP-004 应用层只发 CDN 专用头，浏览器仍走私有 revalidation，弱 ETag 让 Cloudflare 到期回源校验；24h 边缘窗口对“基本不可变”的公开战报可接受。真正开启缓存还需一条只匹配 `/r/raw/*` 的 Cloudflare Cache Rule（“Eligible for cache / Cache Everything”），属需授权的生产配置，尚未执行。
  - GAP-005 只镜像渲染关键的 CSS/JS，CSS 引用的图片改为绝对 delta URL 而非全量镜像（约 90+ 图片），把维护面控制住，同时把 1610ms 的 `wod_standard.js` 与两份 CSS 移出跨境渲染关键路径。未改渲染的死模板 `templates/layout.html`（无任何引用），仅记录待清理。
- 验证：`pytest tests/`（140 passed）。`grep` 确认 `report_reader.html` 无 delta 的 CSS/JS 资源请求，仅剩运行时 host 配置与外站跳转。未做：生产 `curl -I` 响应头、`CF-Cache-Status` HIT、国内/海外探针复测（需部署后），以及 reader tooltip/皮肤/跳转的真实浏览器回归。
- 下一步：请授权并配置 Cloudflare `/r/raw/*` Cache Rule 后发布，按第 7 节做生产响应头与国内/海外探针复测确认 GAP-004；部署后对 reader 做一次浏览器功能回归以关闭 GAP-005。之后按需评估 Wave 2（GAP-006/007）。

### WAVE-20260804-02 — Wave 0 落地（GAP-001/002/003）

- 日期：2026-08-04
- Drive AI：Claude
- Review AI：`unassigned`
- 关联事项：GAP-001、GAP-002、GAP-003 状态改为 `done`
- 改动：
  - GAP-001：删除 `static/css/bootstrap.min.css` 顶部的 Google Fonts `@import`，`--bs-font-sans-serif` 去掉 `Lato,` 前缀改为系统字体栈；同时清理未被模板引用的 `static/css/themes/{cyborg,vapor,darkly}/bootstrap.min.css` 中的同类 `@import`，全仓无 `fonts.googleapis.com` / `fonts.gstatic.com`。
  - GAP-002：删除 `templates/root.html` 与 `templates/category.html` 的 `unpkg.com/filepond` 外链；`category.html` 仅保留本地 `static/css/filepond.css`，`root.html` 无上传控件故直接移除，全仓无 `unpkg.com`。
  - GAP-003：由 1024×1024、`956467 bytes` 的 `logo.png` 生成 `logo-512.webp`（49KB）与 `logo-256.png`（75KB）新文件；`base.html` 侧边栏改用 `<picture>`（WebP 主 + PNG 回退，带 `width/height`）；`report_details.html` 的 OG 图仍用原图（非首屏、不阻塞渲染）。
- 关键取舍：只做本地化/去重/减重，未引入地理分流、国内镜像或缓存动态 HTML；logo 采用新文件名避免依赖同名旧缓存 purge；主题 CSS 虽未被引用仍一并清理以满足“全仓无 Google Fonts”的完成判断。
- 验证：`pytest tests/test_views.py` 全部 34 项通过（覆盖 landing、category、root 等 base.html 渲染路径）；`grep` 确认全仓（排除 docs/git）已无 `fonts.googleapis`/`fonts.gstatic`/`unpkg.com`；本地生成图片字节均满足 GAP-003 完成判断（<120KB 目标）。未做生产响应头/国内外探针复测（需部署后进行）。
- 下一步：进入 Wave 1（GAP-004 raw 战报 Cloudflare 缓存、GAP-005 reader WoD 资源本地镜像）；上线后按第 7 节验证矩阵做生产响应头与国内/海外探针复测。

### WAVE-20260804-01 — Repo 扫描与全局访问计划

- 日期：2026-08-04
- Drive AI：Codex
- Review AI：`unassigned`
- 关联事项：创建 GAP-001..GAP-007
- 改动：基于生产响应、Globalping 中国探针和 repo 扫描，记录 Google Fonts、Google tag、unpkg、reader WoD 外链、logo、raw 缓存和通用静态资源风险。
- 关键取舍：优先本地化/去重/减重/精确缓存这些国内外都受益的改动；不做地理分流，不用国内镜像替代全球资源，不缓存动态 HTML。
- 验证：只读扫描模板、应用代码、静态资源大小和既有 CDN 计划；未修改应用代码或生产配置。
- 下一步：先做 GAP-001、GAP-002、GAP-003；随后推进 GAP-004、GAP-005 并复测国内与海外。
