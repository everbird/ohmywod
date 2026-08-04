---
document_id: ohmywod-afdian-integration-plan
schema_version: 1
document_status: draft
source_of_truth_for: "爱发电站内技术集成（入口按钮接线、开放 API 接入、赞助者墙展示）的实现边界、工作项状态与 wave changelog"
language: zh-CN
created_at: "2026-07-25"
last_updated: "2026-08-04"
review_commit: "5a6a93f"
review_worktree: "clean"
next_item_id: "AFD-005"
---

# 爱发电集成计划（未来）

> 本文是战报网“把爱发电用起来”的最省事落地计划，覆盖两个低成本组合：**① 支持面板加入爱发电入口按钮（纯前端）**；**② 只读赞助者墙（以爱发电为唯一真值源，Redis 缓存，不写 SQLite、不进 DR 链）**。
>
> 支持渠道的**定位、自愿性与文案**以 [站点维护成本支持计划](maintenance-support-plan.md)（SUP-003 / SUP-004）为准，本文不重复拥有；本文只负责爱发电**特有的技术实现**。
>
> **当前结论：先做组合 ①（把 `https://ifdian.net/a/everbird` 作为单一配置入口并入支持面板，与微信码并列，零后端）；组合 ② 作为可选增强，用现成的 `RedisCache` + `cache` 扩展缓存 `query-sponsor` 结果，渲染一个致谢用的赞助者墙。核心功能保持免费，不设付费墙，不做身份关联与自动权益发放，不引入 webhook。**

## 1. 背景、现状与原则

### 1.1 本文负责什么

- 记录爱发电站内**技术集成**的实现边界、未来事项和完成证据：入口按钮接线、开放 API 接入与凭据管理、只读赞助者墙。
- 目标是用最小实现与运维成本把已存在的爱发电主页“用起来”，并可选地给支持者一点非排他的公开致谢。
- **不负责**支持渠道的定位、自愿性表达与首页文案收敛——这些属 [maintenance-support-plan.md](maintenance-support-plan.md) 的 SUP-003 / SUP-004。
- **不负责**任何功能分层、付费墙、身份关联（爱发电用户 ↔ 站点账号）或会员权益发放；这些是更重的独立方向，本文明确不含（见第 6 节）。

### 1.2 2026-07-25 当前基线

| 项 | 当前状态 | 证据与含义 |
|---|---|---|
| 爱发电主页 | 已存在 | `README.md` 与站点内均已填 `https://ifdian.net/a/everbird`；账号、收款属站外事项，非本文范围 |
| 站内支持入口 | 仅微信码 | `ohmywod/templates/landing.html` 的“支持作者”面板只有 `img/wechat-reward-code.jpg`，无爱发电链接 |
| 广告 | 已全部撤除 | maintenance-support-plan SUP-001/002 `done`（2026-07-24 部署，app `327a4e3`） |
| 缓存基建 | 现成可复用 | `ohmywod/config.py` `CACHE_TYPE = "RedisCache"`；`ohmywod/extensions.py` 已有 `cache = Cache()`。赞助者墙缓存层无需新建 |
| 密钥管理 | 现成可复用 | `ohmywod-ops` 用 sops+age 管理密钥，渲染进 `local_config.py`（现有 4 个 `<secret:...>` 字段）。爱发电 token 按同一套路新增即可 |
| DR / 备份 | SQLite 为唯一真值 + litestream | 赞助数据若落 SQLite 即进备份/恢复一致性链，故本文坚持以爱发电为真值、只做缓存（见原则 3） |

### 1.3 爱发电能力边界（只用只读部分）

- 开放 API：`query-sponsor`（查赞助者/会员）、`query-order`（查订单）。鉴权为 `user_id + token`，参数按 `MD5(params + ts + token)` 签名，无 OAuth。
- 本文**只用 `query-sponsor` 的只读能力**做赞助者墙；不使用 webhook、不做订单核验发放。
- token 是敏感凭据；`user_id` 与（如需）`plan_id` 属非密钥。

### 1.4 已拍板的原则

1. 核心功能（看、搜、读、分享战报）始终免费，不因是否支持而分层；本文不引入任何 gate。
2. 爱发电入口 URL 作为**单一配置或模板变量**管理，避免多处硬编码。
3. 赞助数据**以爱发电为唯一真值源**：本地只做 Redis 缓存，绝不写入 SQLite，不进 litestream / DR 备份链。缓存坏了重拉即可。
4. 只读、按需拉取即可满足赞助者墙；**不引入 webhook 或常驻在线校验**，避免新增攻击面与运维负担。
5. 展示以致谢为目的、非排他：只展示爱发电昵称（及可选档位），默认保护隐私，不暴露任何可反查真实身份的信息。
6. token 只进 `ohmywod-ops` 的 sops；仓库不保存 token、订单明细或赞助者 PII。
7. 渠道与展示宁少勿杂；每增加一处展示都要评估隐私、授权与长期维护负担。

### 1.5 成功判断

- 组合 ①：用户能在支持面板一眼看到爱发电入口，点击到达正确主页；URL 只在一处配置；移动端可点或可保存。
- 组合 ②（若做）：赞助者墙数据来自 `query-sponsor` 且经 Redis 缓存命中，源站请求受 TTL 控制；爱发电不可达时页面优雅降级（展示上次缓存或空态），不报错、不阻塞其他页面。
- 全程无任何核心功能被 gate；SQLite 不新增赞助相关表；DR / 备份链不受影响。
- 仓库内无 token、订单或赞助者个人信息。

## 2. 这份计划怎么维护

沿用 [maintenance-support-plan.md](maintenance-support-plan.md) 的同一套约定：个人兴趣项目，不需要 owner / RACI / 增长实验。事项通常由一个 AI 工具推进，另一个 AI 工具独立检查；涉及站外账号、收款或密钥时由用户最后决定并执行。

每个事项两个可选角色：

- `Drive AI`：调查现状、提出选项、实施改动，并更新本文和 changelog。
- `Review AI`：独立检查代码、隐私、用户体验与剩余风险，不只复述 Drive AI 结论。

### 2.1 状态枚举

`todo`（方向已确认未开始）｜`assessing`（需用户选择或外部信息）｜`in_progress`（正在实施）｜`blocked`（有明确阻塞，须写解除方式）｜`done`（完成判断满足且有可复核证据）｜`cancelled`（明确不做，记录理由与重看触发条件）。

### 2.2 更新规则

1. 每个 `AFD-NNN` ID 永久不变、不可复用。新增用 front matter 的 `next_item_id` 并同步递增。
2. 开始工作前先读本文和 `git status`，保留未提交改动。
3. `状态` 是事项主真值；状态变化、代码改动、changelog 放同一波。
4. `done` 需可复核证据；只加了链接、只写了文案、或只拉通一次 API 都不算整个事项完成。
5. `blocked` 写清卡点与解除方式；`cancelled` 写清为何不做与何时重看。
6. token、订单明细、赞助者个人信息不写进本文或仓库任何位置。
7. 涉及爱发电 token / 收款设置等站外操作时，先由用户确认并执行；本文不构成外部账号操作授权。
8. 每波在文末按时间正序追加 changelog；旧记录不重写，纠错追加新记录。
9. 每次变更更新 front matter 的 `last_updated`。

### 2.3 固定工作项格式

- 元信息：`状态`、`优先级`、`波次`、`Drive AI`、`Review AI`、`依赖`、`最后更新`、`结论置信度`
- 内容：`问题与影响`、`证据`、`方向与要点`、`完成判断`、`Review 关注`、`执行证据`

优先级：`P1` 建立“把爱发电用起来”的主路径所必需；`P2` 可选增强，不影响主路径成立。

## 3. 建议推进顺序

### Wave 1：入口按钮（最省事，纯前端）

范围：AFD-001。做完后爱发电就“用起来了”——无需 token、无后端、无 API。这一波即可独立收尾。

### Wave 2：只读赞助者墙（可选增强）

范围：AFD-002、AFD-003、AFD-004。只有在想给支持者一点公开致谢时才做；三项按“接凭据 → 拉取缓存 → 展示”顺序推进，任一步不满意都可停在上一步而不影响 Wave 1。

## 4. 工作项

### AFD-001 — 支持面板加入爱发电入口（纯前端）

- 状态：`done`
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`Claude Code（Opus 4.8）`
- Review AI：`unassigned`
- 依赖：定位与文案对齐 maintenance-support-plan SUP-004（不阻塞技术接线）
- 最后更新：2026-08-04
- 结论置信度：`recommended`

问题与影响：爱发电主页已存在，但站内支持面板只有微信码，用户无从发现可持续支持渠道。这是把爱发电用起来的最低成本一步，零后端。

证据：`ohmywod/templates/landing.html` 的“支持作者”面板（`landing.html:70` 一带），仅 `img/wechat-reward-code.jpg`。

方向与要点：

- 在现有支持面板内加入爱发电入口，与微信码并列；具体形态（按钮 / 链接 / 二维码）结合移动端布局实施时定。
- 爱发电 URL 作为**单一配置或模板变量**，不散落硬编码；未来换主页只改一处。
- 文案与自愿定位对齐 SUP-004，不承诺功能回报、不使用压力式表达；外链带清楚站点名与安全属性（`rel="noopener"`）。
- 移动端二维码提供可点击或可保存的替代路径。

完成判断：支持面板出现爱发电入口并跳转正确主页；URL 仅一处配置；桌面与移动端均可用；文案未暗示支持可换取功能。

Review 关注：小屏布局、外链行为、无障碍文本；确认与 SUP-004 的支持入口收敛不冲突、不重复。

执行证据：

- URL 单点配置：`ohmywod/config.py` 新增**模块级常量** `AFDIAN_URL = "https://ifdian.net/a/everbird"`（公开非密钥）。**注意**：不能放 `DefaultConfig` 类属性——本地/生产运行时 `DefaultConfig` 被 `ohmywod/local_config.py` 整体替换（见 `app.py:12-16`），类属性到不了这些环境。改为模块常量后由 `app.py` 的 context processor `inject_afdian_url` 统一注入模板变量 `afdian_url`，跨所有环境单点一致，换主页只改此一行。
- 入口接线：`ohmywod/templates/landing.html` “支持作者”面板加入 `<a class="donate-afdian-btn" href="{{ afdian_url }}" target="_blank" rel="noopener">`，与微信码并列；顺手给同面板既有 GitHub 外链补上 `rel="noopener"`。
- 文案：改为“核心功能始终免费。如果你愿意让站点继续维持，可以在爱发电支持，或通过微信打赏……”，明确不暗示支持可换取功能，对齐 SUP-004。
- 样式：`ohmywod/static/css/custom.css` 新增 `.donate-afdian-btn`（`inline-flex` 按钮，含 hover/focus 态，复用 `--app-*` 变量），桌面与移动端均可点。
- 验证：本地补齐 `.venv` 依赖后整机启动（supervisord + gunicorn，端口 8013），`GET /` 返回 200，首页“支持作者”面板实际渲染出 `href="https://ifdian.net/a/everbird"` 且带 `target="_blank" rel="noopener"`，确认 context processor 注入在真实 Flask config 下生效。真实浏览器小屏视觉与明暗主题对比度仍留待人工复核。

### AFD-002 — 接入爱发电开放 API 与凭据管理

- 状态：`assessing`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：AFD-001；用户在爱发电后台获取 `user_id` / `token`
- 最后更新：2026-07-25
- 结论置信度：`recommended, external setup required`

问题与影响：赞助者墙需要只读调用 `query-sponsor`，其鉴权依赖 `user_id + token` 与 MD5 签名。token 是敏感凭据，必须走既有密钥管理，不能进公开 app 仓。

证据：`ohmywod-ops` 现用 sops+age 管理密钥并渲染进 `local_config.py`（现有 4 个 `<secret:...>` 字段）；`ohmywod/config.py` 已集中管理配置。

方向与要点：

- 封装一个最小只读客户端：按爱发电文档拼参数、加 `ts`、算 `MD5(params+ts+token)` 签名，仅调用 `query-sponsor`。
- `AFDIAN_TOKEN` 作为**新密钥字段**加入 `ohmywod-ops` 的 `secrets.sops.yaml`，渲染进 `local_config.py`，沿用现有 4 密钥同一套路。
- `AFDIAN_USER_ID`（及如需的 `plan_id`）属非密钥，放 `config.py` 或 ops 的 `vars.yml`。
- 网络调用设超时与异常兜底，任何失败都不得向上抛成 500。

完成判断：本地能用真实凭据成功拉到一次 `query-sponsor` 且签名校验通过；token 只存在于 sops，仓库 grep 无明文；`user_id` 等非密钥集中配置。

Review 关注：token 是否泄漏进日志 / 异常信息 / 模板；签名与 `ts` 实现是否符合当时爱发电文档；超时与失败路径是否健壮。

执行证据：尚无；等待用户提供 / 确认 `user_id` 与 `token`。

### AFD-003 — query-sponsor 拉取与缓存层（以爱发电为真值，不写 SQLite）

- 状态：`todo`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：AFD-002
- 最后更新：2026-07-25
- 结论置信度：`recommended`

问题与影响：直接每次请求都打爱发电 API 会慢且脆。需要一层缓存，同时坚持“爱发电是唯一真值、本地只缓存”的边界，避免污染 SQLite / DR 链。

证据：`ohmywod/extensions.py` 已有 `cache = Cache()`，`ohmywod/config.py` `CACHE_TYPE = "RedisCache"`，缓存基建现成。

方向与要点：

- 用现成 `cache` 扩展包一层 `get_sponsors()`：命中缓存直接返回，未命中调 AFD-002 客户端并回填。
- TTL 取一个较长值（如 1 小时，实施时定），把展示新鲜度与源站压力平衡好。
- **绝不落 SQLite**，不新增任何赞助相关表、迁移或模型；数据只活在 Redis 缓存里。
- 失败降级：爱发电不可达或超时时返回上次缓存或空列表，绝不 500、绝不阻塞其它页面渲染。

完成判断：赞助者数据经 Redis 缓存命中，源站请求受 TTL 控制；模拟爱发电故障时页面优雅降级；全仓无赞助相关 SQLite 表 / migration。

Review 关注：缓存键与失效行为；故障注入下的降级路径；确认没有任何写库副作用潜入 DR / litestream 链。

执行证据：尚无。

### AFD-004 — 赞助者墙展示与隐私 / 授权

- 状态：`assessing`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：AFD-003
- 最后更新：2026-07-25
- 结论置信度：`optional`

问题与影响：赞助者墙是给支持者的公开致谢，但涉及第三方个人信息展示，需要在“表达感谢”与“保护隐私”之间取一个克制的默认。

证据：当前站内无任何赞助者展示；maintenance-support-plan SUP-006 已定“回馈以致谢为主、允许匿名”。

方向与要点：

- 展示内容限于爱发电昵称（及可选档位）；不展示任何可反查真实身份的信息，匿名支持者归入“匿名支持者”。
- 金额是否展示、展示到什么粒度需用户决定（默认建议不展示精确金额，与 maintenance-support-plan 一致）。
- 形态（独立致谢页 / 支持页内区块）结合现有路由与移动端布局实施时定。
- 与 SUP-006 的“允许匿名 / 主动授权”口径对齐，不制造持续内容或客服义务。

完成判断：赞助者墙以克制方式展示致谢；默认不泄露可反查身份信息；匿名策略与 SUP-006 一致；不形成新的长期承诺。

Review 关注：是否泄露 PII；匿名默认是否稳妥；小屏展示与空态；文案是否让人误以为支持可换取功能。

执行证据：尚无。

## 5. 待决策清单

不阻塞 Wave 1，可在处理对应事项时回答：

1. 爱发电入口形态：按钮、纯链接，还是二维码并列？（AFD-001）
2. 是否做组合 ② 赞助者墙？若不做，AFD-002~004 可整体标 `cancelled`，Wave 1 独立成立。（AFD-002）
3. 赞助者墙展示粒度：昵称，还是昵称+档位？是否展示金额？（AFD-004）
4. 匿名策略：默认匿名，还是征得同意后显示昵称？（AFD-004）
5. 是否只展示某档位（如月度支持者）还是全部发电者？（是否需要 `plan_id` 过滤，AFD-002/004）
6. 赞助者墙放独立致谢页还是并入支持页区块？（AFD-004）

## 6. 明确不做

- 不 gate 任何核心功能（看、搜、读、分享战报），不设付费墙、下载限额或支持者专属核心功能。
- 不做身份关联（爱发电用户 ↔ 站点账号）与自动会员 / 权益发放；那是更重的独立方向，不属本计划。
- 不引入 webhook 或常驻在线的订单校验；赞助者墙只按需只读拉取。
- 不把赞助数据写入 SQLite，不新增相关表 / migration，不纳入 litestream / DR 备份链。
- 不在仓库保存 token、订单明细或赞助者个人信息。
- 不展示精确账单、募款进度条或“未达目标即停站”式表达（与 maintenance-support-plan 一致）。
- 不重复拥有支持渠道的定位与文案——以 maintenance-support-plan（SUP-003/004）为准。

## 7. Changelog（append-only，旧 -> 新）

> 每波改动在本节末尾追加。不得改写旧记录；如旧记录有误，追加 correction wave。

### Changelog 条目模板

复制以下模板并追加到本节末尾；条目 ID 使用 `WAVE-YYYYMMDD-NN`：

```markdown
### WAVE-YYYYMMDD-NN — 简短标题

- 日期：YYYY-MM-DD
- Drive AI：工具名称；未使用则写“无”
- Review AI：工具名称；尚未 review 则写 `unassigned`
- 关联事项：AFD-NNN, AFD-NNN
- 状态变化：例如 AFD-001 `todo` -> `in_progress` -> `done`
- 改动：文件、站内页面或站外设置摘要
- 关键取舍：选择和理由；无则写“无”
- 验证：检查、测试或人工确认摘要，不含 token 和赞助者个人信息
- 发生的问题：无则写“无”
- 剩余风险：本波未解决的内容
- 下一步：下一事项或需要用户决定的问题
```

### WAVE-20260725-01 — 爱发电集成计划建档

- 日期：2026-07-25
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：创建 AFD-001 至 AFD-004
- 状态变化：新增 2 个 `todo`（AFD-001、AFD-003）、2 个 `assessing`（AFD-002、AFD-004）
- 改动：新增 `docs/afdian-integration-plan.md` 草案；沿用 maintenance-support-plan 的 front matter、工作项与 append-only changelog 结构；未修改应用代码或站外账号
- 关键取舍：划清与 maintenance-support-plan 的边界——定位 / 文案 / 自愿性归 SUP-003/004，本文只拥有爱发电的技术实现（入口接线、API 接入、赞助者墙）；坚持“爱发电为唯一真值、只做 Redis 缓存、不写 SQLite / 不进 DR 链”，把赞助者墙与站点已有的备份一致性洁癖对齐
- 验证：核对当前支持面板（`landing.html` 仅微信码）、缓存基建（`RedisCache` + `cache` 扩展现成）、密钥管理（sops 可复用）；worktree clean @ `5a6a93f`
- 发生的问题：无
- 剩余风险：组合 ② 依赖用户在爱发电后台取 `user_id` / `token`（站外事项，AFD-002 `assessing`）；赞助者墙展示粒度与匿名策略待用户决定
- 下一步：确认草案后先执行 Wave 1（AFD-001，纯前端）；组合 ② 视是否需要公开致谢再决定

### WAVE-20260804-01 — Wave 1 落地：支持面板加入爱发电入口

- 日期：2026-08-04
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：AFD-001
- 状态变化：AFD-001 `todo` -> `done`
- 改动：`ohmywod/config.py` 新增**模块级常量** `AFDIAN_URL`（单点配置，公开非密钥）；`ohmywod/app.py` 加 context processor `inject_afdian_url` 注入模板变量 `afdian_url`；`ohmywod/templates/landing.html` “支持作者”面板加入爱发电入口按钮（与微信码并列，`target="_blank" rel="noopener"`，读 `{{ afdian_url }}`），并给同面板 GitHub 外链补 `rel="noopener"`，文案改为强调核心功能免费、不暗示回报；`ohmywod/static/css/custom.css` 新增 `.donate-afdian-btn` 按钮样式。未触碰 API / token / 站外账号。
- 关键取舍：入口形态选“带图标的按钮链接”而非纯文字或二维码（回答待决策 #1）——微信码保留原二维码给移动端可保存路径，爱发电用可点按钮即可，两者形态各取所长。URL 单点方式从“`DefaultConfig` 类属性”改为“模块常量 + context processor”：因本地/生产的 `DefaultConfig` 被 `local_config.py` 整体替换，类属性到不了运行环境，会让模板 `config['AFDIAN_URL']` 抛 `KeyError`、首页 500；模块常量经 context processor 注入才真正做到跨环境单点一致。
- 验证：本地补齐 `.venv` 依赖后整机启动（supervisord + gunicorn @ 8013），`GET /` 返回 200，首页面板实际渲染出正确 `href="https://ifdian.net/a/everbird"` 与 `rel="noopener"`，确认真实 Flask 下注入生效。改动未提交（保留在工作树）。
- 发生的问题：初版把 `AFDIAN_URL` 放进 `ohmywod/config.py` 的 `DefaultConfig` 类，误以为模板可经 `config['AFDIAN_URL']` 读到；起本地环境时发现本地/生产实际用 `local_config.py` 的 `DefaultConfig`（整体替换而非继承），该类属性根本不加载，会导致首页 `KeyError`。改为模块常量 + context processor 后整机验证通过。教训：`ohmywod/config.py` 的 `DefaultConfig` 在有 `local_config` 时不参与运行，跨环境常量不能挂在它上面。
- 剩余风险：未在真实浏览器 / 小屏做视觉与无障碍复核；`.donate-afdian-btn` 的明暗主题对比度未实测。
- 下一步：由 Review AI 做小屏布局 / 外链行为 / 无障碍复核，或直接部署后人工验收；组合 ②（AFD-002~004）视是否需要公开致谢再决定，AFD-002 仍等用户提供 `user_id` / `token`。
