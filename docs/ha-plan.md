---
document_id: ohmywod-ha-plan
schema_version: 1
document_status: active
source_of_truth_for: "HA/DR direction, implementation gates, work item status, and wave changelog"
language: zh-CN
created_at: "2026-07-05"
last_updated: "2026-07-18"
review_commit: "app 0f52bf9; ops 5988138; production app 0512c83"
review_worktree: "clean before this documentation wave"
next_item_id: "HA-011"
---

# 高可用与灾难恢复计划

> 本文是 ohmywod 可用性、备份恢复和温备建设方向的工作计划，不是可以直接复制到生产执行的 runbook。具体生产真值和恢复步骤以私有仓库 `ohmywod-ops/docs/recovery.md` 为准，ops 整改细节以 `ohmywod-ops/docs/ops-review-plan.md` 为准。
>
> **当前结论：生产仍是单机。已完成单机加固、SQLite 持续复制、对象存储迁移和战报存储归一化，但冷恢复闭环尚未成立，双机温备也尚未建设。因此当前能力应称为“使用外部对象存储和持续数据库复制的单机部署”，不能称为 HA，也不再宣称 20 分钟可重建。温备仍是目标方向，但必须先关闭恢复顺序、服务依赖和身份恢复缺口。**

## 1. 边界、现状与目标

### 1.1 本文负责什么

- 记录可用性与恢复方向、已拍板架构约束、事项状态和完成证据。
- 维护 `HA-NNN` 级跨仓事项；一个事项可以在 app 和 ops 两个仓库分别落地。
- 不复制生产 IP、bucket、monitor ID、密钥字段和逐条恢复命令；这些真值只放在私有 ops 仓库。
- 不替代 `ohmywod-ops/docs/ops-review-plan.md`。后者负责具体 ops 缺陷，本文负责把它们映射到整体 HA/DR 路线。
- 应用安全、体验和性能改进归 [站点改进计划](improvement-plan-2026-07.md)；维护成本支持归 [站点维护成本支持计划](maintenance-support-plan.md)。

### 1.2 2026-07-18 生产只读盘点

| 能力 | 当前状态 | 证据与边界 |
|---|---|---|
| 计算 | 单台 Linode 1 vCPU / 961 MiB，无私网 IPv4 | Redis `role:master`、`connected_slaves:0`；没有备机 inventory |
| 应用版本 | 生产 `0512c83`，本仓 `0f52bf9` | 生产工作树 `git describe` 为 `v1.7-28-g0512c83` |
| SQLite | WAL，完整性检查通过 | Litestream 0.3.13 active；这只证明持续复制进程运行，不证明冷恢复可用 |
| 战报文件 | 已全部归一到 `/mnt/jfs/reports` | JuiceFS 当前约 104 GiB；旧 `/data/ohmywod/report` 和 `/mnt/extra-report` 已不存在 |
| JuiceFS | Linode Object Storage + Redis db 2 metadata | `--backup-meta` 巡检 timer 最近执行成功；没有 Redis replica |
| 外部监控 | `/healthz` 经 Cloudflare 返回 200 | UptimeRobot 与两个 Healthchecks timer 已配置；仍需验证备份新鲜度和真实可恢复性 |
| 开机恢复 | 相关 systemd unit enabled，曾做真实重启验证 | 当前 `ohmywod-supervisord` 明确排在 JuiceFS 前，web 仍可能早于挂载启动 |
| 身份 | OpenLDAP 仍 active | LDAP 无独立异地 dump；计划退役但尚未开始 |
| 切换 | Cloudflare 可作为流量切换面 | `scripts/switchover.sh` 仍是会 `exit 1` 的占位骨架，未演练 |

### 1.3 风险结论

当前最大的风险不是“少一台机器”，而是已有恢复材料还没有组成安全闭环：

1. ops 的完整 playbook 会先启动应用和 Litestream，再恢复数据；缺库检查还可能创建空 SQLite。
2. Redis meta、JuiceFS、web 的 systemd 依赖方向不满足“挂载未就绪时 web 不得写入”。
3. 裸机 bootstrap、目录、证书、DNS、Cloud Firewall、密钥真值和 LDAP 身份恢复仍有缺口。
4. 监控目前能证明进程和定时任务在运行，不能单独证明最近副本可恢复。
5. ops 渲染的生产 `local_config.py` 是全量替换类，已经遗漏 app 默认配置中的 SQLite timeout；配置真值漂移会让“代码已完成”不等于“生产已生效”。
6. 如果现在直接增加备机，只会把未验证的恢复与启动问题复制到两台机器，并增加脑裂面。

### 1.4 已拍板的原则

1. 先完成可靠的单机 DR，再建设双机温备；备机不能替代恢复演练。
2. 目标架构是 active-passive，不做多活；SQLite 和 Redis 不允许双主写入。
3. 故障切换由告警触发、人工确认、一条命令执行，不做自动 failover。
4. 备机与主机优先同区域、不同宿主机，用私网 VLAN 复制；区域级故障靠对象存储和从零恢复兜底。
5. 流量切换继续使用 Cloudflare 源站变更，不为这个体量引入 NodeBalancer。
6. 配置管理使用 Ansible，密钥使用 sops + age；不引入 Vault/OpenBao 一类新的在线单点。
7. 战报不做 restic 或第二 bucket 副本。接受暂时没有防误删版本化备份的风险；触发条件见 HA-007。
8. LDAP 在建设备机前退役，避免为过渡组件设计复制和切换。
9. 所有 RPO/RTO 只能来自演练记录，不能从组件宣传或脚本目标推导。

### 1.5 成功判断

计划分两层成立：

- **DR 层成立**：从隔离的空白机器恢复时，不会创建并复制空库，不会向未挂载目录写数据；SQLite、JuiceFS metadata、战报、身份、证书、入口网络和监控均有可复核恢复证据，并记录实际 RPO/RTO。
- **温备层成立**：主机与备机角色明确，只有一端可写；真实切换和回切都演练成功，旧主重新加入前经过防脑裂检查；日常升级能按同一套蓝绿流程完成。

## 2. 这份计划怎么维护

这是个人兴趣项目，不需要 owner、RACI 或复杂发布委员会。后续通常由一个 AI 工具推进，再由另一个 AI 工具独立检查。涉及生产写入、停机、DNS、云资源和持续成本时，由用户做最后决定。

每个事项有两个可选角色：

- `Drive AI`：调查现状、提出选项、实施改动，并更新本文和 changelog。
- `Review AI`：独立检查假设、diff、演练证据和剩余风险，不只复述 Drive AI 的结论。

角色可以写工具名，例如 `Codex` 或 `Claude Code`；尚未分配时写 `unassigned`。

### 2.1 状态枚举

工作项的 `状态` 只能使用以下值：

- `todo`：方向已确认，尚未开始
- `assessing`：仍需调查、成本确认或用户选择，尚不能直接实施
- `in_progress`：正在调查或实施
- `blocked`：存在明确阻塞；必须写明解除方式
- `done`：完成判断已经满足，并有可复核证据
- `cancelled`：明确决定不做；记录理由和重新考虑的触发条件

### 2.2 更新规则

1. 每个 `HA-NNN` ID 永久不变、不可复用。新增事项使用 front matter 的 `next_item_id`，并同步递增。
2. 开始工作前先读本文、两个仓库的 `git status` 和 ops 审查计划，保留用户或其他工具的未提交改动。
3. `状态` 是事项主真值。状态变化、实现改动和 changelog 放在同一波变更里。
4. app 仓只维护跨仓目标和应用侧证据；具体 ops 子问题继续使用既有 `OPS-NNN`，不要在这里复制一份独立状态。
5. `done` 必须满足完成判断。进程 active、Molecule 通过、脚本写完或监控为绿，都不能单独证明恢复/切换完成。
6. 生产写入、停服务、重启、DNS、防火墙、密钥、实例创建或删除必须先获得用户明确授权。
7. 证据不得包含 token、口令、SOPS 明文、完整 capability URL 或个人信息。
8. RPO/RTO、费用和供应商能力容易变化；记录日期和来源，不把估算写成长期承诺。
9. 每波改动在文末按时间正序追加 changelog。旧记录不重写，纠错时追加 correction wave。
10. 每次变更更新 front matter 的 `last_updated`。

### 2.3 固定工作项格式

新增事项使用同一套结构：

- 元信息：`状态`、`优先级`、`波次`、`Drive AI`、`Review AI`、`依赖`、`最后更新`、`结论置信度`
- 内容：`问题与影响`、`证据`、`方向与要点`、`完成判断`、`Review 关注`、`执行证据`

优先级定义：

- `P0`：可能造成数据损坏、空库进入备份链、恢复失败或恢复期间错误对外服务
- `P1`：显著影响可恢复性、切换能力、安全性或变更成功率
- `P2`：成本、治理和长期维护性问题

## 3. 建议推进顺序

### Wave 0：把现有单机恢复路径变安全

范围：HA-004、HA-005。

方向：先解决空库、服务启动顺序和未挂载目录写入风险。完成前不执行完整冷恢复，也不创建长期备机。

### Wave 1：建立可验证的 DR 闭环

范围：HA-006、HA-007、HA-008。

方向：补齐裸机、身份、证书、网络和备份证据，在隔离新机做一次端到端恢复并测量 RPO/RTO。LDAP 退役后，SQLite/Litestream 才能覆盖完整账号真值。

### Wave 2：建设并演练温备

范围：HA-009、HA-010。

方向：通过 DR gate 后再创建备机、复制 Redis metadata、实现切换与回切。第一轮使用临时或可按小时计费的实例验证，结果和成本都可接受后再决定长期保留。

## 4. 工作项

### HA-001 — 单机宿主加固与外部存活监控

- 状态：`done`
- 优先级：`P1`
- 波次：历史基线
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-18
- 结论置信度：`confirmed`

问题与影响：旧生产机的 SSH、Redis 暴露、开机自启和外部存活监控都依赖手工状态，重启可能直接变成停机。

证据：ops 仓已经落地 SSH hardening、Cloud Firewall、systemd 受管服务、nginx、UptimeRobot `/healthz` 和 Healthchecks timer；2026-07-12 做过真实重启验证。2026-07-18 只读检查确认相关 unit enabled/active、公开 `/healthz` 返回 200。

方向与要点：保留现有能力；后续的恢复顺序和服务依赖缺口由 HA-004、HA-005 处理，不反向改写本项状态。

完成判断：现有主机重启后基础服务可恢复，公网入口只暴露预期端口，站点和备份巡检有外部告警。

Review 关注：本项 `done` 不等于冷恢复可用，也不证明 JuiceFS 先于 web 启动。

执行证据：`ohmywod-ops` roles：`ssh_hardening`、`supervisord`、`juicefs`、`monitoring`、`nginx`；生产只读复核日期 2026-07-18。

### HA-002 — 战报存储归一化并迁入 Linode Object Storage

- 状态：`done`
- 优先级：`P1`
- 波次：历史基线
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-001
- 最后更新：2026-07-18
- 结论置信度：`confirmed`

问题与影响：战报曾分散在本地盘、Block Storage 和 JuiceFS，靠软链接拼接；任何切换都要同时搬运三种存储状态。

证据：app 的 `DATA_DIR` 已收敛为 `/mnt/jfs/reports`，usage、上传阈值和 `/healthz` 已删除旧存储语义；ops 的 JuiceFS 后端已切到 Linode Object Storage。生产只读检查确认旧本地 report 目录和 `/mnt/extra-report` 均不存在，约 104 GiB 战报位于 JuiceFS。

方向与要点：继续把 JuiceFS metadata 视为最高价值恢复对象；对象块存在不等于文件系统可恢复。

完成判断：生产读写只使用 JuiceFS 战报目录，旧 Block Storage 已释放，应用和运维配置不再依赖旧路径。

Review 关注：避免重新引入三路径容量显示、软链接或迁移脚本。

执行证据：app `0512c83`；ops `c5ee2b8`/`470ba2f`；2026-07-18 生产挂载与目录检查。

### HA-003 — SQLite WAL、持续复制与基础巡检

- 状态：`done`
- 优先级：`P1`
- 波次：历史基线
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-001
- 最后更新：2026-07-18
- 结论置信度：`confirmed, replication only`

问题与影响：单机 SQLite 没有持续副本时，主机损坏会同时丢应用数据。

证据：生产数据库为 WAL，`PRAGMA integrity_check` 返回 `ok`；Litestream 0.3.13 active，Healthchecks timer 最近执行成功，历史上做过一次 restore smoke。应用锁等待的生产漂移单独由 IMP-003 处理。

方向与要点：本项只确认“持续复制链已建立”。恢复安全、备份新鲜度和冷恢复由 HA-004、HA-006、HA-007 验收。

完成判断：生产数据库稳定运行在 WAL，Litestream 连续复制，基础失败能被巡检发现。

Review 关注：不要用 service active 或能列出旧 generation 代替最新恢复验证。

执行证据：app `8fb058e`；ops Litestream role 与 monitoring role；2026-07-18 生产只读检查。

### HA-004 — 重排冷恢复流程，阻止空库上线或进入备份链

- 状态：`todo`
- 优先级：`P0`
- 波次：Wave 0
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-003
- 最后更新：2026-07-18
- 结论置信度：`confirmed`

问题与影响：现有恢复文档先运行完整 playbook，再恢复数据。Litestream role 的 SQLite 检查会在缺库时创建空文件，app、nginx 和 Litestream 也可能过早启动。

证据：`ohmywod-ops/docs/ops-review-plan.md` 的 OPS-001、OPS-002；`docs/recovery.md` 当前顺序；Litestream role 使用默认 `sqlite3.connect()`。

方向与要点：拆分“准备机器、恢复数据、验证、激活流量”；缺库检查必须使用不创建文件的只读打开；恢复完成前禁止 app 和 Litestream 写入/复制目标。

完成判断：空白机和常见失败路径都不会创建空业务库、污染最后恢复点或提前对外服务；`--check` 不产生业务数据副作用。

Review 关注：Litestream generation 选择、失败清理和重复执行是否仍有污染路径。

执行证据：尚无；具体执行状态跟踪 OPS-001、OPS-002。

### HA-005 — 修正 Redis meta、JuiceFS、web 和 nginx 的服务依赖

- 状态：`todo`
- 优先级：`P0`
- 波次：Wave 0
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-004
- 最后更新：2026-07-18
- 结论置信度：`confirmed`

问题与影响：Redis store、Redis cache 和 web 同属一个 Supervisor unit。JuiceFS 必须等 Redis store，但 web 又必须等 JuiceFS，当前 unit 粒度形成错误依赖，重启时 web 可能写进挂载点的底层目录。

证据：生产 `systemctl show` 显示 `ohmywod-supervisord Before=juicefs.service`；app Supervisor 模板同时管理 web 和两个 Redis；OPS-003 已记录同一问题。

方向与要点：重建启动/停止关系，保证 Redis meta → JuiceFS ready → web → nginx；具体选择拆 unit、拆 Supervisor 或增加可靠 gate，实施时评估。

完成判断：正常重启、JuiceFS 挂载失败和短暂对象存储故障下，web 都不会向未挂载目录写入；依赖可由自动测试和真实重启复现。

Review 关注：循环依赖、停止顺序、挂载假活和 nginx 过早接流量。

执行证据：尚无；具体执行状态跟踪 OPS-003。

### HA-006 — 补齐裸机恢复前提并完成端到端演练

- 状态：`todo`
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-004、HA-005
- 最后更新：2026-07-18
- 结论置信度：`confirmed`

问题与影响：bootstrap、运行目录、Supervisor 来源、证书、DNS、Cloud Firewall、新 inventory 和工具安装尚未形成空白 Ubuntu 可重复流程。现有 smoke 只恢复 SQLite 到临时目录。

证据：OPS-002、OPS-004、OPS-007、OPS-010 至 OPS-012；2026-07-18 生产也确认系统没有 `sqlite3` CLI，说明文档中的隐含工具前提不成立。

方向与要点：在隔离新机从信任根开始，恢复 SQLite、JuiceFS metadata/战报、身份、证书、入口网络和监控；验证后再切测试流量。记录每一步耗时和恢复点时间。

完成判断：一台空白 Ubuntu 能安全到达“数据已恢复但未上线”，再经显式激活对外服务；至少一次完整演练记录真实 RPO/RTO、回退和遗留手工步骤。

Review 关注：是否偷用了旧主机文件、个人 shell、已存在 DNS/证书或未入库凭据。

执行证据：尚无；详细子项跟踪 OPS-002、OPS-004、OPS-007、OPS-010、OPS-011、OPS-012。

### HA-007 — 验证备份新鲜度、保留策略与误删风险边界

- 状态：`assessing`
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-006
- 最后更新：2026-07-18
- 结论置信度：`confirmed gap, solution assessing`

问题与影响：当前 timer 成功只证明脚本返回 0；战报对象和 metadata 也没有独立、不可变、可回到误删前的副本。

证据：OPS-005、OPS-006；当前设计明确不做 restic 和第二 bucket，JuiceFS `TrashDays` 为 1。

方向与要点：先让监控校验最新可恢复点的年龄，并用定期隔离恢复证明副本可用。是否增加对象版本化、第二 bucket 或更长 trash 保留，只按真实误删风险、供应商能力和成本评估。

完成判断：SQLite 和 JuiceFS metadata 的新鲜度阈值明确且会告警；恢复演练能读取最新副本；用户已明确接受或收窄战报误删风险。

Review 关注：复制与备份边界、同账号/同区域故障域、告警被静默禁用、恢复验证污染生产。

执行证据：尚无；详细子项跟踪 OPS-005、OPS-006。

### HA-008 — 退役 LDAP，把身份真值纳入 SQLite 恢复链

- 状态：`todo`
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-003、HA-006
- 最后更新：2026-07-18
- 结论置信度：`recommended`

问题与影响：OpenLDAP 仍是本机单点且没有异地 dump；如果先建设备机，就要为一个计划退役的组件额外设计复制、恢复和切换。

证据：生产 `slapd` active；应用仍使用 `flask-ldap3-login`，admin 仍是独立 Basic Auth；OPS-008 指出 LDAP 身份与“两个信任根”说法尚未闭环。

方向与要点：把 SSHA 哈希迁入 user 表，登录成功惰性升级到 argon2id；补找回密码、统一失败提示、登录限速和 session 吊销；双轨只读观察后再停 LDAP。邮件只使用标准 SMTP 接口，供应商在实施时复核。

完成判断：现有用户无需统一重设密码；注册、登录、改密、找回密码和 admin 权限有测试与迁移/回退记录；LDAP 停止后，账号可随 SQLite/Litestream 恢复。

Review 关注：SSHA 兼容实现、token 失效、用户枚举、邮件失败、管理员迁移和双轨期间的真值冲突。

执行证据：尚无。

### HA-009 — 通过 DR gate 后建立同区域温备

- 状态：`assessing`
- 优先级：`P1`
- 波次：Wave 2
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-006、HA-007、HA-008
- 最后更新：2026-07-18
- 结论置信度：`direction confirmed, sizing pending`

问题与影响：单机仍会受宿主机故障和维护窗口影响；但当前 1 GiB 主机已有 swap 压力，直接复制现有形状会把资源和恢复问题一起复制。

证据：生产内存约 961 MiB，2026-07-18 已使用 swap；没有私网 IPv4、standby inventory 或 Redis replica。温备脚本仍是占位。

方向与要点：先用临时新机验证 Ansible 与 DR，再决定长期主备规格。候选是同区域两台至少 2 GiB、不同宿主机、私网 VLAN；Redis store 单向复制，备机 cache 独立，应用常驻但不接公网流量。

完成判断：DR gate 全部通过；实例规格由实测内存和成本确认；主备配置一致，角色和唯一写入端明确，复制延迟与故障行为有记录。

Review 关注：同宿主机放置、私网认证、Redis 全量同步内存峰值、备机误接生产流量和持续费用。

执行证据：尚无。创建实例和持续成本必须由用户确认。

### HA-010 — 实现并演练切换、回切和日常蓝绿发布

- 状态：`todo`
- 优先级：`P1`
- 波次：Wave 2
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：HA-009
- 最后更新：2026-07-18
- 结论置信度：`recommended`

问题与影响：没有演练过的切换脚本不能降低故障恢复时间；当前占位脚本只打印 TODO 并退出。

证据：`ohmywod-ops/scripts/switchover.sh` 当前 `exit 1`；没有回切脚本、真实 Cloudflare 切流记录或防脑裂 gate。

方向与要点：脚本先 fencing/确认旧主不可写，再提升 Redis、恢复 SQLite、重挂 JuiceFS、运行本机健康与业务冒烟，最后显式切 Cloudflare；回切走相同的重新同步和唯一主校验。日常发布复用同一流程。

完成判断：低峰真实切换和回切各成功一次；记录告警到人工确认、脚本执行、流量恢复和数据新鲜度；任一步失败能安全停住并回退。

Review 关注：旧主复活、Cloudflare API 部分成功、SQLite 写入窗口、Redis replication offset、DNS/证书和脚本重复执行。

执行证据：尚无。

## 5. 目标拓扑与成本 gate

### 5.1 目标拓扑

```text
                    Cloudflare（唯一公开入口）
                         │ 人工确认后切源站
               ┌─────────┴─────────┐
               ▼                   ▼（平时不接流量）
         ┌───────────┐       ┌───────────┐
         │ active     │       │ standby    │
         │ nginx/web  │       │ nginx/web  │
         │ SQLite     │       │ SQLite 恢复副本 │
         │ Redis meta │──────▶│ Redis replica │
         │ JuiceFS    │       │ JuiceFS     │
         └─────┬─────┘       └─────┬─────┘
               └────────┬──────────┘
                        ▼
              Linode Object Storage
              战报块 + meta dump + Litestream
```

只有 active 可以处理业务写入。standby 提升为 active 前必须确认旧主不可写；旧主恢复后不能自动重新加入。

### 5.2 成本规则

- 月预算上限仍为 100 美元，但不是“有预算就必须花完”。
- 当前 Object Storage 计费和实例价格在实施时从 Cloud Manager / [Akamai Cloud 官方价格页](https://www.akamai.com/cloud/pricing) 复核；价格与区域可能变化，不在本文把约 29 美元的旧估算当作真值。
- HA-009 第一轮优先使用按小时计费的临时实例完成恢复和容量验证，再决定是否长期保留两台。
- 2 GiB 是当前候选下限，不是永久规格。判断依据是 Redis 全量同步、JuiceFS cache、gunicorn 和恢复过程的峰值内存，而不是稳定态平均值。
- 不再为旧 `/mnt/extra-report` 支付 Block Storage；若账单仍存在该卷，需在云端确认数据已释放后单独清理。

## 6. 明确不做

- 不做多活、SQLite 多主、Redis 双主或自动 failover。
- 不为现有体量引入 Kubernetes、NodeBalancer、Consul、etcd、Vault/OpenBao 或独立 PostgreSQL 集群。
- 不把 service active、timer success、Molecule green 或脚本存在写成“可恢复”证据。
- 不在 app 公共仓库复制生产 IP、bucket、monitor ID、密钥 schema 明文或完整恢复命令。
- 不在 HA-004 至 HA-008 未通过前购买并长期运行备机。
- 不承诺尚未演练出的 20 分钟冷恢复或 1 分钟切换目标。
- 不默认增加 restic 或第二 bucket；只有 HA-007 的风险/能力评估给出明确收益时再重看。

## 7. 待决策清单

以下问题按对应事项处理，不阻塞 Wave 0：

1. HA-007：是否继续接受战报无独立防误删备份，以及 JuiceFS trash 保留多久。
2. HA-008：找回密码邮件供应商和发件域最终设置。
3. HA-009：实测后选择长期 2 GiB ×2，还是保留单机 + 临时恢复机模式。
4. HA-009：是否需要供应商级 placement group 来明确主备分散到不同宿主机。
5. HA-010：可接受的人工响应窗口，以及真实切换演练的低峰时间。

## 8. Changelog（append-only，旧 -> 新）

> 每波改动在本节末尾追加。不得改写旧记录；旧版文档在引入 changelog 前的历史仍可从 Git 追溯。

### Changelog 条目模板

```markdown
### WAVE-YYYYMMDD-NN — 简短标题

- 日期：YYYY-MM-DD
- Drive AI：工具名称；未使用则写“无”
- Review AI：工具名称；尚未 review 则写 `unassigned`
- 关联事项：HA-NNN, HA-NNN
- 状态变化：例如 HA-004 `todo` -> `in_progress` -> `done`
- 改动：文件、基础设施或运行手册摘要
- 关键取舍：选择和理由；无则写“无”
- 验证：检查、测试或演练摘要，不含密钥和个人信息
- 发生的问题：无则写“无”
- 剩余风险：本波未解决的内容
- 下一步：下一事项或需要用户决定的问题
```

### WAVE-20260718-01 — 按当前实现重建 HA/DR 计划真值

- 日期：2026-07-18
- Drive AI：Codex
- Review AI：`unassigned`
- 关联事项：创建 HA-001 至 HA-010
- 状态变化：确认 HA-001 至 HA-003 `done`；新增 HA-004 至 HA-006、HA-008、HA-010 `todo`；新增 HA-007、HA-009 `assessing`
- 改动：以维护支持计划的 front matter、稳定 ID、固定状态、完成证据和 append-only changelog 结构重写本文；把旧“阶段 0 已解决 80% 风险”的说法改为当前能力边界；将 ops 审查的 P0 恢复问题放在温备之前
- 关键取舍：保留 active-passive + 人工切换的目标架构，但不再把备机建设当作下一步；先完成安全冷恢复和 LDAP 退役
- 验证：核对 app `0f52bf9`、ops `5988138`、生产 app `0512c83`；2026-07-18 通过 SSH 只读检查服务、依赖、挂载、WAL、Redis replication、timer、内存、公开 `/healthz` 和有效非密钥 Flask 配置；本地 `pytest` 39 项通过；未修改生产
- 发生的问题：生产没有系统级 `sqlite3`，改用 app venv 的 Python 以 SQLite URI `mode=ro` 读取 journal mode 和 integrity；Supervisor 控制端口拒绝连接，因此不把 supervisor 子进程状态作为本轮证据
- 剩余风险：恢复顺序和服务依赖仍是 P0；LDAP、无 Redis replica、备份新鲜度和冷恢复均未闭环
- 下一步：从 HA-004 / OPS-001 开始，先把数据库存在性检查改为不创建文件的只读模式，再拆分恢复阶段
