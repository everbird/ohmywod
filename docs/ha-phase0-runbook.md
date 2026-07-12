# HA 阶段 0 执行手册（2026-07）

本手册对应 `ha-plan.md` 的“阶段 0：单机加固”。目标：把单机从“坏了才知道、靠手工记忆恢复”推进到“有持续备份、有监控、有可复现配置、有恢复演练”。

**执行方式（2026-07-12 起）**：配置管理已从 bash 一键脚本转为 **Ansible**（`ohmywod-ops/ansible/`）。每个 role 先过 **molecule**（Docker + systemd 容器，本地验证 converge/幂等/断言）再对生产 `ansible-playbook site.yml` 收敛；密钥用 **sops+age**，由 **community.sops** vars 插件消费（非 ansible-vault）。**执行细节以 `ohmywod-ops` 为准，本文只跟踪阶段 0 各项状态**；下方保留的 bash 命令仅作参考/验收用。

## 状态一览（2026-07-12）

| # | 项 | 状态 | 落地 / 备注 |
|---|---|---|---|
| 1 | 私有配置仓库 + 可复现部署 | ✅ 骨架完成 | `ohmywod-ops`，Ansible roles + molecule |
| + | SSH 加固（关密码登录、root 仅 key） | ✅ 已上并验证 | role `ssh_hardening`（体检新发现，原计划未列）|
| + | 开机自启（supervisord+juicefs → systemd） | ✅ 已上，**真实重启验证** | roles `supervisord`/`juicefs`（修“重启=停机”，原计划未识别）|
| 2 | 固化 Redis（AOF / loopback） | ✅ 线上确认 | 运行态与模板一致 |
| 3 | JuiceFS `--backup-meta 1h` | ✅ 已上 | role `juicefs`，进程 cmdline 确认 |
| 4 | Litestream 备份 SQLite | ✅ 已上，**restore 演练过** | role `litestream` → Linode OS `ohmywod-backups`(jp-tyo-1)，已切 WAL |
| 5 | restic 过渡备份（战报文件 / 块存储卷） | ⬜ 待做 | 复用同 bucket 不同前缀 |
| 6 | LDAP 每日 dump | ⬜ 待做 | 阶段 2 退役后消亡 |
| 7 | 监控（UptimeRobot + Healthchecks） | ⬜ 待做 | `/healthz` 需先随 **app role** bump 生产到含该路由的 commit（现跑 `5c92e38`，healthz 404）|
| 8 | Cloud Firewall | 🟡 部分 | 防火墙已存在、默认 Drop、放行 80/443/22 → **389/8013 已挡**；待办：80/443 收窄到 CF 段、SSH 限管理 IP（已用关密码登录缓解）|

## 不能进主仓库的内容

以下内容进 `ohmywod-ops`（密钥经 sops 加密），不提交本仓库：

- 真实 `ohmywod/local_config.py`、`.env`、Redis 密码、Cloudflare/Linode/S3/Resend token。
- nginx server block、certbot/Cloudflare DNS token、JuiceFS secret key、Litestream/restic repository password、对象存储 access/secret key。
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

### 5. restic 过渡备份 —— ⬜ 待做

阶段 1 存储归一化前备份 `/data/ohmywod/report` 本地实体 + `/mnt/extra-report` 块存储卷（不备份 JuiceFS 对象块本身，它由对象存储 + metadata backup 兜底）。可复用 `ohmywod-backups` bucket（不同前缀）。验收：定时运行 + Healthchecks 心跳 + 一次抽样 `restic restore`。

### 6. LDAP 每日 dump —— ⬜ 待做

`slapcat -b "dc=everbird,dc=me"` 每日导出进 restic / 加密 bucket。阶段 2 退役 LDAP 后删除。

### 7. 监控 —— ⬜ 待做

UptimeRobot 盯 `https://wod.everbird.me/healthz`；Healthchecks.io 每条备份任务（Litestream 巡检、restic、LDAP dump、JuiceFS meta）一条独立 check。**前置**：生产 bump 到含 `/healthz` 的 commit（app role）——现跑 `5c92e38` 早于该路由，直接监控会一直 404。

### 8. Cloud Firewall —— 🟡 部分

现状（浏览器核实）：Linode 防火墙 `ohmywod` 已启用、**入站默认 Drop**、仅放行 80/443/22 → 389(slapd)/8013(gunicorn) 从公网已挡住。
待办：80/443 源收窄到 **Cloudflare IP 段**（也是限流信任 `CF-Connecting-IP` 的前提）；SSH 22 目前对全网开放（已用关密码登录缓解，可选再按固定管理 IP 收窄）。

## 阶段 0 完成定义（勾选）

- [x] 私有配置仓库能复现服务配置（Ansible + molecule）
- [x] Redis AOF ✅ · JuiceFS `--backup-meta` ✅ · Litestream ✅
- [ ] restic、LDAP dump 待做；各备份接 Healthchecks 心跳待做
- [ ] UptimeRobot 监控 `/healthz`（待 app role bump 生产版本）
- [x] SQLite restore 抽样验证；[ ] restic restore 待做
- [~] Cloud Firewall 已挡 389/8013；[ ] 80/443 收窄到 CF 段待做
- [x] （额外）SSH 加固、开机自启已上并真实重启验证
