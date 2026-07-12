# 高可用计划（2026-07 定稿）

单点 Linode VPS → 双机温备架构的完整计划。目标不是业界标准的"真 HA"（多活 + 自动 failover），而是用最小成本达成两件事：

1. **迁移和大改动不再造成服务不可用**——所有升级变成蓝绿部署：备机先做、先验证、再切流量。
2. **物理机重启/宕机可控**——从"听天由命等 Linode"变成"收到告警后一条命令切换，1~2 分钟恢复"。

预算上限 $100/月，方案实际成本约 $30/月。

前置阅读：[vps-migration-2026-07.md](vps-migration-2026-07.md)（当前生产拓扑以它为准）。

## 已拍板的决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 架构 | **温备（active-passive），不做多活** | 读多写少、写丢失容忍度高；多活需要 SQLite→PG、NodeBalancer 等，成本翻倍只为把"1 分钟手动切换"变成 0 秒 |
| 备机位置 | **同机房** | JuiceFS/Redis 复制延迟敏感 + 免费私网 VLAN + Block Storage 卷只能同机房漂移；防宿主机故障两台不同宿主机已覆盖，机房级灾难靠 bucket 备份异地重建兜底 |
| 切换方式 | **告警后手动触发脚本**，不做自动 failover | 自动切换的脑裂风险（双写 SQLite/Redis）> 收益；个人项目可接受几分钟人工响应 |
| 流量切换 | **Cloudflare 改源站 IP**（已是橙云代理，秒级生效） | 不依赖 DNS TTL；已就绪 |
| 对象存储 | **AWS S3 → Linode Object Storage** | 用 Linode credit；同机房延迟更好。接受几分钟停写窗口做最终切换 |
| LDAP | **退役**，认证收编进 Flask + SQLite，安排在搭建备机**之前** | N=1 应用付多应用成本；退役后 HA 拓扑少一个最难伺候的组件，切换脚本不用写带 slapd 的版本 |
| Secrets | **sops + age**，加密进私有配置仓库（`ohmywod-ops`） | 零运行时依赖；Vault/OpenBao 类在线服务对 N=1 项目是负资产（自身成为新单点，重启后 sealed——精确患上我们正在治的病） |
| 找回密码邮件 | **Resend 免费档**（3000 封/月），发件域 `everbird.me` | 自定义域名是硬需求（gmail 地址发改密链接形同钓鱼）；应用侧只写标准 SMTP，凭据走 secrets.env，可随时换厂商 |

## 状态盘点：绑死单机的东西

| 状态 | 位置 | 关键程度 | 归宿 |
|---|---|---|---|
| SQLite 主库 | `/data/ohmywod/ohmywod_d.sqlite` | 高 | Litestream 持续复制 → Linode OS bucket |
| JuiceFS metadata | redis-store **db 2** | **最高**（丢了 = 整个 JuiceFS 报废，S3 块变废纸） | AOF + 备机 replica + `--backup-meta` 兜底 |
| 点赞/浏览计数 | redis-store 其他 db（`/stats/report/*`） | 低 | 随整实例复制，丢了可忍 |
| 战报文件（本地） | `/data/ohmywod/report`（含软链接） | 高 | 归一化进 JuiceFS（见下），过渡期 restic 备份 |
| 战报文件（块存储） | Block Storage 卷 `/mnt/extra-report` | 高 | 同上归一化；未归一化前靠卷漂移 + restic |
| 战报文件（JuiceFS） | `/mnt/jfs`（S3 后端） | 高 | 后端迁 Linode OS；数据本身已在对象存储 ✓ |
| 用户账号 | 本机 OpenLDAP | 高 | 退役进 SQLite（随 Litestream 走） |
| Session | redis（Flask-Session） | 可丢（重新登录） | 不处理 |
| 真实配置/secrets | 线上手工维护的 `local_config.py` 等 | 高 | 反向工程入私有 git 仓库 + sops 加密 |

**存储归一化（推荐，新增提议）**：战报目前横跨本地盘、块存储卷、JuiceFS 三处靠软链接粘合。建议全部归并进 JuiceFS——后端换成 Linode OS 后容量便宜（$0.02/GB vs 块存储 $0.10/GB，且有 credit），本地盘只留 JuiceFS cache。收益：文件层变成"近乎无状态"，failover 不再需要块存储卷的 detach/attach 舞蹈，`DISK_USAGE_THRESHOLD` 溢出逻辑和三处软链接的复杂度全部消亡。做完后卷可释放，省 $ 也省心。

## 目标拓扑

```
                     Cloudflare（橙云代理，已就绪）
                       │  切换 = API 改源站 IP，秒级
              ┌────────┴────────┐
              ▼                 ▼（平时不接流量）
        ┌──────────┐      ┌──────────┐
        │ 主机 2GB  │      │ 备机 2GB  │   同机房，私网 VLAN 互联
        │ nginx     │      │ nginx     │
        │ gunicorn  │      │ gunicorn（常驻）
        │ redis-    │─────▶│ redis-store replica（实时）
        │  store    │ 复制  │ redis-cache（独立）
        │ redis-    │      │ juicefs mount（指向主 redis）
        │  cache    │      │ sqlite（Litestream 定时 restore）
        │ juicefs   │      └──────────┘
        │ sqlite ───┼─Litestream─┐
        └──────────┘            ▼
                    Linode Object Storage bucket
                    （JuiceFS 块 + Litestream 副本 + restic 备份 + juicefs meta dump）
```

LDAP 退役后拓扑中没有 slapd。恢复的信任根只有两个：**私有配置仓库**（含 sops 加密的 secrets）+ **密码管理器里的 age 私钥**，两者在手可从零重建一切。

## 实施阶段

每步独立有价值，做到哪停到哪都行。

### 阶段 0：单机加固（不加机器）

执行细节见 [ha-phase0-runbook.md](ha-phase0-runbook.md)。

1. **线上体检**（两条命令的事，先做）：
   - redis-store 是否开了 AOF？没有则加 `appendonly yes` + `appendfsync everysec`（metadata 实例 RDB-only 意味着最坏丢 15 分钟 JuiceFS 元数据 = 近期上传变孤儿块）。
   - JuiceFS 挂载是否带 `--backup-meta`（定期 dump 元数据到 bucket）？没有则加上，或配 `juicefs dump` 的 cron。
2. **配置反向工程入库**：线上真实的 redis conf、juicefs 挂载参数（systemd unit / fstab）、nginx server block、supervisord、certbot 配置收进私有 git 仓库；secrets 用 sops+age 加密（`secrets.env.enc`），age 私钥存密码管理器。目标：从裸 Ubuntu 24.04 到服务就绪的一键部署脚本（迁移记录里的 8 步固化成代码）。
3. **备份链路**：
   - SQLite：Litestream 持续复制 → Linode OS bucket（秒级 RPO，零代码侵入）。
   - `report/` 本地部分 + 块存储卷：restic 定时增量备份 → 同 bucket（存储归一化完成后此项自然消亡）。
   - LDAP：每日 `slapcat -b "dc=everbird,dc=me"` 进备份（退役后消亡）。
   - 所有 cron 接 Healthchecks.io（免费）——备份最怕静默失败。
4. UptimeRobot（免费）监控 `https://wod.everbird.me/healthz`。

**阶段 0 完成态**：机器整个炸了也能 20 分钟在任何 VPS 商重建，数据丢失以秒计。已解决 80% 风险。

### 阶段 1：S3 → Linode Object Storage

1. 建 bucket（与 VPS 同机房）。
2. `juicefs sync` 把块数据 S3 → Linode OS（服务照常跑，可多轮增量）。
3. 停写窗口（浏览不受影响，仅暂停上传）：最后一轮增量 sync → `juicefs config --bucket` 指向新 bucket → 重挂载 → 验证 → 恢复写入。窗口预计几分钟。
4. 观察数日后清空 AWS S3，退订。
5. **（推荐同期做）存储归一化**：本地 `report/` 实体文件与 `/mnt/extra-report` 内容 `juicefs sync`/cp 进 `/mnt/jfs`，软链接改指或直接换成 JuiceFS 路径，验证后释放块存储卷。

### 阶段 2：LDAP 退役 + 密码体系（代码改动，详设见附录 A）

1. user 表加密码哈希等字段；`slapcat` 导出，`{SSHA}` 哈希原样导入——passlib/libpass 可直接校验，**用户无感知，无需重设密码**。
2. 登录换 CryptContext（argon2 首选 + SSHA 兼容），登录成功惰性升级哈希。
3. 新增找回密码流程（Resend + itsdangerous 限时 token）。
4. Flask-Limiter 登录限速；改密后吊销该用户全部 session。
5. admin 后台并入同一套认证（user 表加 `is_admin`），删除 `FLASK_ADMIN_USERNAME/PASSWD` 配置对。
6. 双轨观察 1~2 周（LDAP 只读兜底）→ 停 slapd → 删 flask-ldap3-login 依赖。

### 阶段 3：备机 + 切换能力

1. 开同机房 Linode 2GB ×2（现 nano 1GB 跑双 redis + JuiceFS cache + gunicorn 太挤，借机升配；主机用一键部署脚本重建为 2GB，本身就是对脚本的第一次实战演练 + 第一次蓝绿切换）。
2. 备机常态：
   - redis-store 作 replica（走私网 VLAN，`replicaof <主机私网IP> 6379`，设 `masterauth`）；
   - Litestream 每 5 分钟 restore 最新 SQLite 到本地；
   - JuiceFS 挂载指向主机 redis（只读用途）；
   - 应用进程常驻（随时可接流量）。
3. **切换脚本**（一条命令）：备机 redis `REPLICAOF NO ONE` → JuiceFS 重挂到本地 redis → restore 最新 SQLite → 冒烟检查 → Cloudflare API 改源站 IP。目标 1 分钟内。
4. **演练一次真实切换**（周末低峰），并把回切也演练了。没演练过的 failover 等于没有。

### 日常运维模式（阶段 3 之后）

- **升级/迁移** = 蓝绿：备机上先做 → hosts 指过去全链路验证 → 切流量 → 老主机变新备机。
- **宿主机故障** = UptimeRobot 告警 → 确认主机确实不可用 → 跑切换脚本。
- 每次大版本升级顺便就是一次 failover 演练，能力不会锈掉。

## 成本

| 项目 | 月费 |
|---|---|
| Linode 2GB ×2 | $24 |
| Linode Object Storage 250GB | $5（credit 可抵） |
| Block Storage 卷 | $0（归一化后释放） |
| Cloudflare / UptimeRobot / Healthchecks / Litestream / restic / sops / Resend | $0 |
| **合计** | **≈ $29**（预算 $100 的三成） |

结余预算刻意不花：留作数据增长后升配，不为"最佳实践"加机器。

## 附录 A：密码与认证详设

- **哈希**：argon2id。用 `CryptContext(schemes=["argon2", "ldap_salted_sha1"], deprecated="auto")` 的 `verify_and_update()` 实现 SSHA 惰性升级。注意 passlib 已停维护，用兼容 fork **libpass**（或 argon2-cffi + 手写 20 行 SSHA 校验）。
- **策略**（NIST 800-63B）：仅最小长度 ≥10，不强制字符组合、不强制定期改密，最大长度 ≥64。可选：HIBP k-匿名 API 拒绝已泄露密码。
- **防爆破**：Flask-Limiter（存储用现有 redis-cache），按 `CF-Connecting-IP` + 用户名双维度各 5 次/分钟；Cloudflare 免费 rate limiting rule 指向 `/login`；登录失败统一提示"用户名或密码错误"。
- **找回密码**：itsdangerous 签发 30 分钟限时 token，payload 含 user_id + 当前密码哈希指纹（密码一改旧 token 自动失效，无需存库）；页面对不存在的邮箱同样显示"已发送"（防枚举）；发送失败记日志并告警（低频功能最怕坏了没人知道）。
- **Session**：改密/重置成功后删除该用户在 redis 中的全部 session。
- **明确不做**：强制 2FA。admin 账号可选 pyotp TOTP，优先级最低。

## 附录 B：Secrets 管理（sops + age）

```bash
age-keygen -o ~/.config/sops/age/keys.txt   # 私钥进密码管理器
sops -e secrets.env > secrets.env.enc        # 密文进私有配置仓库
# 部署时：sops -d secrets.env.enc > /etc/ohmywod/.env && chmod 600
```

不引入 Vault/OpenBao：在线秘密服务自身需要 HA、重启后 sealed、为 ~10 个静态字符串引入 24/7 依赖，N=1 场景全是负资产。若未来服务数量增长或 Akamai 推出托管 OpenBao，再评估迁移（sops → 任何方案都是半小时的事，现在的选择不锁死未来）。

## 附录 C：邮件（Resend）

- 免费档 3000 封/月；`everbird.me` 配 DKIM/SPF/DMARC（DNS 在 Cloudflare，顺手）。
- 应用只写标准 SMTP（Flask-Mail/smtplib），host/凭据走 secrets.env——换厂商 = 改 4 个环境变量，不用任何厂商 SDK。
- 备选：Brevo（300 封/天）、SES（最便宜但 sandbox 审核 + 与撤离 AWS 方向相反）。不自建 SMTP（Linode 封 25 端口 + IP 信誉无底洞）。
- Cloudflare Email Routing 只管收信，顺手配 `noreply@` 回信转发，与发信互补。

## 附录 D：Redis 迁移与恢复操作手册

### 开启 AOF（从 RDB-only 切换，零丢失）

数据真身在内存，RDB/AOF 只是落盘格式。热开启以当前内存为起点生成 AOF，不读旧 dump.rdb，零丢失；RDB 的 save 规则继续生效，之后是双持久化并存，重启时优先加载 AOF。

```bash
# 1. 热开启（无中断）
redis-cli -p 6379 CONFIG SET appendonly yes
redis-cli -p 6379 CONFIG SET appendfsync everysec
# 2. 确认：aof_enabled:1、aof_rewrite_in_progress:0、aof_last_bgrewrite_status:ok
redis-cli -p 6379 INFO persistence | grep -E 'aof_enabled|rewrite'
# 3. 把 appendonly yes / appendfsync everysec 写进配置模板（gen.py 的源头，不是线上产物）
```

**脚枪警告**：不要跳过热开启、直接改配置文件重启——老版本 Redis 发现"配置有 AOF 但磁盘上没有"时会建空 AOF 且不加载 RDB，等于清库。永远先 `CONFIG SET` 再改文件。

### 未来迁移：首选复制，不拷文件

```
新机器 redis 启动 → REPLICAOF <老机器IP> 6379 → 等全量+增量同步完成
→ 各 db 的 DBSIZE 对比一致 → 应用切换 → 新机器 REPLICAOF NO ONE
```

复制协议内部自己传 RDB 流并实时追增量，源端 AOF 开关无关，服务不停。迁移 = 一次演练过的 failover。

### 拷文件迁移（仅当两机网络不通时的退路）

**RDB 是搬家格式，AOF 是本机续命日志，不要搬 AOF**（appendonlydir 需源端完全停机才能一致拷贝，约束多收益零）。

1. 源端 `redis-cli --rdb dump.rdb`（走复制协议取快照，不受 AOF 影响）；
2. 目标机 redis 以 `appendonly no` 启动加载 dump.rdb（文件名必须是 dump.rdb，且在首次启动前放进 dir）；
3. 验证 `DBSIZE` 后按上面流程热开启 AOF，再写回配置。

### JuiceFS 元数据（db 2）的专属通道

`juicefs dump` / `juicefs load` 走文件系统语义导出导入（2026-07 迁移实际用过），与 Redis 层迁移互为备份手段；`--backup-meta` 的定期 dump 存于 bucket 的 `meta/` 目录，是最后的兜底。

## 待线上确认（阶段 0 第 1 步）—— 2026-07-05 已确认

- [x] redis-store 的 AOF 状态：**原为 RDB-only，已按附录 D 流程热开启 AOF（everysec）**；`configs/templates/redis-store.conf.template` 已同步 `appendonly yes` + `appendfsync everysec`
- [x] JuiceFS `--backup-meta`：**未开启**。待办：挂载参数显式加 `--backup-meta 1h` 写进 systemd unit，低峰时段重挂载生效
- [x] 存储占用：本地 `report/` 6.2G + `/mnt/extra-report` 8.9G ≈ 15G——对象存储 250GB 起步档绰绰有余，归一化无容量顾虑
- [x] redis-store 无 `requirepass`，且曾监听 `0.0.0.0`（幸有默认 `protected-mode yes` 拒绝了所有外部连接，未成事故）。**已修复**：线上两个 redis 均已 `bind 127.0.0.1 -::1` + 显式 `protected-mode yes` 并重启，配置模板同步更新。密码推迟到阶段 3 建复制前统一加（需同步改 flask-redis URL 与 juicefs meta URL）。教训：Linode Cloud Firewall（阶段 0 待办）作为此类失误的外层兜底
- [x] 应用侧 `/healthz` 已落地，检查 SQLite、Redis、`DATA_DIR` 和 `/mnt/jfs`；UptimeRobot 改监控该端点
