# HA 阶段 0 执行手册（2026-07）

本手册对应 `ha-plan.md` 的“阶段 0：单机加固”。目标是在不增加第二台机器的前提下，把当前单机从“坏了才知道、靠手工记忆恢复”推进到“有持续备份、有监控、有可复现配置、有恢复演练”。

## 当前仓库侧已完成

- `configs/templates/redis-store.conf.template` 已开启 `appendonly yes` 和 `appendfsync everysec`，并限制 `bind 127.0.0.1 -::1` + `protected-mode yes`。
- 应用已提供 `/healthz`，检查 SQLite、Redis 和配置中的存储挂载路径；UptimeRobot 应监控这个端点而不是首页。
- SQLite 连接已配置 5 秒 timeout，作为 Litestream/WAL 的应用侧配套。

## 不能进主仓库的内容

以下内容应进入私有配置仓库，不要提交到本仓库：

- 真实 `ohmywod/local_config.py`、`.env`、Redis 密码、Cloudflare/Linode/S3/Resend token。
- nginx server block、certbot/Cloudflare DNS token、JuiceFS secret key、Litestream/restic repository password。
- age 私钥。私钥只放密码管理器；私有配置仓库只放 sops 加密后的 secrets。

## 执行顺序

### 1. 建私有配置仓库骨架 —— 已完成（`ohmywod-ops`）

私有仓库 `ohmywod-ops`（github.com/everbird/ohmywod-ops）已建并搭好骨架。当前结构：

```text
ohmywod-ops/
  .sops.yaml                     age 公钥 + 加密规则
  secrets/
    secrets.env.example          schema（无真值）
    secrets.env.enc              sops 密文（明文与 age 私钥不入库）
  deploy/
    deploy.sh                    裸机 → 服务就绪主脚本
    bootstrap.sh                 apt 系统依赖
    templates/ohmywod_local_config.py.tmpl   继承主仓库 config.py，只覆盖 4 个密钥
  systemd/                       juicefs(--backup-meta) / litestream / restic / ldap-dump units+timers
  nginx/wod.everbird.me.conf
  litestream/litestream.yml
  restic/restic.env.tmpl
  scripts/                       backup-restic / backup-ldap / restore-smoke / switchover(阶段3)
  firewall/cloud-firewall.md
  docs/recovery.md
```

**设计要点**：主仓库 `ohmywod/config.py` 是生产非密钥真值的唯一来源；生产 `ohmywod/local_config.py` 由 `deploy.sh` 渲染 = 继承 `config.py` + 只填 4 个密钥。`deploy.sh` clone 主仓库 `@APP_REF`（固定 commit，非 submodule）拼接两仓。

**尚待收尾**：骨架里标 `# CONFIRM:` 处的值来自 docs 而非生产实测，首次部署前需逐条核对（尤以生产当前 `local_config.py` 实际内容、nginx `-T` 导出、JuiceFS 挂载来源为准）。

验收标准：从一台裸 Ubuntu 24.04 机器开始，至少能按 README 复制出当前生产的 nginx、supervisord、redis、JuiceFS、应用配置。

### 2. 固化 Redis 配置

主仓库模板已经包含 AOF 和本地 bind。线上要确认运行态和模板一致：

```bash
redis-cli -p 6379 CONFIG GET appendonly appendfsync bind protected-mode
redis-cli -p 6379 INFO persistence | grep -E 'aof_enabled|aof_last_bgrewrite_status|aof_last_write_status'
redis-cli -p 7379 CONFIG GET bind protected-mode maxmemory
```

验收标准：`redis-store` 显示 `aof_enabled:1`，`appendfsync everysec`，只监听 loopback。把最终 conf 放入私有配置仓库。

### 3. 开 JuiceFS metadata 备份

线上当前待办是给 JuiceFS mount 显式加 `--backup-meta 1h`。步骤建议：

1. 找到当前挂载来源：`systemctl cat <juicefs-unit>` 或查看 fstab/supervisord/手工启动记录。
2. 在私有配置仓库的 unit/template 中加入 `--backup-meta 1h`。
3. 低峰期重挂载 JuiceFS。
4. 验证挂载恢复后，打开几个老战报、上传一个小测试战报，再删除测试数据。
5. 确认 bucket 里开始出现 metadata backup 文件。

回滚：恢复旧 unit/template，重挂载到原参数。该步骤不迁移数据，只改变定时 metadata dump。

### 4. 接 Litestream 备份 SQLite

建议先把 SQLite 切到 WAL，再启动 Litestream 持续复制到 Linode Object Storage。

验证命令示例：

```bash
sqlite3 /data/ohmywod/ohmywod_d.sqlite 'PRAGMA journal_mode; PRAGMA busy_timeout;'
litestream replicate -config /etc/litestream.yml
litestream snapshots -config /etc/litestream.yml /data/ohmywod/ohmywod_d.sqlite
```

验收标准：

- `journal_mode` 为 `wal`。
- Litestream 有最新 snapshot/generation。
- 在临时目录 restore 一份库并能打开查询。

回滚：停止 Litestream 不影响应用；如 WAL 切换后异常，低峰期停应用并按 SQLite 官方流程切回 DELETE journal。

### 5. 接 restic 过渡备份

阶段 1 存储归一化前，仍需备份：

- `/data/ohmywod/report` 本地实体文件。
- `/mnt/extra-report` 块存储卷内容。

不需要备份 JuiceFS 对象块本身；它会迁到 Linode Object Storage，并由 JuiceFS metadata backup 兜底。

验收标准：restic backup 定时运行，Healthchecks.io 能看到成功心跳，且完成一次 `restic restore --target /tmp/ohmywod-restore-test latest` 抽样验证。

### 6. 接 LDAP 过渡备份

LDAP 退役前，每日导出：

```bash
slapcat -b "dc=everbird,dc=me" > ldap-$(date +%F).ldif
```

导出的 LDIF 进 restic 或加密 bucket，不进主仓库。阶段 2 退役 LDAP 后删除这条备份任务。

### 7. 接监控

- UptimeRobot 监控：`https://wod.everbird.me/healthz`。
- Healthchecks.io：每个 cron 或 systemd timer 一条独立 check，包括 Litestream 备份巡检、restic、LDAP dump、JuiceFS metadata 备份检查。

验收标准：手动停掉一个非破坏性依赖或临时指向不存在的 storage path 时，`/healthz` 返回 503；恢复后回到 200。

### 8. Linode Cloud Firewall

Cloudflare 橙云代理已经启用后，源站入站应限制为：

- HTTP/HTTPS：只允许 Cloudflare IP 段。
- SSH：只允许你的固定管理 IP 或临时手动开放。
- Redis、supervisord、JuiceFS metadata Redis：不对公网开放。

验收标准：公网无法直接访问源站 IP 的 80/443；Cloudflare 域名访问正常。

## 阶段 0 完成定义

- 私有配置仓库能复现当前服务配置。
- Redis AOF、JuiceFS `--backup-meta`、Litestream、restic、LDAP dump 都有监控心跳。
- UptimeRobot 监控 `/healthz`。
- 至少做过一次 SQLite restore 和 restic restore 抽样验证。
- Cloud Firewall 已限制源站入口。
