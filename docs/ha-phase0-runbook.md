# HA 阶段 0 执行手册（2026-07）

本手册对应 `ha-plan.md` 的“阶段 0：单机加固”。目标：把单机从“坏了才知道、靠手工记忆恢复”推进到“有持续备份、有监控、有可复现配置、有恢复演练”。

**执行方式（2026-07-12 起）**：配置管理已从 bash 一键脚本转为 **Ansible**（`ohmywod-ops/ansible/`）。每个 role 先过 **molecule**（Docker + systemd 容器，本地验证 converge/幂等/断言）再对生产 `ansible-playbook site.yml` 收敛；密钥用 **sops+age**，由 **community.sops** vars 插件消费（非 ansible-vault）。**执行细节以 `ohmywod-ops` 为准，本文只跟踪阶段 0 各项状态**；下方保留的 bash 命令仅作参考/验收用。

## 状态一览（2026-07-15）

| # | 项 | 状态 | 落地 / 备注 |
|---|---|---|---|
| 1 | 私有配置仓库 + 可复现部署 | ✅ 骨架完成 | `ohmywod-ops`，Ansible roles + molecule |
| + | SSH 加固（关密码登录、root 仅 key） | ✅ 已上并验证 | role `ssh_hardening`（体检新发现，原计划未列）|
| + | 开机自启（supervisord+juicefs → systemd） | ✅ 已上，**真实重启验证** | roles `supervisord`/`juicefs`（修“重启=停机”，原计划未识别）|
| 2 | 固化 Redis（AOF / loopback） | ✅ 线上确认 | 运行态与模板一致 |
| 3 | JuiceFS `--backup-meta 1h` | ✅ 已上 | role `juicefs`，进程 cmdline 确认 |
| 4 | Litestream 备份 SQLite | ✅ 已上，**restore 演练过** | role `litestream` → Linode OS `ohmywod-backups`(jp-tyo-1)，已切 WAL |
| 5 | ~~restic 过渡备份（战报文件 / 块存储卷）~~ | ❌ 已砍（2026-07-12） | 归一化进 JuiceFS 后不做，接受无防误删备份风险，见 ha-plan.md "restic 决策" |
| 6 | ~~LDAP 每日 dump~~ | ❌ 已砍（2026-07-12） | 阶段 2 就退役，过渡窗口不单建备份；接受 cutover 前账号无异地备份的窗口风险 |
| 7 | 监控（UptimeRobot + Healthchecks） | ✅ 已上 | UptimeRobot 监控 `/healthz`；Healthchecks 已接 Litestream 与 JuiceFS meta 巡检 |
| 8 | Cloud Firewall | ✅ 已收口 | 入站默认 Drop；80/443 已收窄到 Cloudflare IP 段；389/8013 不对公网开放；SSH 仅作管理入口 |

## 不能进主仓库的内容

以下内容进 `ohmywod-ops`（密钥经 sops 加密），不提交本仓库：

- 真实 `ohmywod/local_config.py`、`.env`、Redis 密码、Cloudflare/Linode/S3/Resend token。
- nginx server block、certbot/Cloudflare DNS token、JuiceFS secret key、Litestream repository password、对象存储 access/secret key。
- age 私钥（只放密码管理器；仓库只放 sops 密文）。

## 各项参考与验收

### 1. 私有配置仓库 + Ansible —— ✅

`ohmywod-ops`：`ansible/`（roles + molecule + `community.sops`）、`docs/apply-bootstart.md`（开机自启上线手册）、`docs/recovery.md`（恢复手册）。控制节点在 WSL，SSH 到生产；生产另 clone 于 `/var/ohmywod/ops`（供 systemd 脚本）。主仓库 `ohmywod/config.py` 是生产非密钥真值唯一来源；生产 `local_config.py` 将由 **app role** 用 sops 渲染（继承 config.py + 只覆盖 4 个密钥）。
验收：从裸 Ubuntu 24.04 能用 `ansible-playbook` 复现 nginx/supervisord/redis/JuiceFS/应用配置。

### SSH 加固 —— ✅（体检新增）

关 `PasswordAuthentication`、`PermitRootLogin prohibit-password`（drop-in，role `ssh_hardening`）。已验证 key 登录正常、密码登录被拒。背景：体检发现 22 对全网开放且原开着密码登录 + root 登录 + 无 fail2ban。

### 开机自启 —— ✅（体检新增）

生产 supervisord 与 JuiceFS 原为**手动启动**（无 systemd unit / fstab），机器重启后不会自动恢复（"重启=停机"陷阱）。roles `supervisord`/`juicefs` 收编为 systemd 服务并 enable；2026-07-12 做过一次**真实重启验证**：全链路自动恢复、首页 200、`reboot_required` 清除。cutover 顺序见 `ohmywod-ops/docs/apply-bootstart.md`（先停手动实例再交 systemd，避免抢端口）。

### 2. 固化 Redis —— ✅

线上确认（参考命令）：

```bash
redis-cli -p 6379 CONFIG GET appendonly appendfsync bind protected-mode
redis-cli -p 6379 INFO persistence | grep -E 'aof_enabled|aof_last_bgrewrite_status'
```

结果：`aof_enabled:1`、`appendfsync everysec`、两个 redis 均只监听 loopback。

### 3. JuiceFS `--backup-meta` —— ✅

role `juicefs` 的 unit：`juicefs mount redis://localhost:6379/2 /mnt/jfs --backup-meta 1h`（去掉原来的 `-d`，前台交 systemd 管；`After=ohmywod-supervisord`）。

### 4. Litestream 备份 SQLite —— ✅

role `litestream`：装 v0.3.13 .deb、SQLite 切 WAL（幂等）、渲染 `/etc/litestream.yml`（sops 注入 key，`no_log`）、持续复制到 Linode OS。

参考/验收命令：

```bash
litestream snapshots -config /etc/litestream.yml /data/ohmywod/ohmywod_d.sqlite
litestream restore -config /etc/litestream.yml -o /tmp/t.sqlite /data/ohmywod/ohmywod_d.sqlite
```

已做过一次 restore 演练：恢复库行数与线上一致（report 13462）。

### 5. restic 过渡备份 —— ❌ 已砍（2026-07-12）

不做。原意图是归一化完成前备份 `/data/ohmywod/report` 本地实体 + `/mnt/extra-report` 块存储卷。评估后决定：归一化进 JuiceFS 后战报靠 bucket 对象持久性 + JuiceFS 元数据备份兜底，接受"无独立防误删备份"风险（误删概率低 + 计划对写丢失容忍度高）。详见 ha-plan.md "restic 决策"。若日后不安，补救是周期性 `juicefs sync` 到第二 bucket。

### 6. LDAP 每日 dump —— ❌ 已砍（2026-07-12）

不做。阶段 2 就把 LDAP 收编进 SQLite 退役，为过渡窗口单建 `slapcat` dump 不值当。**已知缺口**：阶段 2 cutover 前，OpenLDAP 账号无异地备份，此窗口内整机损坏会丢账号（SQLite/Litestream 尚未覆盖账号）；接受此风险，靠尽快推进阶段 2。

### 7. 监控 —— ✅

UptimeRobot 已监控 `https://wod.everbird.me/healthz`。Healthchecks.io 已为备份链路建立独立 check：Litestream 巡检与 JuiceFS meta dump 巡检各一条，生产侧由 `ohmywod-ops` 的 monitoring role 渲染脚本与 systemd timer 负责定时 ping。职责边界保持不变：UptimeRobot 看“站点现在是否可用”，Healthchecks 看“备份/巡检任务是否按时回报”。

### 8. Cloud Firewall —— ✅

Linode 防火墙 `ohmywod` 已启用并收口：入站默认 Drop，80/443 仅放行 Cloudflare IP 段，389(slapd)/8013(gunicorn) 不对公网开放；SSH 仍是管理入口，配合已完成的关密码登录/root 仅 key 使用。80/443 收窄后，应用侧读取 `CF-Connecting-IP` 做限流/日志归因才有可信边界。

## 阶段 0 完成定义（勾选）

- [x] 私有配置仓库能复现服务配置（Ansible + molecule）
- [x] Redis AOF ✅ · JuiceFS `--backup-meta` ✅ · Litestream ✅
- [x] restic ❌ 已砍、LDAP dump ❌ 已砍（均 2026-07-12，见上）；Litestream/JuiceFS meta 巡检已接 Healthchecks 心跳
- [x] UptimeRobot 监控 `/healthz`
- [x] SQLite restore 抽样验证
- [x] Cloud Firewall 已收口：389/8013 已挡，80/443 已收窄到 CF 段
- [x] （额外）SSH 加固、开机自启已上并真实重启验证
