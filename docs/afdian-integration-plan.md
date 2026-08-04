---
document_id: ohmywod-afdian-integration-plan
schema_version: 1
document_status: draft
source_of_truth_for: "爱发电站内技术集成（入口按钮接线、开放 API 接入、赞助者墙展示）的实现边界、工作项状态与 wave changelog"
language: zh-CN
created_at: "2026-07-25"
last_updated: "2026-08-04"
review_commit: "b1728f5"
review_worktree: "dirty (AFD-001 review nit: custom.css text-bright fallback)"
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
5. 展示以致谢为目的、非排他：优先展示用户在爱发电赞助方案自定义字段填写的“致谢页显示名（可选）”；留空用爱发电昵称，填“匿名”则显示为“匿名支持者”。默认保护隐私，不暴露任何可反查真实身份的信息。
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
- Review AI：`Claude Code（Opus 4.8）`
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
- Review（2026-08-04，Claude Code Opus 4.8）：复核已提交代码 `b1728f5`。单点配置（模块常量 + context processor）、外链 `target/rel`（爱发电按钮与 GitHub 均补 `rel="noopener"`）、SUP-004 文案、键盘可聚焦与图标+可见文字的无障碍均通过。确认全站为**纯暗色主题**（无 `prefers-color-scheme` / `data-theme` 切换），故“明暗对比”实为单主题对比，按钮复用 `--app-border` / `--app-surface-hover`，与全站一致。**唯一瑕疵**：`.donate-afdian-btn` 的 `color` 用了全站未定义的 `--app-text-bright` 且无兜底，回退到继承色（可读但非预期亮白）；已对齐 `custom.css` 既有写法（line 1651）改为 `var(--app-text-bright, #fff)`。此改动尚未提交（工作树）。

### AFD-002 — 接入爱发电开放 API 与凭据管理

- 状态：`done`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`Claude Code（Opus 4.8）`
- Review AI：`unassigned`
- 依赖：AFD-001；用户已在爱发电后台提供 `user_id` / `token`（已 provision）
- 最后更新：2026-08-04
- 结论置信度：`recommended`

问题与影响：赞助者墙需要只读调用 `query-sponsor`，其鉴权依赖 `user_id + token` 与 MD5 签名。token 是敏感凭据，必须走既有密钥管理，不能进公开 app 仓。

证据：`ohmywod-ops` 现用 sops+age 管理密钥并渲染进 `local_config.py`（现有 4 个 `<secret:...>` 字段）；`ohmywod/config.py` 已集中管理配置。

方向与要点：

- 封装一个最小只读客户端：按爱发电文档拼参数、加 `ts`、算 `MD5(params+ts+token)` 签名，仅调用 `query-sponsor`。
- `AFDIAN_TOKEN` 作为**新密钥字段**加入 `ohmywod-ops` 的 `secrets.sops.yaml`，渲染进 `local_config.py`，沿用现有 4 密钥同一套路。
- `AFDIAN_USER_ID`（及如需的 `plan_id`）属非密钥，放 `config.py` 或 ops 的 `vars.yml`。
- 网络调用设超时与异常兜底，任何失败都不得向上抛成 500。

完成判断：本地能用真实凭据成功拉到一次 `query-sponsor` 且签名校验通过；token 只存在于 sops，仓库 grep 无明文；`user_id` 等非密钥集中配置。

Review 关注：token 是否泄漏进日志 / 异常信息 / 模板；签名与 `ts` 实现是否符合当时爱发电文档；超时与失败路径是否健壮。

执行证据（scaffold，2026-08-04；待真实凭据收尾）：

- 只读客户端：新增 `ohmywod/afdian.py`，仅用标准库（`urllib` + `hashlib` + `json`，**不新增依赖**）。`sign()` 实现 `md5(token+"params"+params+"ts"+ts+"user_id"+user_id)`；`query_sponsor()` POST `https://afdian.com/api/open/query-sponsor`，设 `DEFAULT_TIMEOUT=5`，任何网络/HTTP/解码/`ec!=200` 失败都翻译成 `AfdianError` 且**消息不含 token**（只带异常类名 / 安全的 `em`）；`fetch_all_sponsors()` 分页拉取、受 `MAX_PAGES=20` 上界保护。
- 凭据来源与降级：`_credentials()` 从 Flask config 读 `AFDIAN_USER_ID` / `AFDIAN_TOKEN`；空值或未渲染的 `"<secret:..."` 前缀一律视为"未配置"→ `fetch_all_sponsors()` 返回 `[]`、`is_configured()` 为 `False`，绝不抛错。dev/未配置环境天然降级。
- config 契约：`ohmywod/config.py` `DefaultConfig` 加 `AFDIAN_USER_ID` / `AFDIAN_TOKEN`（均缺省空串，仅作 schema 参考——运行时用 `local_config.py`，见 AFD-001 教训）。
- ops 凭据管理（`ohmywod-ops`）：`ohmywod_local_config.py.j2` 加 `AFDIAN_USER_ID = "{{ afdian_user_id | default('') }}"` 与 `AFDIAN_TOKEN = "{{ afdian_token | default('') }}"`（未 provision 时渲染成空串、不 break、不进 secrets 断言）；`secrets.sops.yaml.example` 加 `afdian_token`（密钥，可选）；`vars.yml` 加 `afdian_user_id`（非密钥）。真实 token 由用户经 sops 写入 `secrets.sops.yaml`、`user_id` 写入 `vars.yml`（站外步骤，本文不代为操作）。
- 验证：`tests/test_afdian.py` 8 项全绿——签名对已知向量、未配置→空、占位符 `"<secret:..."` 不当真值、分页、`MAX_PAGES` 上界、以及两条错误路径断言**不泄漏 token**；全仓 120 项测试通过；`import ohmywod.afdian` 干净；Jinja 渲染验证 `default('')` 在未 provision / 已 provision 两态都正确。仓库 grep 无明文 token（凭据只经 sops）。
- 真实凭据收尾（2026-08-04，已转 `done`）：用户经 sops 写入 `afdian_token`、`vars.yml` 填 `afdian_user_id`（本机 `sops -d` 解密通过、两者均在）。用真实凭据实调 `https://afdian.com/api/open/query-sponsor` **成功**：HTTP 200、`ec=200`、`em=sponsor`、`data` 含 `list/total_count/total_page`，当前 `total_count=0`（账号暂无赞助者，属正常空态）。签名口径 `md5(token+"params"+params+"ts"+ts+"user_id"+user_id)` 经真实服务端校验通过。经完整客户端路径 `is_configured()=True`、`fetch_all_sponsors()=[]`（空态不报错）。token 全程只在 sops / 进程环境变量，未落任何文件、未入日志/异常。
- **实调发现并修复的真实缺陷（UA/1010）**：`afdian.com` 在 Cloudflare 后，默认 `Python-urllib` UA 会被 **HTTP 403 error code 1010**（浏览器签名封禁）挡下。客户端已加浏览器 `User-Agent`（`ohmywod/afdian.py` `USER_AGENT` 常量 + 请求头），并加 `Accept: application/json`。另确认正确 host 是 `afdian.com`（`afdian.net` 已不解析）。新增 `tests/test_afdian.py::test_query_sponsor_sends_browser_user_agent` 守此回归。全仓 121 项测试通过。

### AFD-003 — query-sponsor 拉取与缓存层（以爱发电为真值，不写 SQLite）

- 状态：`done`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`Claude Code（Opus 4.8）`
- Review AI：`unassigned`
- 依赖：AFD-002
- 最后更新：2026-08-04
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

执行证据（2026-08-04）：

- 缓存包装：`ohmywod/afdian.py` `get_sponsors()` 用现成 `cache_get` / `cache_set`（`ohmywod/extensions.py`，本就 fail-soft）。命中 `afdian_sponsors_fresh` 直接返回；未命中调 `fetch_all_sponsors()` 并同时回填 `fresh`（TTL）与 `last_good`（长存 7 天）两份。
- TTL：`AFDIAN_CACHE_TTL`（`config.py` 缺省 3600=1h，可覆盖）控制 `fresh` 新鲜度，把展示新鲜度与源站压力平衡好。
- 故障降级：源站不可达 / `AfdianError` 时，返回 `last_good`（上次成功结果），无则返回 `[]`；只 `logger.warning`（仅异常类名），**绝不抛错、绝不阻塞页面渲染**。未配置直接返回 `[]`。
- 边界坚守：**不落 SQLite**、无任何赞助相关模型 / migration / 表，数据只活在 Redis 缓存；不进 litestream / DR 链。
- 验证：`tests/test_afdian.py` 新增 4 项——未配置→空、miss→拉取+回填且二次命中不再拉取、故障→降级到 `last_good`、故障且无缓存→空；`test_afdian` 共 13 项全绿。缓存后端无关（测试用 `simple`，生产用 `RedisCache`，同走 `cache_get/set`）。
- 剩余：真实赞助者数据形状（`total_page` 分页、档位字段）在账号有赞助者前未见实样，属 AFD-004 展示映射的关注点，不影响缓存机制成立。

### AFD-004 — 赞助者墙展示与隐私 / 授权

- 状态：`done`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`Claude Code（Opus 4.8）`
- Review AI：`unassigned`
- 依赖：AFD-003
- 最后更新：2026-08-04
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

用户拍板（2026-08-04，回答待决策 #3/#4/#6）：**仅展示昵称**（不显档位、不显金额）；**显示昵称、缺失/匿名者归"匿名支持者"**；放**独立致谢页**。#5（是否按档位过滤）未单列，当前展示全部发电者、不过滤。2026-08-04 追加口径：爱发电赞助方案新增自定义字段“致谢页显示名（可选）”，说明为“自定义留名，留空用昵称。匿名请填“匿名””。展示时优先使用该字段；字段留空回落爱发电昵称；字段为“匿名”时显示“匿名支持者”。

执行证据（2026-08-04）：

- 展示映射：`ohmywod/afdian.py` `sponsor_display_names()` 从 `get_sponsors()`（AFD-003 缓存）取显示名，隐私优先——优先识别爱发电赞助方案自定义字段“致谢页显示名（可选）”；字段留空回落 `user.name`；字段为“匿名”或昵称空白/缺失、畸形条目时显示 `ANONYMOUS_NAME="匿名支持者"`；不出金额 / `user_id` / 头像；未配置 / 空源→`[]`。
- 独立致谢页：`ohmywod/views/frontend.py` 加 `GET /thanks`（`thanks_page`），渲染 `ohmywod/templates/thanks.html`（继承 `base.html`）。有数据出 `.sponsor-wall` 昵称 chip；空态出克制文案（"暂时还没有赞助者…"）；页脚说明"自定义致谢页显示名优先、留空用爱发电昵称、填匿名显示匿名支持者、不显金额"。文案不暗示支持可换功能，对齐 SUP-004/006。
- 入口：左侧全局侧栏导航加"赞助者致谢"项（`base.html`，`heart` 图标，`url_for('frontend.thanks_page')`，全站可达）；首页"支持作者"面板另加"查看赞助者致谢 →"链接。
- 隐私 / 安全：第三方昵称经 Jinja 自动转义（测试断言 `<script>` 被转义、不落原样），无反查身份信息、无金额、无持续客服义务。
- 样式：`custom.css` 加 `.sponsor-wall` / `.sponsor-chip`（圆角 chip，flex wrap，`word-break`）/ `.sponsor-empty` / `.sponsor-note` / `.donate-thanks-link`，复用 `--app-*` 变量。
- 验证：`tests/test_afdian.py` 加 4 项（映射+匿名化、空、`/thanks` 空态 200、`/thanks` 列表且 XSS 转义），`test_afdian` 共 17 项、全仓 129 项测试全绿；真实 Flask 路由渲染 `/thanks` 实测出正确 chip（`Alice` / `匿名支持者` / `梦想家`）与首页入口链接。
- 剩余：真实浏览器小屏视觉与明暗（纯暗色单主题）观感未人工验收；账号当前 0 赞助者，线上先呈空态（非缺陷）；真实赞助者数据字段形状未见实样，若 afdian `user.name` 字段路径与预期不符需在有数据时微调（已对畸形条目容错）。

## 5. 待决策清单

> 状态（2026-08-04）：#2 已定为**做组合 ②**并已落地 AFD-002~004；#3/#4/#6 已由用户回答（见 AFD-004）；#5 当前不过滤、展示全部；#1 已在 AFD-001 定为按钮。以下保留原始清单供追溯。

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

### WAVE-20260804-02 — AFD-001 Review 复核与小瑕疵修正

- 日期：2026-08-04
- Drive AI：无
- Review AI：Claude Code（Opus 4.8）
- 关联事项：AFD-001
- 状态变化：AFD-001 保持 `done`；Review AI 由 `unassigned` -> `Claude Code（Opus 4.8）`
- 改动：复核已提交代码 `b1728f5`（config 单点、context processor、landing 外链与文案、CSS 按钮）。仅 CSS 一处修正：`ohmywod/static/css/custom.css` 的 `.donate-afdian-btn` 把 `color: var(--app-text-bright)` 改为带兜底的 `var(--app-text-bright, #fff)`，对齐同文件既有写法（line 1651）。未触碰 API / token / 站外账号。
- 关键取舍：站点为**纯暗色单主题**（无 `prefers-color-scheme` / `data-theme` 切换），故原计划的“明暗对比度”实为单主题对比；按钮复用 `--app-border` / `--app-surface-hover`，与全站一致，不引入新主题变量。
- 验证：静态代码复核 + 变量定义追踪（确认 `--app-text-bright` 全站未定义，故补兜底）。未起服务（本波仅 CSS 兜底值变更，无逻辑分支）。改动未提交（保留在工作树）。
- 发生的问题：无
- 剩余风险：真实浏览器小屏视觉仍未人工验收（纯暗色下按钮 hover/focus 观感）；本波 CSS 兜底改动未提交、未部署。
- 下一步：等用户决定是否做组合 ②（赞助者墙）。若做，AFD-002 需用户在爱发电后台提供 `user_id` / `token`；若不做，AFD-002~004 整体标 `cancelled`，Wave 1 独立成立。

### WAVE-20260804-03 — AFD-002 只读客户端与凭据管理 scaffold

- 日期：2026-08-04
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：AFD-002
- 状态变化：AFD-002 `assessing` -> `in_progress`（用户拍板做组合 ②、承诺提供凭据）
- 改动：app 端新增 `ohmywod/afdian.py`（纯标准库只读客户端：`sign` / `query_sponsor` / `fetch_all_sponsors` / `is_configured`，超时 + `AfdianError` 兜底 + token 不入异常消息）与 `tests/test_afdian.py`（8 项）；`ohmywod/config.py` `DefaultConfig` 加 `AFDIAN_USER_ID` / `AFDIAN_TOKEN` 空缺省作 schema 参考。ops 端（`ohmywod-ops`）`ohmywod_local_config.py.j2` 加两行 `| default('')` 渲染的 AFDIAN 字段、`secrets.sops.yaml.example` 加可选 `afdian_token`、`vars.yml` 加非密钥 `afdian_user_id`。未写 SQLite、未加依赖、未引入 webhook、仓库无明文 token。
- 关键取舍：HTTP 用标准库 `urllib` 而非新引 `requests`（`requests` 非现有依赖，为一个 P2 可选功能不值得扩依赖面）。凭据接入走 ops 的 j2 独立全量类而非 `config.py`（生产 `local_config.py` 由 j2 渲染、整体取代 `config.py`；AFD-001 的教训）。所有 AFDIAN 字段 `default('')` + app 侧"空/占位符=未配置降级"，使该功能对生产**可选**：未 provision 不 break 渲染、不进 secrets 硬断言、页面返回空赞助者墙而非 500。
- 验证：`tests/test_afdian.py` 8 项 + 全仓 120 项测试全绿（`.venv/bin/python -m pytest`）；`import ohmywod.afdian` 干净；两条错误路径断言异常消息不含 token；`sign()` 对独立预计算的 md5 向量匹配；Jinja `default('')` 在 provision / 未 provision 两态渲染均正确。无网络调用（`urlopen` 被 monkeypatch）。改动分两仓，尚未提交。
- 发生的问题：无
- 剩余风险：**未用真实凭据实调一次 `query-sponsor`**——签名字段顺序 / `ts` 口径 / 端点是否与当时爱发电文档完全一致，须在用户 provision 后核实（现按通行的 `md5(token+"params"+params+"ts"+ts+"user_id"+user_id)` 实现）。AFD-003 缓存层与 AFD-004 展示 / 隐私尚未动。
- 下一步：用户在爱发电后台取 `user_id` / `token`，`user_id` 写 `vars.yml`、`token` 经 sops 写 `secrets.sops.yaml`；随后实调一次核签名并把 AFD-002 转 `done`。之后 AFD-003（Redis 缓存层，需定 TTL）与 AFD-004（展示粒度 / 匿名策略，待决策 #3~#6）。

### WAVE-20260804-04 — AFD-002 真实凭据实调收尾 + Cloudflare UA 修复

- 日期：2026-08-04
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：AFD-002
- 状态变化：AFD-002 `in_progress` -> `done`
- 改动：用户 provision 凭据后实调 `query-sponsor` 收尾。发现 `afdian.com` 在 Cloudflare 后默认 `Python-urllib` UA 触发 **HTTP 403 error code 1010**；`ohmywod/afdian.py` 加 `USER_AGENT` 常量与请求头（含 `Accept: application/json`）修复。`tests/test_afdian.py` 加 `test_query_sponsor_sends_browser_user_agent`（共 9 项）。ops 端无新增改动（凭据由用户经 sops / vars.yml 写入，不入本仓）。
- 关键取舍：正确 API host 为 `afdian.com`（`afdian.net` 已不解析，`ifdian.net` 也在同一 Cloudflare 后）。UA 用通用桌面 Chrome 串即可绕过 1010，不需要更复杂的反爬处理（只读、低频）。
- 验证：真实凭据实调 `https://afdian.com/api/open/query-sponsor` 成功 —— HTTP 200、`ec=200`、`em=sponsor`、`data` 含 `list/total_count/total_page`（当前 `total_count=0` 空态）；签名 `md5(token+"params"+params+"ts"+ts+"user_id"+user_id)` 经服务端校验通过；完整客户端路径 `is_configured()=True`、`fetch_all_sponsors()=[]` 不报错。`tests/test_afdian.py` 9 项 + 全仓 121 项测试全绿。token 只在 sops / 进程环境变量，未落文件、未入日志/异常。
- 发生的问题：首次实调对 `afdian.com` 与 `ifdian.net` 均 403 error code 1010（Cloudflare 按 UA 封禁），`afdian.net` DNS 不解析。加浏览器 UA 后 200。
- 剩余风险：账号当前 `total_count=0`，赞助者墙将呈空态（非缺陷）；`query-sponsor` 分页字段（`total_page` 等）在有真实赞助者时的形状尚未见实样，AFD-004 展示映射需在有数据时再核。
- 下一步：AFD-003（Redis 缓存层 `get_sponsors()`，需你定 TTL，计划建议 ~1 小时）；AFD-004（展示粒度 / 匿名策略，待决策 #3~#6）。

### WAVE-20260804-05 — AFD-003 只读缓存层（Redis 缓存，不写 SQLite）

- 日期：2026-08-04
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：AFD-003
- 状态变化：AFD-003 `todo` -> `done`
- 改动：`ohmywod/afdian.py` 加 `get_sponsors()`（复用 `extensions.cache_get/cache_set`）：命中 `fresh` 直接返回；miss 拉取并回填 `fresh`（TTL）+ `last_good`（长存 7 天）；源站故障降级到 `last_good`、无则 `[]`，只 `logger.warning`、绝不抛错；未配置→`[]`。`config.py` 加 `AFDIAN_CACHE_TTL=3600`（可覆盖）。`tests/test_afdian.py` 加 4 项（共 13）。未写 SQLite、无 model/migration、不进 DR 链。
- 关键取舍：TTL 用计划预先认可的 1h 缺省（`AFDIAN_CACHE_TTL` 可调），不再单独等用户拍板即可推进。双键设计（`fresh` 短 TTL + `last_good` 长存）实现"源站抖动降级到上次结果而非空墙"，比单键更稳。缓存逻辑放 `afdian.py` 而非视图层，展示层（AFD-004）只调 `get_sponsors()`。
- 验证：`tests/test_afdian.py` 13 项全绿（未配置→空、miss→拉取+回填、二次命中不再拉取、故障→`last_good`、故障且无缓存→空）；缓存后端无关（测试 `simple`，生产 `RedisCache`）。
- 发生的问题：无
- 剩余风险：真实赞助者数据的字段形状未见实样（账号当前 0 赞助者），影响 AFD-004 展示映射而非缓存机制；生产真实 Redis 命中未用真数据观测（机制已由测试覆盖）。
- 下一步：仅剩 AFD-004（展示 + 隐私）——需你定待决策 #3~#6（昵称/档位、是否展金额、匿名默认、是否按档位过滤、独立页还是并入支持页）。

### WAVE-20260804-06 — AFD-004 独立赞助者致谢页（仅昵称，隐私优先）

- 日期：2026-08-04
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：AFD-004（Wave 2 收尾）
- 状态变化：AFD-004 `assessing` -> `done`
- 改动：`ohmywod/afdian.py` 加 `sponsor_display_names()`（隐私优先：仅 `user.name`、空/缺失/畸形→`ANONYMOUS_NAME`"匿名支持者"）；`ohmywod/views/frontend.py` 加 `GET /thanks`；新增模板 `ohmywod/templates/thanks.html`（昵称 chip 墙 + 空态 + 克制文案）；`landing.html` 支持面板加致谢页入口链接；`custom.css` 加 `.sponsor-wall`/`.sponsor-chip`/`.sponsor-empty`/`.sponsor-note`/`.donate-thanks-link`。未写 SQLite、未新增路由外副作用。
- 关键取舍：按用户决策——**仅昵称**（不显档位/金额，最克制、隐私风险最低，对齐 SUP-006 与 maintenance-support-plan"不显精确金额"）；**显示昵称、匿名/缺失归"匿名支持者"**；**独立致谢页** `/thanks`（而非支持页区块），并从首页支持面板给入口。#5 不做档位过滤，展示全部发电者。第三方昵称靠 Jinja autoescape 防 XSS（加断言守回归）。
- 验证：`tests/test_afdian.py` 加 4 项（映射+匿名化、空、`/thanks` 空态 200、`/thanks` 列表且 `<script>` 被转义），共 17 项；全仓 129 项测试全绿；真实 Flask 路由渲染 `/thanks` 出正确 chip（`Alice`/`匿名支持者`/`梦想家`）与首页入口链接。
- 发生的问题：无
- 剩余风险：真实浏览器小屏 / 纯暗色观感未人工验收；账号当前 0 赞助者→线上先空态（非缺陷）；`user.name` 真实字段路径若与预期不符需在有数据时微调（已对畸形条目容错）。整个 Wave 2 改动仍在分支 `afdian-wave2`（app）/`afdian-wave2`（ops），未 push、未部署。
- 下一步：Wave 2（AFD-001~004）全部 `done`，爱发电"用起来了"。待你：①是否 push 两个分支并部署（app 分支 + ops 已含凭据字段渲染）；②部署后人工验收 `/thanks` 小屏视觉；③账号有赞助者后核 `user.name` 实样。

### WAVE-20260804-07 — /thanks 增加"取消广告、转向自愿赞助"说明段

- 日期：2026-08-04
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：AFD-004（/thanks 页文案）
- 状态变化：无（AFD-004 保持 `done`；纯文案增补）
- 改动：`ohmywod/templates/thanks.html` 在赞助者墙下新增一节"为什么这儿没有广告"，讲 AdSense 实验受挫（小众中文 WoD 访客 + "众所周知的原因"[GFW]致 Google 广告在墙内加载不良、覆盖率长期个位数百分比、收入与维护开销不成比例、且带来第三方脚本/布局/政策维护负担）、**彻底取消 AdSense 全面下线广告**、转向**自愿赞助**的决定；语气按用户要求走**第一人称、随性口语**，不用"我们"、不强调"免费"（只轻点"站照常用、赞助随意换不来特别待遇、不打扰"）。事实以 maintenance-support-plan §1.1/§1.3 与 SUP-001/002 为准，克制对齐 SUP-004/006（不施压、不暗示回报）。
- 关键取舍：只用"覆盖率个位数百分比"这类广告表现事实，**不写具体金额或成本比例**（SUP-005 是否公开成本口径仍 `assessing`，不越权披露）。放在致谢墙之后作为"为什么"背景，致谢仍是页面主角。作为纯个人兴趣项目用单数第一人称叙述。
- 验证：本地 dev 服务器 `GET /thanks` 200，新段四句关键文案实测渲染；`tests/test_afdian.py` 17 项全绿（空态/列表/转义断言不受影响）。
- 发生的问题：无
- 剩余风险：真实浏览器小屏观感未人工验收；该段属公开对外表态，用户可自行删改措辞。
- 下一步：随 `/thanks` 一起部署即可对外可见；如需也在 maintenance-support-plan 记一笔，可加一条对应 SUP changelog。

### WAVE-20260804-08 — 致谢页接入爱发电自定义显示名口径

- 日期：2026-08-04
- Drive AI：Codex
- Review AI：`unassigned`
- 关联事项：AFD-004（赞助者墙展示与隐私 / 授权）
- 状态变化：AFD-004 保持 `done`；展示口径更新
- 改动：用户在爱发电赞助方案中新增自定义字段“致谢页显示名（可选）”（说明：“自定义留名，留空用昵称。匿名请填“匿名””）。app 侧 `ohmywod/afdian.py` 新增 `query-order` 只读读取：`query-sponsor` 负责当前赞助者列表，`query-order` 的 `remark` 负责按 `user_private_id` 映射“致谢页显示名（可选）”；字段留空回落爱发电昵称；字段为“匿名”时显示“匿名支持者”；仍不展示金额、档位、头像、`user_id` 或订单信息，Redis 只缓存最小显示名映射、不缓存完整订单。`ohmywod/templates/thanks.html` 同步更新页面说明。`tests/test_afdian.py` 增加自定义留名、匿名、留空回落、`remark` 文本解析、订单映射与最小缓存覆盖。
- 关键取舍：真实实调确认 `query-sponsor` 只返回 `user/current_plan/sponsor_plans/amount/time` 等信息，不含自定义字段；`query-order` 返回的订单 `remark` 字段包含用户填写的显示名。因此采用“双源只读”：赞助者资格以 `query-sponsor` 为准，显示名覆盖以 `query-order.remark` 为准。继续不写 SQLite，不保存本地支持者名单或完整订单。
- 验证：`tests/test_afdian.py` 覆盖自定义字段覆盖昵称、填“匿名”匿名化、留空回落昵称、`remark` 中 `致谢页显示名（可选）：...` 解析、`query-order.remark` 按 `user_private_id` 覆盖赞助者昵称、只缓存最小映射；`tests/test_afdian.py` 25 项全绿；真实 API 实调 `query-sponsor total_count=1` 且不含自定义字段，`query-order remark` 返回“蓓兰妮琪·碎羽”，当前 `sponsor_display_names()` 输出 `["蓓兰妮琪·碎羽"]`。
- 发生的问题：无
- 剩余风险：`query-order.remark` 被用作自定义显示名来源；若未来爱发电把 `remark` 改作其他含义，可能误把普通订单备注显示到致谢页。当前赞助方案只有“致谢页显示名（可选）”这类自定义留名用途，风险可接受。
- 下一步：上线后清理生产 Redis 对应缓存或等待 TTL，使 `/thanks` 读取新的订单显示名映射。
