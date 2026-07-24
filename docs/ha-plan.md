---
document_id: ohmywod-single-node-dr-plan
schema_version: 3
document_status: active
source_of_truth_for: "单机快速重建与节点替换：目标体验、必要步骤、当前下一步"
language: zh-CN
created_at: "2026-07-05"
last_updated: "2026-07-23"
---

# 单机 DR：快速重建与节点替换

> 个人兴趣项目。目标不是工业级 HA，而是：**一条命令自动起一台装好数据的新机，做一次简单验证，再一条命令把生产切过去。**
> 不追求漂亮的 RPO/RTO 数字，只求少人肉、流程短到自己能完全掌控。

## 1. 为什么可以很简单

- **战报在共享对象存储**（JuiceFS 对象桶）。新机 load metadata + 补凭据后读的是同一批文件，**不需要拷贝战报**。
- **SQLite 由 Litestream 持续复制**到备份桶。新机 `litestream restore` 即可，数据落后以秒计。
- **主机配置全在 Ansible**（`site.yml`）。空白 Ubuntu 一把幂等收敛；密钥在 sops，控制机直接用，不做二次加密传递。
- **唯一硬约束：同一时刻只能有一个写者。** 两台机同时向同一备份桶 / 对象桶写会分叉。所以新机在切换前不启动
  Litestream、不接公网流量——没有流量就没有写入。守住这一条，其余安全门都可以省。

## 2. 明确不做（这是之前失控的来源，一律去掉）

- 不建常驻温备、双机复制、自动 failover、NodeBalancer、多活。
- 不做候选机只读演练挂载、独立 drill inventory、强制重启复验、逐层哈希证据、三步 age 凭据仪式、逐层 RPO/RTO 证明。
- 不做请求排空、事务级一致切换、自动回滚、把新机写入合并回旧机。切换瞬间正在处理的请求可以失败。

接受的风险（与站点体量相称，真出事或成本明显下降再重估）：

- 旧机彻底死时，SQLite 回到 Litestream 最新点、JuiceFS 回到最近一次 metadata dump，可能丢几秒到一次备份间隔的数据。
- 战报没有第二桶或不可变副本，不防供应商账号级事故和超窗口误删。
- 切换后旧机不再自动追平；需要回退时手动把 DNS 改回旧机。

## 3. 目标命令（待在私有 `ohmywod-ops` 仓实现）

```bash
./scripts/dr-node build              # 自动起一台装好数据、已自检通过的新机（不接公网）
./scripts/dr-node cutover <new-ip>   # 一次确认，把生产切到新机
./scripts/dr-node cleanup <old-id>   # 稳定观察后，单独删旧机
```

正常路径不需要 SSH 进新机、编辑 inventory、开云控制台或逐条跑 Ansible。排错时才看脚本生成的临时 inventory 和日志。

## 4. `build`：自动起一台可接管的新机

一条命令顺序完成，任何一步失败都不碰生产 DNS / 旧机，只删掉本次新建的机器（`--keep-on-failure` 可保留现场）：

1. 用 sops 里的 Linode token 建一台 Ubuntu 24.04，注入 SSH key、绑 Cloud Firewall，等 SSH 通。
2. 生成临时 inventory，`site.yml -e deploy_phase=prepare`：装好全部服务但都不启动（OPS-001 闸门，数据没恢复不上线）。
3. 恢复数据：`litestream restore` 拉回 SQLite；找对象桶里最新 metadata dump 做 `juicefs load`，由 Ansible `no_log`
   补回对象凭据，挂 `/mnt/jfs`。
4. 启动服务用于自检，但**不启动 Litestream 和监控上报**（避免与旧机争同一备份桶）。
5. **必要验证只有一项**：把域名临时解析到新机 IP（`curl --resolve`），`/healthz` 与一个真实战报页都返回 200。
   `/healthz` 本身已检查 SQLite、Redis、`/mnt/jfs`，战报页又实际读了一次对象存储——这两个绿就够。
6. 打印新机 IP、SQLite 恢复点，和下一条 `cutover` 命令。

## 5. `cutover`：一次确认，四个动作

先显示旧机、新机、恢复点，只问一次 `Replace <old> with <new>? [yes/no]`。确认后：

1. **停旧机写者**：停旧机 nginx、web、Litestream（不等在途请求）。旧机已死则跳过。
2. **追平一次**：旧机可达时，在新机再跑一次 `litestream restore` 补上最后几秒，然后在新机启动 Litestream
   （此刻它是唯一写者）。旧机已死则沿用 `build` 的恢复点。
3. **改入口**：把 Cloudflare A 记录从旧机 IP 改到新机，确认 Cloud Firewall 已绑新机。
4. **看结果**：走公网请求 `/healthz` 和一个战报页，确认流量已在新机。

不自动回滚、不合并数据、不自动删旧机。任一步失败就停下、保留现场，由你决定修新机还是回退旧机（把 A 记录改回去）。

## 6. 实现顺序

- **DR-1（下一步）**：实现 `dr-node build`，复用现有 roles / Litestream / JuiceFS，删掉正常路径里的人工 inventory、
  age 凭据仪式和只读 drill mount。完成标准：一条命令从空白云资源得到自检通过、不接公网的新机。
- **DR-2**：实现 `dr-node cutover`（上面四步）+ `cleanup` 独立删机。完成标准：除一次 `yes` 外不需 dashboard / SSH。
- **DR-3**：用临时 Linode 真跑一次 `build`，低峰真跑一次 `cutover`，记录实际耗时和恢复点，只修挡住正常路径的问题。

## 7. 现有可复用基础

Ansible 能把空白 Ubuntu 收敛到运行态；SQLite WAL + Litestream 在跑；JuiceFS metadata 已能从对象桶 load、
对象端真实文件已读到；2026-07-22 已在临时 Linode 恢复出与生产一致的 SQLite；Cloudflare / Linode / 对象存储 /
应用密钥都有 sops 真值；nginx 已受 JuiceFS 挂载闸门保护。

旧的 HA-001..010、OPS 波次、age secret-delivery 与演练细节留在 Git 历史与私有 ops 文档中，作为调查记录，不是当前待办。
