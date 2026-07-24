---
document_id: ohmywod-cdn-improvement-plan
schema_version: 1
document_status: draft
source_of_truth_for: "future CDN cache scope, domestic access improvement direction, work item status, and wave changelog"
language: zh-CN
created_at: "2026-07-24"
last_updated: "2026-07-24"
review_commit: "907babd"
review_worktree: "dirty: existing docs/ha-plan.md changes preserved"
next_item_id: "CDN-003"
---

# 国内访问与 CDN 改进计划（未来）

> 本文是战报网未来 CDN 与国内访问体验优化的工作计划，不是多地域部署方案。节点替换与恢复以 [单机 DR 与节点替换计划](ha-plan.md) 为准，已经完成的应用缓存与安全基线以 [站点改进计划](improvement-plan-2026-07.md) 为准。
>
> **当前结论：继续使用 Cloudflare 橙云和东京源站，不增加国内节点或更换 CDN。下一步最有价值的两项小改进是：让公开且基本不可变的 `/r/raw/*` 战报 HTML 在 Cloudflare 边缘缓存 1 天；缩小每页都会加载的 1024×1024、约 956 KB logo。两项可以并行。metadata 页面、登录态页面和互动接口继续不缓存。**

## 1. 边界、现状与原则

### 1.1 本文负责什么

- 记录 Cloudflare 对公开战报与静态资源的缓存边界、未来事项和完成证据。
- 目标是用很小的实现与运维成本改善国内用户的重复访问和冷页面加载体验。
- 不负责 PostgreSQL、共享 Redis、无状态多节点或跨地域数据库；这些只有在站点规模与需求发生明显变化时再单独规划。
- 不把中国大陆节点、ICP 备案、Cloudflare China Network 或另一家 CDN 作为当前事项。

### 1.2 2026-07-24 当前基线

| 链路 | 当前状态 | 证据与含义 |
|---|---|---|
| 应用与对象存储区域 | 东京 | `ohmywod-ops/scripts/dr-node` 默认区域为 `ap-northeast`；JuiceFS / Litestream 对象存储 endpoint 位于 `jp-tyo-1` |
| Cloudflare 入口 | 已启用 | `wod.everbird.me` 使用橙云代理；公网响应有 `server: cloudflare`、`cf-ray` 和 HTTP/3 `alt-svc` |
| 文本压缩 | 已启用 | 公开 CSS 与真实 `/r/raw/*` 请求在声明 `Accept-Encoding: br, gzip` 时返回 `content-encoding: br` |
| `/static/*` | 已缓存 | 生产 `logo.png` 与 CSS 返回 `Cache-Control: max-age=14400`，实测 `CF-Cache-Status: REVALIDATED` |
| `/r/raw/*` | 未共享缓存 | 生产真实战报返回 `Cache-Control: private, no-cache`、`CF-Cache-Status: DYNAMIC`；CSP 仍为 `sandbox allow-scripts allow-popups` |
| metadata / 动态页面 | 不可直接共享缓存 | 首页与目录页返回 `Vary: Cookie` 和匿名 session cookie；报告详情、metadata、登录与互动内容可能因用户或数据库状态变化 |
| 战报规模 | CDN 有实际收益空间 | 既有扫描为约 105.3 GB HTML；单文件平均约 846 KB、中位数约 432 KB，且内容高度可压缩 |
| logo | 冷加载体积偏大 | `static/img/logo.png` 为 1024×1024、956,467 bytes；页面 CSS 最大只显示到 256px |

### 1.3 已拍板的原则

1. 只缓存明确公开、对所有访问者响应一致、基本不可变的内容。
2. `/r/raw/*` 与报告 metadata 分开处理：raw HTML 可以长缓存；`/r/report/*`、reader、分类、搜索、`/usage`、登录和互动接口保持动态。
3. 用户上传 HTML 的 CSP sandbox 不能因为 CDN 改动而削弱；不得加入 `allow-same-origin`。
4. 浏览器继续保留当前的重新验证语义；用 `Cloudflare-CDN-Cache-Control` 单独控制 Cloudflare 边缘缓存。
5. 首版接受极少数战报替换或删除后最多 1 天的边缘旧副本，不为此立即增加自动 purge、队列或额外凭据。
6. metadata 修改不会改变 raw HTML，因此不触发 raw 缓存失效。
7. 不缓存整个站点，不使用宽泛的 Cache Everything，不把 Cookie 或用户身份带入共享缓存。
8. 先验证国内真实访问效果与 Cloudflare 命中率；没有证据时不购买 Argo、Cache Reserve、Enterprise China Network 或另一家 CDN。

### 1.4 成功判断

- `/r/raw/*` 在同一 Cloudflare 边缘首次请求为 `MISS` / `REVALIDATED`，后续请求可见 `HIT`，且边缘 TTL 为 1 天。
- raw 的浏览器响应仍为 `Cache-Control: private, no-cache`，ETag、304 和 CSP sandbox 行为没有回归。
- metadata 更新立即可见，不会因为 raw CDN 缓存而延迟。
- 首页、报告详情、登录、搜索、`/usage`、点赞与收藏等动态页面保持 `DYNAMIC` / `BYPASS`。
- logo 明显小于当前 956 KB，桌面与移动端显示无肉眼可见退化。
- 国内用户对重复访问热门战报的体感或实测有改善；若没有改善，不继续扩大 CDN 工作。

## 2. 这份计划怎么维护

这是个人兴趣项目，只保留稳定 ID、状态、完成判断和简短 changelog，不引入复杂的性能平台或多供应商方案。

工作项状态沿用其他计划：

- `todo`：方向已确认，尚未实施
- `in_progress`：正在实现或验证
- `blocked`：存在明确阻塞，并写明解除方式
- `done`：完成判断已满足，并有可复核证据
- `cancelled`：明确决定不做，并记录重新考虑的触发条件

更新规则：

1. `CDN-NNN` ID 永久不变。新增事项使用 front matter 的 `next_item_id` 并同步递增。
2. 开始工作前先读本文和 `git status`，保留用户或其他工具的未提交改动。
3. 涉及 Cloudflare 控制台、API token 或生产发布时，需要用户明确授权；本文不构成站外修改授权。
4. `done` 至少需要测试、生产响应头和一次真实 Cloudflare 命中验证。
5. 每波改动在文末追加 changelog，并更新 `last_updated`。

## 3. 建议推进顺序与依赖

```text
CDN-001 公开战报边缘缓存 ──┐
                          ├──> 国内真实访问复测 ──> 决定是否还值得继续
CDN-002 logo 减重 ─────────┘
```

CDN-001 与 CDN-002 没有顺序依赖，可以并行。完成后先停下来观察，不自动增加新的 CDN 工作。

明确暂不做：

- 自动 purge：只有 1 天旧副本确实造成用户问题时再补；届时优先在重新上传和删除时按报告 URL 前缀清理。
- `/static/*` 更长 TTL：当前已经缓存，先完成 logo 减重；只有部署后频繁回源或静态流量明显时再调整。
- 动态 HTML 缓存：匿名请求也会创建 session，且页面含 metadata 与用户状态，不值得承担串内容风险。
- 独立 `cdn.` 子域名或直接公开 JuiceFS bucket：前者增加连接与配置，后者存的是 JuiceFS 数据块而不是可直接访问的原始文件。
- 中国大陆 CDN：只有愿意办理 ICP 备案且实测东京 + Cloudflare 仍不能满足需求时再评估。

## 4. 工作项

### CDN-001 — 为公开且基本不可变的 raw 战报增加 Cloudflare 边缘缓存

- 状态：`todo`
- 优先级：`P1`
- 波次：Wave 0
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-24
- 结论置信度：`confirmed`

问题与影响：`/r/raw/*` 是公开、非个性化且基本不会修改的战报 HTML，但当前 `private, no-cache` 使 Cloudflare 每次都回东京源站。它绕过了 CDN 最能改善的部分，也让每次请求都经过 Flask、JuiceFS 元数据和对象读取链路。

证据：

- `ohmywod/views/report.py::_report_raw_response` 当前设置 `Cache-Control: private, no-cache`。
- 生产真实 `/r/raw/*` 响应为 `CF-Cache-Status: DYNAMIC`，没有 `Set-Cookie`，只有 `Vary: accept-encoding`，且对所有访问者返回同一 raw 内容与固定 reader-state beacon。
- 既有扫描显示 HTML 单文件平均约 846 KB、中位数约 432 KB，总量约 105.3 GB；群内分享的同一战报有重复访问场景。

方向与要点：

- Cloudflare Cache Rule 只匹配：

  ```text
  (http.host eq "wod.everbird.me"
   and starts_with(http.request.uri.path, "/r/raw/"))
  ```

- 设置 `Cache eligibility: Eligible for cache`，Edge TTL 尊重源站。
- raw 响应继续给浏览器：

  ```http
  Cache-Control: private, no-cache
  ```

- 同时只给 Cloudflare 增加：

  ```http
  Cloudflare-CDN-Cache-Control: public, max-age=86400
  ```

- 保留现有 weak ETag、304、`Content-Security-Policy: sandbox allow-scripts allow-popups` 和 reader-state beacon。
- metadata 编辑不清缓存。首版不接自动 purge，接受重新上传或删除后最多 1 天旧副本。

完成判断：

- 单元测试覆盖 200 与 304 响应都保留 CSP、ETag、浏览器 Cache-Control 和 Cloudflare 专用缓存头。
- Cloudflare 规则仅命中 `/r/raw/*`；真实 raw 连续请求出现 `HIT`，动态页面仍为 `DYNAMIC` / `BYPASS`。
- 报告 metadata 修改立即可见；raw iframe、页内跳转、tooltip 和 reader-state 兼容行为正常。
- 记录一个国内网络下的首次与重复访问对比；只需证明方向有收益，不设工业级 SLO。

Review 关注：规则路径误写成 `/raw/*` 而漏掉真实 `/r/raw/*`；缓存整个 `/r/*`；Cloudflare 缓存头覆盖浏览器语义；304 丢 CSP；缓存响应意外包含 `Set-Cookie`；削弱 sandbox。

执行证据：尚无。

### CDN-002 — 缩小每页加载的 logo

- 状态：`todo`
- 优先级：`P2`
- 波次：Wave 0
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：无；可与 CDN-001 并行
- 最后更新：2026-07-24
- 结论置信度：`confirmed`

问题与影响：`static/img/logo.png` 为 1024×1024、约 956 KB，而侧边栏 CSS 最大只显示到 256px。即使 CDN 命中，用户首次打开页面仍要下载完整字节；这对国内移动网络的影响可能比继续调整静态 TTL 更直接。

证据：

- `file static/img/logo.png`：1024×1024 RGBA PNG。
- 文件大小：956,467 bytes。
- `static/css/custom.css`：`.brand-logo` 最大高度为 256px。
- `templates/base.html` 在普通页面侧边栏加载该图片；`report_details.html` 还将它用作 OG 图片。

方向与要点：

- 生成适合 256px 展示的轻量版本；可以保留 512px 以兼顾高 DPI。
- 优先保持一个简单、兼容的图片源，不为几十 KB 收益引入复杂响应式图片管线。
- 若 UI 与 OG 对清晰度要求不同，可以保留原图仅作 OG，页面加载轻量版本；是否拆分以实际体积和视觉对比决定。
- 文件名若不变，部署后清理该静态 URL 的 Cloudflare 缓存；若使用新文件名，则模板切换后自然失效。

完成判断：

- 页面实际加载的 logo 显著小于当前 956 KB，建议目标不超过 250 KB。
- 桌面、移动端和高 DPI 显示无明显模糊或透明背景异常。
- 首页、侧边栏和 OG 预览使用正确；Cloudflare 返回缓存命中且 Brotli/HTTP/3 基线无回归。

Review 关注：只改 CSS 尺寸但没有减少下载字节；误伤透明背景；社交预览不支持所选格式；同名替换后 Cloudflare 或浏览器仍显示旧图。

执行证据：尚无。

## 5. 未来重新评估条件

只有满足以下任一条件，才新增后续 CDN 事项：

- CDN-001 上线后，热门 raw 战报仍长期没有 `HIT`，且国内真实访问仍明显慢。
- raw 删除或重新上传后的 1 天旧副本确实产生用户问题，需要自动 purge。
- Cloudflare 统计或源站日志显示 `/static/*` 仍有明显重复回源，值得延长边缘 TTL。
- 国内用户量和维护意愿足以承担 ICP 备案与大陆 CDN；届时仍只优先加速 `/static/*` 与 `/r/raw/*`。
- 动态页面的服务端 TTFB 成为实测主瓶颈；该问题归应用查询或部署位置，不用 Cache Everything 掩盖。

## 6. Changelog

### WAVE-20260724-01 — 建立轻量 CDN 未来方案

- 日期：2026-07-24
- Drive AI：Codex
- Review AI：`unassigned`
- 关联事项：创建 CDN-001、CDN-002
- 状态变化：CDN-001、CDN-002 创建为 `todo`
- 改动：记录东京源站、Cloudflare 橙云、静态缓存、Brotli/HTTP/3 与 raw `DYNAMIC` 基线；将未来工作收敛为 raw 一天边缘缓存和 logo 减重
- 关键取舍：raw 与 metadata 分离；浏览器继续重验证，Cloudflare 单独缓存 1 天；暂不做自动 purge、动态页面缓存、独立 CDN 子域名、大陆节点或供应商切换
- 验证：只读核对应用路由、缓存头、CSP、logo 尺寸与 CSS；对生产首页、静态资源和真实 raw URL 检查公开响应头；未修改 Cloudflare 或生产
- 发生的问题：无
- 剩余风险：Cloudflare 标准全球网络对不同国内运营商的实际路径仍可能波动；只有上线 raw 缓存并从国内网络复测后才能确认体感收益
- 下一步：CDN-001 与 CDN-002 可并行；实施需单独确认 Cloudflare 规则与生产发布
