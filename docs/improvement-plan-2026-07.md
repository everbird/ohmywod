---
document_id: ohmywod-improvement-plan-2026-07
schema_version: 1
document_status: active
source_of_truth_for: "application improvement direction, work item status, and wave changelog"
language: zh-CN
created_at: "2026-07-05"
last_updated: "2026-07-21"
review_commit: "app c0ad327; ops 31105fe; production app d930c6a"
review_worktree: "clean before this documentation wave"
next_item_id: "IMP-010"
---

# 站点改进计划（2026-07）

> 本文是 ohmywod 应用安全、正确性、可发现性、性能和工程质量的工作计划。维护成本支持与 AdSense 去留以 [站点维护成本支持计划](maintenance-support-plan.md) 为准；备份、恢复、存储和温备以 [高可用与灾难恢复计划](ha-plan.md) 为准。
>
> **当前结论：IMP-001 至 IMP-009 已全部完成。应用安全、正确性、SEO、健康检查、SQLite 锁等待、防滥用和最小 CI 都已有实现与验证；生产已启用共享 Redis sitemap cache，并为战报 HTML 增加安全的条件请求。搜索在 11,515 条公开战报下实测 p95 约 11 ms，因此继续使用简单 LIKE，不引入 FTS；后续只在达到已记录阈值时重新评估性能设计。跨仓主线继续由 HA/DR 计划维护。**

## 1. 边界、现状与原则

### 1.1 本文负责什么

- 记录应用层改进的稳定 ID、优先级、状态、完成判断和执行证据。
- 覆盖 Flask 路由、模板、数据访问、测试和 CI。
- 不重复记录 HA/DR、生产恢复或维护成本支持事项；跨计划只写依赖关系。
- 不把纯粹“有空清理”的想法包装成必须完成的路线；低优先级事项要有触发条件。

### 1.2 2026-07-21 当前实现

| 方向 | 当前状态 | 代码 / 生产证据 |
|---|---|---|
| 上传 HTML 隔离 | 已完成 | `report_raw` 返回 CSP sandbox，且没有 `allow-same-origin`；已有回归测试 |
| 500 与数据漂移 | 已完成 | `new_category` 要求登录；缺失 report 返回 404；点赞/收藏只在状态实际变化时更新计数；404/500 页面和异常日志已落地 |
| SQLite 配套 | 已完成 | 生产数据库为 WAL 且 integrity check 为 `ok`；生产有效 `SQLALCHEMY_ENGINE_OPTIONS` 已为 `{'connect_args': {'timeout': 5}}`，5 秒锁等待生效（IMP-003，ops `30b4848`，2026-07-21 部署并只读复核） |
| SEO | 已完成 | report meta/OG、页面 title、`sitemap.xml` 和 robots 引用已落地并有测试；sitemap 使用共享 Redis cache，内容变更会主动失效 |
| 运维探针 | 已完成 | `/healthz` 检查 SQLite、Redis 和 `/mnt/jfs/reports`；生产经 Cloudflare 返回 200 |
| 存储语义 | 已收敛到 HA-002 | app 只把 `/mnt/jfs/reports` 视为战报持久层；本地只保留上传 staging |
| 防滥用 | 已完成 | 登录/注册/反馈/互动写端点均由 Flask-Limiter 限流（`client_ip_key` + redis-cache + fail-open）并已上线；注册有蜜罐（IMP-006，生产 `c8fc8cd`） |
| CI | 已完成 | GitHub Actions 在 PR、main push 和手工触发时用 Python 3.12 执行 changed-lines whitespace check 与完整 pytest；首次两次 main run 均成功 |
| 应用与战报缓存 | 已完成 | 生产 `CACHE_TYPE=RedisCache`；sitemap 首次生成 0.776 s、命中 0.084 s；`report_raw` 使用 weak ETag + `private, no-cache`，304 保留 CSP sandbox |
| 搜索 | 已完成当前决策 | 11,515 条公开 report 的真实形状 LIKE 查询 p50 6.97 ms、p95 11.03 ms；继续 LIKE，FTS 暂不成立，重复 model query helper 已删除 |

### 1.3 已拍板的原则

1. 先修可被直接利用的安全问题和会破坏数据正确性的 bug，再做性能与代码整洁。
2. 用户上传 HTML 必须与主站身份隔离；任何兼容修复都不能重新加入 `allow-same-origin`。
3. 防滥用优先使用一个统一的限流设施，不为 login、register、feedback 各引入一套机制。
4. `CF-Connecting-IP` 只有在源站入口被 Cloudflare/防火墙约束时才可作为可信限流 key；该边界由 HA/ops 计划维护。
5. 搜索、缓存和 FTS 先用生产证据证明瓶颈，再增加索引、缓存失效或迁移复杂度。
6. `done` 必须有测试或可复核行为；“代码看起来改了”不算完成。
7. 不在本文重复追踪 AdSense、爱发电、LDAP 退役、Litestream、JuiceFS 或温备。

### 1.4 成功判断

- 已完成事项在当前测试集保持覆盖，生产发布后仍能从代码版本和行为复核。
- 公开写端点有与站点体量匹配、不会误伤正常用户的防滥用保护。
- 每个 PR/主分支变更能自动运行核心测试；失败不会被静默忽略。
- 性能事项只有在记录基线和触发阈值后才实施，避免长期维护无收益的复杂度。
- 本文、维护支持计划和 HA/DR 计划之间没有重复状态真值。

## 2. 这份计划怎么维护

这是个人兴趣项目，不需要 owner、RACI 或复杂产品流程。后续工作通常由一个 AI 工具推进，再由另一个 AI 工具独立检查。涉及用户体验、外部服务或生产发布时，由用户做最后决定。

每个事项有两个可选角色：

- `Drive AI`：调查现状、提出选项、实施改动，并更新本文和 changelog。
- `Review AI`：独立检查安全边界、diff、测试、兼容性和剩余风险。

角色可以写工具名，例如 `Codex` 或 `Claude Code`；尚未分配时写 `unassigned`。

### 2.1 状态枚举

工作项的 `状态` 只能使用以下值：

- `todo`：方向已确认，尚未开始
- `assessing`：需要性能数据、用户选择或实现比较，尚不能直接实施
- `in_progress`：正在调查或实施
- `blocked`：存在明确阻塞；必须写明解除方式
- `done`：完成判断已经满足，并有可复核证据
- `cancelled`：明确决定不做；记录理由和重新考虑的触发条件

### 2.2 更新规则

1. 每个 `IMP-NNN` ID 永久不变、不可复用。新增事项使用 front matter 的 `next_item_id`，并同步递增。
2. 开始工作前先读本文和 `git status`，保留用户或其他工具的未提交改动。
3. `状态` 是事项主真值。状态变化、代码改动、测试和 changelog 放在同一波变更里。
4. `done` 需要可复核证据；只更新本文、只加依赖或只完成 happy path 不算完成。
5. `blocked` 要说明卡在哪里、怎样解除。`cancelled` 要说明理由和重新考虑的触发条件。
6. 事项明显扩大时拆新 ID；不要把所有“顺手清理”塞进一个永不结束的事项。
7. 涉及生产发布、站外账号或外部服务配置时先由用户确认；本文不构成生产执行授权。
8. 生产证据不得包含账号、token、口令、用户内容或其他个人信息。
9. 每波改动在文末按时间正序追加 changelog。旧记录不重写，纠错时追加 correction wave。
10. 每次变更更新 front matter 的 `last_updated`。

### 2.3 固定工作项格式

新增事项使用同一套结构：

- 元信息：`状态`、`优先级`、`波次`、`Drive AI`、`Review AI`、`依赖`、`最后更新`、`结论置信度`
- 内容：`问题与影响`、`证据`、`方向与要点`、`完成判断`、`Review 关注`、`执行证据`

优先级定义：

- `P0`：可直接利用的安全问题、数据损坏或广泛不可用
- `P1`：显著影响正确性、防滥用、可回归性或用户查找价值
- `P2`：性能、维护性或只有达到触发阈值才值得做的优化

## 3. 建议推进顺序

### 历史基线：保住已经完成的改进

范围：IMP-001、IMP-002、IMP-004、IMP-005。

方向：这些事项已经部署。后续工作是维持回归测试和安全边界，不重复实施，也不因重写计划丢失完成证据。

### Wave 0：先关闭配置漂移，再补公开写端点的防滥用

范围：IMP-003、IMP-006。

方向：本波作为 HA-008 的应用侧并行支线。SQLite timeout 可在删除 ops LDAP 配置时同步到生产模板；限流先覆盖即将切到 SQLite 认证的 login、register，再覆盖 feedback 和可重放的互动 POST，并与 Cloudflare 入口信任边界一起 review。

### Wave 1：让现有测试自动执行

范围：IMP-007。

方向：已建立最小 CI，只跑项目已有测试与必要 whitespace check；不同时引入复杂矩阵、发布流水线或 coverage threshold。

### Wave 2：按证据做性能与清理

范围：IMP-008、IMP-009。

方向：生产基线已记录。sitemap 与 raw conditional GET 有明确收益并已实施；搜索未达到阈值，维持 LIKE。只有搜索 p95 连续三次基线达到 100 ms、出现明确用户侧慢查询，或数据量跨过 50,000 / 100,000 两个复测点时，才重新评估 FTS。

## 4. 工作项

### IMP-001 — 隔离同源直出的用户上传 HTML

- 状态：`done`
- 优先级：`P0`
- 波次：历史基线
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-18
- 结论置信度：`confirmed`

问题与影响：`report_raw` 会把用户 zip 中的 HTML 原样以主域名 `text/html` 返回。没有隔离时，上传者可以获得同源脚本执行能力。

证据：`ohmywod/views/report.py` 在 raw 响应上设置 `Content-Security-Policy: sandbox allow-scripts allow-popups`；测试明确断言没有 `allow-same-origin`。阅读模式状态通过 `postMessage` beacon 兼容。

方向与要点：保留 WoD 报告脚本和 popup 能力，但永远不恢复同源身份；需要新增 `allow-forms` 等权限时单独评估。

完成判断：上传 HTML 的脚本不能读取主站 cookie/localStorage 或以主站身份发同源请求；旧战报 tooltip、页内跳转和阅读模式可用。

Review 关注：CSP header 被 nginx/CDN 覆盖、添加 `allow-same-origin`、父子窗口消息未校验来源或内容。

执行证据：`60c9b71`、`34c242d`、`8bc8dbb`；已包含在生产 `0512c83`。

### IMP-002 — 修复常见 500、计数漂移与不可诊断异常

- 状态：`done`
- 优先级：`P1`
- 波次：历史基线
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-18
- 结论置信度：`confirmed`

问题与影响：匿名创建分类、缺失 report、重复点赞/取消和吞异常会分别造成 500、计数漂移或无法排障。

证据：`new_category` 已加 `@login_required`；详情和 reader 在访问属性前检查 report；Redis `sadd`/`srem` 或收藏状态实际变化后才更新计数；`load_user` 等异常写结构化日志；404/500 handler 已落地。

方向与要点：保持写端点幂等语义；新增互动操作时先定义重复提交结果。

完成判断：已识别的 500 返回登录跳转或 404；重复互动不改变计数；关键异常进入应用日志；用户看到站点风格错误页。

Review 关注：取消操作把计数降为负数、异常 handler 自身依赖已故障的数据库或模板扩展。

执行证据：`ee96a7c`、`8bc8dbb`；已包含在生产 `0512c83`。

### IMP-003 — 让 SQLite 锁等待在生产全量配置中真正生效

- 状态：`done`
- 优先级：`P1`
- 波次：Wave 0
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-003
- 最后更新：2026-07-21
- 结论置信度：`confirmed`

问题与影响：多 gunicorn worker、SQLite 写入和 Litestream 持续读取并存时，默认锁等待容易把短暂竞争变成 `database is locked`。公共 app 配置已经修复，但生产使用的全量配置类没有继承该值。

证据：app `DefaultConfig.SQLALCHEMY_ENGINE_OPTIONS.connect_args.timeout` 为 5 秒，无效的 gunicorn `debug` 已删除；但 ops 的 `ohmywod_local_config.py.j2` 没有 `SQLALCHEMY_ENGINE_OPTIONS`。2026-07-18 生产只读实例化 Flask 后，有效值为 `{}`。生产数据库本身处于 WAL，integrity check 为 `ok`。

方向与要点：把 timeout 同步到 ops 全量模板和 Molecule 断言，部署前后分别检查 Flask 有效配置；同时评估全量替换类是否继续可接受。WAL 与备份归 HA-003。若生效后仍出现锁错误，再根据日志评估事务范围。

完成判断：app 默认配置、ops 渲染模板和生产有效配置都包含相同的 5 秒锁等待；Molecule / 应用测试和部署后只读检查通过，正常写路径没有回归。

Review 关注：不同配置类或 ops 渲染的全量 `local_config.py` 覆盖掉默认 engine options。

执行证据：app 侧 `8fb058e` 已完成；ops 侧 `ohmywod_local_config.py.j2` 独立全量类补齐 `SQLALCHEMY_ENGINE_OPTIONS`（connect_args timeout=5，与 app config.py 同值）并加 Molecule 断言（ops `30b4848`，molecule test 全绿）；2026-07-21 经 `ansible-playbook site.yml --tags app` 只渲染 local_config + 重启 web 部署到生产（仅 2 处 changed，未触碰其它 role）。部署后 SSH 只读实例化 Flask，有效值为 `{'connect_args': {'timeout': 5}}`（此前为 `{}`）；healthz 200（db/redis/storage 均 ok）、首页 200，无写路径回归。三处（app 默认、ops 模板、生产有效）现一致，本项 `done`。

### IMP-004 — 改善公开战报的搜索引擎可发现性

- 状态：`done`
- 优先级：`P1`
- 波次：历史基线
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-18
- 结论置信度：`confirmed`

问题与影响：公开战报已有副本、服务器、职业等结构化信息，但旧页面缺 meta description、Open Graph、独立 title 和 sitemap。

证据：report details 已有 description/OG；分类、搜索、reader 有页面 title；`/sitemap.xml` 输出公开 report/category；robots 指向 sitemap；测试覆盖删除战报排除逻辑。代码尝试缓存一小时，但生产未启用 Flask-Caching，此性能缺口归 IMP-008，不影响 sitemap 正确性。

方向与要点：SEO 服务于中文 WoD 玩家查找战报，不与广告流量或收入目标绑定。页面级细节只有在搜索结果确有问题时继续补。

完成判断：公开可索引页面有准确 title/description；sitemap 可访问且不包含软删除 report；robots 引用正确 URL。

Review 关注：用户描述未转义、私有/删除内容进入 sitemap、canonical 或 OG URL 指向错误 host。

执行证据：`53101a2`；已包含在生产 `0512c83`。

### IMP-005 — 建立依赖真实数据面的健康检查

- 状态：`done`
- 优先级：`P1`
- 波次：历史基线
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-002、HA-003
- 最后更新：2026-07-18
- 结论置信度：`confirmed`

问题与影响：首页 200 不能证明 SQLite、Redis 或 JuiceFS 正常；挂载掉线时旧监控可能继续报绿。

证据：`/healthz` 执行 SQLite `SELECT 1`、Redis `PING` 并检查 `/mnt/jfs/reports` 可读；任一失败返回 503。生产公开 endpoint 2026-07-18 经 Cloudflare 返回 200，JSON 三类检查均为 `ok`。

方向与要点：保持 endpoint 轻量、无敏感信息，供外部监控和未来切换脚本复用。备份新鲜度不塞进请求路径，归 HA-007 的独立 timer。

完成判断：数据面故障会让 endpoint 返回非 200；正常请求不执行昂贵扫描；响应不泄露凭据或内部异常。

Review 关注：只检查目录存在却命中未挂载底层目录；HA-005 需要从服务依赖层解决这一边界。

执行证据：`8fb058e`、`0512c83`；生产只读复核日期 2026-07-18。

### IMP-006 — 为登录、注册、反馈和互动写端点增加防滥用保护

- 状态：`done`（登录/注册随 HA-008 slice-2 `c91c7f3` 上线；feedback、like/favorite 随 `c8fc8cd` 上线，2026-07-21 部署并只读复核）
- 优先级：`P1`
- 波次：Wave 0
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-001；登录/注册切片与 HA-008 同波
- 最后更新：2026-07-21
- 结论置信度：`recommended`

问题与影响：开放注册、登录、反馈和多个互动 POST 没有速率限制，容易被爆破、spam 或简单重放消耗资源。

证据：当前 requirements 和应用初始化没有 Flask-Limiter；注册表单无蜜罐。Cloud Firewall 已把源站 80/443 收窄到 Cloudflare IP 段，为可信读取 `CF-Connecting-IP` 提供入口边界。

方向与要点：统一引入 Flask-Limiter，存储复用 redis-cache；先配合 HA-008 为 SQLite 认证后的 login、register 定义 IP 和用户名/账号双维度限制，再扩到 feedback、like/favorite。注册加不打扰真人的蜜罐。限值先保守并记录命中日志，不引入 CAPTCHA。

完成判断：目标端点超过阈值返回一致 429；正常用户、测试和反向代理场景不受影响；伪造转发头不能绕过或误伤；Redis 降级行为明确。

Review 关注：key 函数信任任意客户端 header、IPv6/缺 header、登录用户名枚举、限流存储故障导致全站失败。

执行证据（登录/注册切片，2026-07-21，Claude Code；app 分支 `ha-008-sqlite-user-schema`，未部署）：引入 `Flask-Limiter`，key 函数信任 `CF-Connecting-IP`（源站已被 Cloud Firewall 收窄到 Cloudflare 段）、缺失时回退 socket peer；`login` 加 IP（10/分、60/时）与用户名（6/分）双维度限制，`register` 加 IP（5/分、30/时）限制；仅这两个端点被装饰，其它端点不受影响。存储复用运行中的 redis-cache（`redis://localhost:7379/0`，测试用 `memory://`），`RATELIMIT_SWALLOW_ERRORS` + in-memory fallback 实现**存储故障 fail-open**（不 500 全站）。注册加隐藏蜜罐字段 `website`（真人不受扰，机器人填了即静默丢弃并记日志）；统一 `429` 页与命中告警日志。本地 `pytest` 58 通过（新增 `tests/test_ratelimit.py` 5 项：CF-IP key、登录/注册触发 429、蜜罐静默丢弃、正常注册不受影响）。未做：feedback、like/favorite 限流；生产部署随 HA-008 第二切片一起（切换 runbook 已含装 `Flask-Limiter`）。

执行证据（feedback + like/favorite 切片，2026-07-21，Claude Code / Opus 4.8；app 分支 `main`，已本地提交未部署）：复用同一 `limiter`（`client_ip_key` + redis-cache 存储，fail-open 与登录/注册切片同一套）。`feedback` 开放写端点加 IP 限制 `5/分、20/时`（`methods=["POST"]`，GET 看表单不受影响）；四个已登录互动写端点 `like`/`unlike`/`add_favorite`/`cancel_favorite` 各加共享常量 `_INTERACTION_LIMIT = "20/分、200/时"`，装饰器置于 `@login_required` **之外**（未登录洪泛也计数），计数器本就靠集合成员幂等、限流只约束请求量。命中走同一 `429` 页 + 告警日志（app.py 现成 handler）。新增测试 3 项（feedback 触发 429、互动端点 22 次触发 429、阈值内 5 次不误伤）；本地 `pytest` 61 项全过，`git diff --check` 干净。已部署（2026-07-21）：push app `main`（`c8fc8cd`）→ ops bump `app_ref`（`dbd86e1`）→ `ansible-playbook site.yml --tags app`（仅 2 处 changed：checkout `c91c7f3`→`c8fc8cd` + 重启 web）。部署后只读复核：生产 checkout = `c8fc8cd`、五个限流装饰器均在位、`SQLALCHEMY_ENGINE_OPTIONS` 仍为 `{'connect_args': {'timeout': 5}}`（IMP-003 无回归）、healthz 200、首页 200、feedback GET 200（表单不被 POST 限流误伤）。IMP-006 全部四类端点均已限流上线，本项 `done`。

### IMP-007 — 建立最小 CI 回归门槛

- 状态：`done`
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`Codex`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-21
- 结论置信度：`confirmed`

问题与影响：仓库已有覆盖安全、认证、错误处理、健康检查和 SEO 的测试，但没有自动 workflow；这些边界只能依赖本地手工运行。

证据：实施前 `.github/workflows/` 不存在；本地 `make test` 是唯一入口。实施后 `.github/workflows/tests.yml` 已进入 main。

方向与要点：从单 Python 版本、依赖安装、`pytest` 和 `git diff --check` 开始。先确保稳定，再考虑缓存、版本矩阵、coverage threshold 或自动发布。

完成判断：PR 和 main push 自动运行核心测试；失败阻止合并或至少清楚可见；workflow 不需要生产密钥、LDAP 或真实 JuiceFS。

Review 关注：测试依赖 Redis/文件路径的隔离、未固定依赖导致漂移、CI 绿但跳过关键测试。

执行证据：app `d930c6a` 新增单 Python 3.12 GitHub Actions workflow，触发面为 PR、main push 和手工运行；使用 `actions/checkout@v4`、`actions/setup-python@v5`、pip cache、锁定的 `requirements.txt`，执行变更范围 `git diff --check` 与完整 `pytest tests/ --cov=ohmywod -v`。workflow 不读取生产密钥、不连接真实 Redis/JuiceFS。实现波本地 67 项测试通过；GitHub main push run [#1](https://github.com/everbird/ohmywod/actions/runs/29889859526) 与 [#2](https://github.com/everbird/ohmywod/actions/runs/29890051929) 均为 `success`。

### IMP-008 — 为 sitemap 与不可变战报建立有意的缓存策略

- 状态：`done`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`Codex`
- Review AI：`unassigned`
- 依赖：HA-002
- 最后更新：2026-07-21
- 结论置信度：`confirmed by production measurement`

问题与影响：生产没有配置 `CACHE_TYPE`，Flask-Caching 实际处于 null 模式，因此 sitemap 的一小时缓存调用无效；`report_raw` 也会在每次请求从 JuiceFS 读取完整 HTML、替换 `http:` 并追加 reader beacon。

证据：实施前生产有效 `CACHE_TYPE=None`，Redis 无 `flask_cache_sitemap_xml`；11,515 条公开 report / 522 个公开 category 下，每次 sitemap 生成 1.17 MiB，p50 929 ms、最慢 1,451 ms。80 个真实 raw 样本大小 p50 18.6 KiB、p95 293 KiB；40 个样本的 JuiceFS 读取加文本变换 p50 18.4 ms、p95 62.9 ms。

方向与要点：先决定站内派生数据是否使用 redis-cache 或简单进程缓存，并让 sitemap 的缓存行为可测试、可观测。对 raw 报告先测大小与延迟；若值得做，优先 conditional GET。必须保证更新/删除不会长期返回旧内容，且 CSP 在 304/缓存响应上仍存在。

完成判断：生产缓存配置是显式选择，不再静默 null；sitemap 不会每次遍历全量数据；若增加 raw 缓存，重复读取显著减少且更新、删除、权限、CSP 与失效行为有测试。

Review 关注：弱/强 ETag 计算成本、CDN 缓存用户内容、reader beacon 随代码变化、304 丢安全 header。

执行证据：app `d930c6a` 与 ops `31105fe`：app 默认、生成模板和生产 full replacement config 都显式使用 redis-cache 7379 db 0，并以 `flask_cache_` 隔离 key；cache get/set/delete 失败时 fail-open，不把 Redis cache 变成页面或已提交写操作的新硬依赖。sitemap 保持 1 小时共享缓存，report/category 创建、更新、删除后主动失效；测试覆盖填充、失效、删除和 cache 故障降级。`report_raw` 使用文件 mtime/size + beacon version 的 weak ETag，`private, no-cache` 允许浏览器保存但每次重验证，不让 CDN 共享用户 HTML；匹配时 stat 后直接 304、不读取正文，304 继续带 CSP sandbox。生产部署后首次 sitemap 200 / 1,255,311 bytes / 0.776 s，第二次 200 / 同大小 / 0.084 s，Redis key 存在且 TTL=3600；真实 raw 验收为 200→304、第二次 0 bytes、ETag 为 weak、CSP 有 sandbox 且无 `allow-same-origin`；healthz 200。

### IMP-009 — 为搜索性能定义触发阈值并清理重复实现

- 状态：`done`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`Codex`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-21
- 结论置信度：`confirmed no FTS needed at current scale`

问题与影响：真实搜索使用 `%q%` LIKE，数据增长后会全表扫；`ReportQuery.search` 与 controller 搜索并存，容易让维护者改错入口。

证据：生产 2026-07-21 有 11,515 条公开 report。按真实 controller 形状对从现有标题抽取的 23 个双字符样本分别执行 count + 首 20 条查询，p50 6.97 ms、p95 11.03 ms、最大 12.86 ms；`EXPLAIN QUERY PLAN` 确认仍是 `SCAN report`，但当前规模没有性能问题。全仓引用确认真实路由只调用 `ReportController.search`；`ReportQuery` / `ReportCategoryQuery` 未被 model 配置或调用。

方向与要点：当前继续 LIKE。以后在公开 report 达到 50,000 和 100,000 时各复测；任意规模下若相同方法的 p95 连续三次达到 100 ms，或出现明确用户侧慢查询，再评估 SQLite FTS5。FTS 实施前必须单独验证中文 tokenization、索引更新/删除和回退。

完成判断：已记录继续 LIKE 或迁入 FTS5 的依据；若迁移，索引构建、更新、中文分词边界和回退有测试；若不迁移，重复死代码已安全处理。

Review 关注：FTS tokenization 对中文内容的实际价值、索引与软删除同步、把小数据集简单查询过度工程化。

执行证据：app `d930c6a` 删除完全未接线的 `ReportQuery`、`ReportCategoryQuery` 及相关旧 imports，保留唯一真实实现 `ReportController.search`；新增测试覆盖 display name、description、软删除过滤和 `show_deleted=True`。生产发布后 `/r/search?q=ab` 返回 200。基于上述 11 ms p95 明确不引入 FTS，本项以“测量、阈值、死代码清理”完成。

## 5. 跨计划归属

| 主题 | 唯一状态真值 | 本文处理方式 |
|---|---|---|
| AdSense 文案、脚本和支持入口 | `maintenance-support-plan.md` SUP-001 至 SUP-006 | 不重复建 IMP；线上 2026-07-18 仍存在，按 SUP 推进 |
| 存储归一化 | `ha-plan.md` HA-002 | 仅在 IMP-005 / IMP-008 记录应用依赖 |
| WAL、Litestream 和恢复 | `ha-plan.md` HA-003 至 HA-007 | IMP-003 只负责应用锁等待及配置同步 |
| LDAP 退役、SQLite 密码和 session | `ha-plan.md` HA-008；ops 清理由 `ops-review-plan.md` OPS-015 跟踪 | IMP-006 只维护限流状态；登录/注册切片与 HA-008 同波，不重复认证迁移状态 |
| 温备和切换 | `ha-plan.md` HA-009、HA-010 | `/healthz` 作为可复用探针 |

## 6. 明确不做

- 不把 SEO 与广告流量、RPM 或收入目标绑定。
- 不为没有性能证据的 13k 级数据立即引入 Elasticsearch、PostgreSQL 或外部搜索服务。
- 不在第一版 CI 同时建设多 Python 矩阵、自动部署、复杂 coverage gate 或生产集成测试。
- 不用 CAPTCHA 作为防滥用第一步；轻量限流和蜜罐不足时再评估。
- 不通过移除 CSP sandbox 来修复旧战报兼容问题。
- 不把备份新鲜度、云 API 检查等慢操作放进同步 `/healthz`。
- 不在本计划重复维护 AdSense、爱发电、恢复 runbook 或 HA 拓扑状态。

## 7. Changelog（append-only，旧 -> 新）

> 每波改动在本节末尾追加。不得改写旧记录；旧版文档在引入 changelog 前的历史仍可从 Git 追溯。

### Changelog 条目模板

```markdown
### WAVE-YYYYMMDD-NN — 简短标题

- 日期：YYYY-MM-DD
- Drive AI：工具名称；未使用则写“无”
- Review AI：工具名称；尚未 review 则写 `unassigned`
- 关联事项：IMP-NNN, IMP-NNN
- 状态变化：例如 IMP-006 `todo` -> `in_progress` -> `done`
- 改动：代码、模板、测试或文档摘要
- 关键取舍：选择和理由；无则写“无”
- 验证：检查、测试或生产只读证据摘要
- 发生的问题：无则写“无”
- 剩余风险：本波未解决的内容
- 下一步：下一事项或需要用户决定的问题
```

### WAVE-20260718-01 — 按实现重建站点改进计划真值

- 日期：2026-07-18
- Drive AI：Codex
- Review AI：`unassigned`
- 关联事项：创建 IMP-001 至 IMP-009
- 状态变化：确认 IMP-001、IMP-002、IMP-004、IMP-005 `done`；确认 IMP-003、IMP-006、IMP-007 `todo`；新增 IMP-008、IMP-009 `assessing`
- 改动：以维护支持计划的 front matter、稳定 ID、固定状态、完成证据和 append-only changelog 结构重写本文；删除旧文档中已落地却仍像未来方案的描述；把存储、LDAP、HA 和 AdSense 状态分别归回对应计划
- 关键取舍：先关闭生产全量配置覆盖 app 默认值的漂移，再推进防滥用和最小 CI；缓存与 FTS 必须先有实测，不因“看起来是最佳实践”直接实施
- 验证：核对 app `0f52bf9`、ops `5988138`、生产 app `0512c83`；检查 CSP、认证装饰器、404、幂等计数、错误 handler、SQLite timeout、SEO、sitemap、`/healthz`、测试目录和 CI 缺失；2026-07-18 SSH 只读确认生产 WAL、integrity、report 数量、JuiceFS 路径、公开 `/healthz` 和有效 Flask 配置；确认生产 timeout 未生效且 app cache 为 null；本地 `pytest` 39 项通过；未修改生产
- 发生的问题：线上仍加载 AdSense 并展示“偶尔点点网站左下角的广告”，但该问题已有 SUP-001 / SUP-002，因此没有在本文重复建项
- 剩余风险：生产 SQLite timeout 未生效；公开写端点仍无限流；仓库测试仍无自动 CI；缓存与搜索性能尚无基线
- 下一步：先执行 IMP-003，把 app 默认配置与 ops 全量模板同步并验证生产有效值，再执行 IMP-006

### WAVE-20260721-01 — 配合 LDAP-first 主线调整应用事项顺序

- 日期：2026-07-21
- Drive AI：Codex
- Review AI：`unassigned`
- 关联事项：IMP-003、IMP-006、IMP-007；跨计划 HA-008
- 状态变化：无；IMP-003、IMP-006、IMP-007 保持 `todo`
- 改动：明确认证迁移状态只由 HA-008 维护；IMP-006 的 login / register 限流成为 HA-008 上线 gate，其他写端点随后完成；IMP-007 尽量在认证测试重写前建立最小 CI；IMP-003 与 ops LDAP 配置清理并行收敛
- 关键取舍：不新增重复的 IMP 身份迁移事项；HA-008 负责用户、密码、session 和迁移/回退，IMP-006 只负责防滥用
- 验证：只读核对当前 `LDAPLoginForm`、LDAP manager、LDAP mock、注册/profile 写路径、`User` 模型和现有测试；本波只更新计划，没有修改应用或生产
- 发生的问题：无
- 剩余风险：认证迁移尚未开始，现有测试仍以 mock LDAP 为基础，仓库也尚无 CI
- 下一步：主线执行 HA-008；可并行先做 IMP-007，随后把 IMP-006 的登录/注册限流纳入 HA-008 上线验收

### WAVE-20260721-02 — IMP-003 生产锁等待收敛并部署

- 日期：2026-07-21
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：IMP-003；跨仓 `ohmywod-ops` app role
- 状态变化：IMP-003 `todo` -> `done`
- 改动：ops `ohmywod_local_config.py.j2` 独立全量类补 `SQLALCHEMY_ENGINE_OPTIONS`（connect_args timeout=5，与 app config.py 同值）并注释说明为何该类必须显式携带该键；app role molecule verify 增加断言（渲染出的 local_config 必含 engine options + `"timeout": 5`），防止该值再次静默丢失（ops `30b4848`）。app 代码本波无改动（config.py 早在 `8fb058e` 已含该值）。
- 关键取舍：不把独立全量类改成继承式（会连带改变 ALLOWED_EXTENSIONS / 缺 FLASK_ADMIN_SWATCH 等线上真实差异），只就地复制该键；部署用 `--tags app` 单独收敛 app role，刻意不触碰生产上与本项无关、尚未同步的 OPS-003 juicefs/nginx systemd 挂载闸门漂移（避免重启 JuiceFS/nginx）。
- 验证：molecule test 全绿（含新断言、幂等第二次 converge `changed=0`）；`ansible-playbook site.yml --tags app --diff` 真跑仅 2 处 changed（渲染 local_config + 重启 web），checkout 因 `app_ref` 未变而跳过；部署后 SSH 只读实例化 Flask，有效 `SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'timeout': 5}}`（此前 `{}`）；公开 healthz 200（db/redis/storage 均 ok）、首页 200，无写路径回归。
- 发生的问题：无（PowerShell→wsl→ssh 内联引号转义首次导致空输出，改用脚本文件经 ssh stdin 后正常，不影响结果）。
- 剩余风险：生产与 ops 仓存在与本项无关的 OPS-003 juicefs/nginx systemd 挂载闸门漂移（`site.yml --check` 可见），本波刻意未收敛，需按 OPS-003 单独评估窗口后 apply。
- 下一步：推进 IMP-006 剩余切片（feedback、like/favorite 写端点限流）；IMP-007 最小 CI。

### WAVE-20260721-03 — IMP-006 剩余写端点限流（feedback + 互动）

- 日期：2026-07-21
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：IMP-006
- 状态变化：IMP-006 保持 `in_progress`（登录/注册已在生产；本波补 feedback + like/favorite，已实现+测试，未部署）
- 改动：`feedback` 加 IP 限制 `5/分、20/时`（仅 POST，GET 看表单不受影响）；`like`/`unlike`/`add_favorite`/`cancel_favorite` 四个已登录互动写端点各加共享 `_INTERACTION_LIMIT = "20/分、200/时"`，限流装饰器置于 `@login_required` 外；复用登录/注册切片同一 `limiter`（`client_ip_key` + redis-cache 存储 + fail-open）与 `429` handler。新增 3 项测试。
- 关键取舍：互动端点用 IP 维度 + 宽松阈值（正常浏览不误伤，只挡刷量），不引入 per-user key 以保持与现有 `client_ip_key` 一致；feedback 只加限流不加蜜罐（蜜罐留在 register，避免扩面）；沿用现成 HTML `429` handler，未为 AJAX 端点单独返 JSON（JS 只看状态码）。
- 验证：本地 `pytest` 61 项全过（新增 feedback 触发 429、互动端点 22 次触发 429、阈值内 5 次不误伤）；`git diff --check` 干净。未在生产验证（未部署）。
- 发生的问题：无
- 剩余风险：新端点限流仅在代码+测试层完成，尚未在生产生效；部署需 push app `main` + ops bump `app_ref` + `--tags app`（属外发/生产动作，待用户确认）。
- 下一步：按用户意向决定是否 push + 部署 feedback/like/favorite 切片；随后 IMP-007 最小 CI 把这些回归纳入自动门槛。

### WAVE-20260721-04 — IMP-006 剩余切片上线，IMP-006 `done`

- 日期：2026-07-21
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：IMP-006
- 状态变化：IMP-006 `in_progress` -> `done`
- 改动：用户批准后部署 WAVE-20260721-03 的 feedback + like/favorite 限流：push app `main`（`c8fc8cd`）→ ops `dbd86e1` bump `app_ref` c91c7f3→c8fc8cd → `ansible-playbook site.yml --tags app`（仅 checkout + 重启 web 两处 changed，未触碰其它 role）。
- 关键取舍：沿用 IMP-003 的 `--tags app` 隔离收敛，刻意绕开生产上无关的 OPS-003 juicefs/nginx 挂载闸门漂移（按用户决定暂不收敛）。
- 验证：部署后 SSH 只读复核：生产 checkout = `c8fc8cd`、`report.py` 四个互动端点 + `frontend.py` feedback 限流装饰器均在位、`SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'timeout': 5}}`（IMP-003 无回归）；公开 healthz 200（db/redis/storage 均 ok）、首页 200、feedback GET 200。未在生产主动触发 429（避免造垃圾 feedback 行与日志噪声；限流行为已由 61 项测试覆盖真实请求路径）。
- 发生的问题：无
- 剩余风险：IMP-006 已完成；未决项归其它事项——OPS-003 挂载闸门漂移（本轮记录未收敛）、ops 仓两个提交（`30b4848`、`dbd86e1`）仍在本地未 push。
- 下一步：IMP-007 最小 CI，把认证/限流回归纳入 PR 自动门槛。

### WAVE-20260721-05 — IMP-007 至 IMP-009：CI、共享缓存与搜索决策全部完成

- 日期：2026-07-21
- Drive AI：Codex
- Review AI：`unassigned`
- 关联事项：IMP-007、IMP-008、IMP-009；跨仓生产配置 app `d930c6a` / ops `31105fe`
- 状态变化：IMP-007 `todo` -> `done`；IMP-008 `assessing` -> `done`；IMP-009 `assessing` -> `done`
- 改动：新增最小 GitHub Actions（PR/main/manual，Python 3.12，changed-lines whitespace check + 完整 pytest）；将 app 默认、生成模板和 ops 生产 full replacement config 的 cache 显式收敛为共享 RedisCache，并为 cache 操作增加 fail-open；sitemap 继续缓存 1 小时且在 report/category 内容变更后主动失效；`report_raw` 增加基于文件元数据与 beacon version 的 weak ETag、`private, no-cache` 和不削弱 CSP 的 304；删除未接线的 `ReportQuery` / `ReportCategoryQuery`，保留 controller 唯一搜索实现并补回归测试。
- 关键取舍：sitemap 在生产每次生成接近 1 秒，采用跨 worker 一致的 Redis cache，不用会产生多份状态且失效不一致的进程内 cache；raw 只做浏览器条件请求，不让 CDN 共享缓存用户 HTML；搜索虽为全表扫，但当前 p95 约 11 ms，明确不引入 FTS，并把重新评估 gate 设为 50k/100k 数据量复测或 p95 连续三次达到 100 ms。
- 验证：改动前生产基线：11,515 条公开 report、522 category；sitemap 1.17 MiB，p50 929 ms / 最大 1,451 ms；LIKE count+page 23 样本 p50 6.97 ms / p95 11.03 ms / 最大 12.86 ms；raw 40 样本读取 p50 18.4 ms / p95 62.9 ms。本地 `pytest` 67 项全过、coverage 83%、`git diff --check` 与 compileall 通过；ops `site.yml --syntax-check` 通过。部署 `--tags app` 仅 checkout、渲染 local config、reload web 三处 changed，`failed=0`。部署后生产 app=`d930c6a`、有效 `CACHE_TYPE=RedisCache`；sitemap 冷请求 0.776 s、热请求 0.084 s、TTL=3600；raw 200→304/0 bytes 且 ETag/Cache-Control/CSP 正确；healthz/search 200。GitHub Actions run 29889859526、29890051929 均成功。
- 发生的问题：首次用按 head SHA 的公开 Actions 查询过早返回 0，改查 workflow 自身 runs 后确认首个实现提交的 run 已成功，第二次 main push 同样成功；不影响 CI。
- 剩余风险：Redis cache 与 limiter 共用 7379/db0，但 key prefix 隔离且 cache fail-open；report/category 经 Flask-Admin 直接修改时不走 controller invalidation，最坏保留到 sitemap 1 小时 TTL，自愿接受。FTS 未实施是有基线的明确决定，不代表永不实施。
- 下一步：应用计划 IMP-001 至 IMP-009 已全部完成；后续主线回到 HA-008 收尾与 HA-006 / OPS-004 单机 DR，应用侧仅在新证据或新事项出现时新增 IMP ID。
