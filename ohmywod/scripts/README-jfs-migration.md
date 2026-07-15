# 战报统一进 JuiceFS(<owner>/<category>/<report>)运行手册

**目标终态**：所有战报都在 `/mnt/jfs/reports/<owner>/<category>/<report>`（JuiceFS 管理、后端已在 Linode OS）；
app 的 `DATA_DIR` 指向它，**新上传解压直接落 JuiceFS→自动到 Linode**，从此不再需要迁移脚本。

## 现状（2026-07-14 生产实测）
- `/mnt/jfs/reports/<category>/<report>`：107 个「扁平」category（早期迁移丢了 owner 层）+ `test.log` 杂物。
- `/data/ohmywod/report/<owner>/<category>`：226 个真实 owner 目录未迁（~6.2GB）；内部 category 有真实(未迁)也有软链(已进 jfs)。
- `/mnt/extra-report/extra/report/<owner>`：34 个 owner 曾迁到本地块设备，其 category 有的软链去了 jfs。
- **owner 归属判据**：`/data|extra` 里 `<owner>/<category>` 是「指向 jfs 的软链」⇒ 该 jfs category 归此 owner；
  同名「真实目录」是另一个 owner 的独立战报。实测 107/107 唯一、0 冲突（连 `常规` 都自动定为 Masuo）。

## 脚本
| 脚本 | 作用 | 开销 |
|---|---|---|
| `jfs-report-owner-backfill.sh` | 步骤1：`mv` 扁平 category → `<owner>/<category>`（JuiceFS 内 mv=纯元数据，**零数据传输**）+ repoint 软链 + 删杂物 | 极低 |
| `jfs-report-migrate-remaining.sh` | 步骤2+3：`rsync` 未迁的真实目录 category → jfs（幂等续跑，**不动 /data 原件**） | ~6.2GB 写 Linode |

两个都支持 `--dry-run`，务必先干跑审阅。

## 执行顺序
```bash
cd /var/ohmywod/src/ohmywod/scripts     # 生产上

# 1) 归位：先干跑看所有 mv/repoint 动作
bash jfs-report-owner-backfill.sh --dry-run
bash jfs-report-owner-backfill.sh --purge-junk      # 真跑（含删 test.log）

# 2) 存量迁移：先干跑（会用 rsync --dry-run 列将传的文件）
bash jfs-report-migrate-remaining.sh --dry-run
bash jfs-report-migrate-remaining.sh                 # 真跑；可随时中断续跑
#    也可单 owner 试点： --owner <name>

# 3) 校验：此时 /mnt/jfs/reports/<owner>/<category>/<report> 应覆盖全部战报
#    抽查若干 owner 的战报能在 jfs 下读到；对比 /data 里对应 owner 的 category 数

# 4) 切 DATA_DIR（见下），重启，验证站点浏览/上传；/data 原件留几天回滚
```

## 步骤4：把 DATA_DIR 指向 JuiceFS
`DATA_DIR` 现值 `/data/ohmywod/report`。改为 **`/mnt/jfs/reports`**：
- 生效位置：运维仓 `ohmywod-ops` 的 app role 模板 `ansible/roles/app/templates/ohmywod_local_config.py.j2`
  里 `DATA_DIR = "/mnt/jfs/reports"`（local_config 覆盖 config.py），随后 `ansible-playbook site.yml --tags app` 应用并重启 web。
- `UPLOAD_DIR` **保持本地** `/data/ohmywod/upload`（临时 zip，无需进 jfs；磁盘用量检查也对它做）。
- 生效后 `upload.py` 解压路径 `DATA_DIR/<owner>/<category>/<report>` 即写进 JuiceFS→Linode。

**性能提示**：解压是很多小文件写 FUSE。当前挂载未开 `--writeback`（同步写 Linode，较慢但最稳）。
若上传明显变慢，可在 juicefs role 的 unit 加 `--writeback`（本地缓存先落、异步上传，代价是崩溃时未上传部分有风险）。

## 回滚
- 步骤1/2 只新增/repoint，不删 /data 原件；切 DATA_DIR 前站点始终读 /data，随时可停。
- 切 DATA_DIR 后若有问题，改回 `/data/ohmywod/report` 重新 apply 即回退（原件还在）。

## 清理旧脚本（本次一并处理）
`migrate-report-to-s3.sh` / `migrate-uname-report.sh` / `migrate-top-unames.sh` 已被本套取代，应删除。
其中 **`migrate-report-to-s3.sh` 第 17 行硬编码了 AWS secret 明文**（key `AKIASBWFRLK3W4KELEPN` 已停用）——
删文件并注意该密钥仍在 git 历史里，敏感度已随停用降低，但删除文件是应有的卫生。

## 明文镜像（rstore/reports/）——已于 2026-07-15 删除
旧流程曾用 `juicefs sync` 往桶 `ohmywod-reports` 的 `rstore/reports/` 前缀存了一份约 87.5GiB 明文可读镜像
（当初误以为需手动 sync 而意外产生的额外开销）。本套不再维护它，**已删除**（94,984 个对象，0 错误）。

删除后桶 `ohmywod-reports` 只剩 JuiceFS 自身数据：`rstore/chunks/`（块）、`rstore/meta/`（`--backup-meta` 元数据 dump）、
`rstore/juicefs_uuid`（卷身份）。**注意**：chunks 离开 redis 元数据（db2, 卷 rstore）即无意义；镜像删除后无独立的
人可读副本，元数据保险仅剩 `rstore/meta/` 的 dump（见 ha-plan.md 已接受此风险）。
如日后想再要一份可读备份，需另写指向 Linode 的定期 `juicefs sync` 任务（不要用旧脚本里的 AWS 硬编码）。
