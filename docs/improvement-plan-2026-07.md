# 站点改进方案（2026-07）

基于对代码库的通读整理，覆盖广告方案（见 `ad-optimization-plan-2026-07.md`）之外的改进方向，按优先级排序。

**2026-07-06 更新**：第 1 项、第 2 项、第 4 项的应用侧 `SQLALCHEMY_ENGINE_OPTIONS`/gunicorn 清理、第 6 项 `/healthz` 已落地；HA 阶段 0 的执行细节已拆到 [ha-phase0-runbook.md](ha-phase0-runbook.md)。

**2026-07-05 更新**：对照 [ha-plan.md](ha-plan.md) 重新梳理。原第 6 项（备份/监控）大部分被 HA 阶段 0 吸收，第 3 项（限流）改为搭 HA 阶段 2 的车，第 4 项（WAL）从可选优化升级为 Litestream 的前置配套，新增第 8 项（存储归一化的代码侧配套）。与 HA 计划有依赖关系的项都标注了对应阶段。

## 1. 安全：`report_raw` 把用户上传的 HTML 同源直出（最高优先）

**现状**：`ohmywod/views/report.py` 的 `report_raw` 把上传 zip 里的 HTML 原样以 `text/html` 返回（只做了 `http:`→`https:` 替换，不做任何清洗），且挂在主域名同源下。阅读模式有一整套精心写的 `sanitize_wod_report`（白名单 onclick/onmouseover、lxml Cleaner），但 raw 路由完全绕过了这些——它不只是 iframe 的内部后端，任何人都可以直接访问这个 URL。

**风险**：注册是开放的，任何用户都能上传含任意 JS 的 zip，得到一个挂在主域名下的存储型 XSS 页面。session cookie 有 HttpOnly 保护，但同源 JS 依然能以受害者身份读页面拿 CSRF token、发起改资料/删战报等请求。

**方案**（改动很小）：给 `report_raw` 的响应加一个头：

```python
resp.headers['Content-Security-Policy'] = "sandbox allow-scripts allow-popups"
```

CSP `sandbox` 让浏览器把该响应当作**独立不透明源**——报告里的 JS（wodToolTip 那些）照常运行，但拿不到主站 cookie、localStorage，也无法以用户身份发同源请求。iframe 展示不受影响。比拆独立子域名便宜得多，效果等价。

**验证点**：老战报的交互（tooltip、页内跳转）在 sandbox 下是否正常；`allow-popups`/`allow-forms` 按需增减。

## 2. 会 500 或数据漂移的小 bug（便宜，顺手修）

- **`new_category` 缺 `@login_required`**（`views/report.py`）：匿名用户 POST 时 `validate_name` 里的 `current_user.username` 直接 AttributeError 500；GET 也不该对匿名开放。同文件其他写操作都有这个装饰器，只有这一个漏了。
- **`report_reader` 不检查 report 是否存在**：`rc.get_report(report_id)` 返回 None 时下一行 `report.owner` 直接 500，应该 404。`view_report` 有个小变体：在 `if not report: abort(404)` **之前**就构造了 presenter。
- **点赞/收藏计数会漂移**：`rc.like()` 用 Redis `sadd`，重复点赞返回 0，但 `incr_likes_cnt` 无条件执行——双击或重放请求就能刷计数（unlike 同理能刷成负数）。改成只在 `sadd`/`srem` 返回 1 时才增减计数。
- **`print` 当日志用**（`app.py` 的 `load_user`、`views/frontend.py` 的 `validate_old_password`）：迁移记录里"登录成功又被弹回、零报错日志"那个坑，排查困难的根因恰恰是 `load_user` 里 `except: print()` 吞异常。改成 `current_app.logger.exception(...)`。注：这两处都是 LDAP 相关代码，HA 阶段 2（LDAP 退役）会整个重写——但阶段 2 排期在存储迁移之后，过渡期内 LDAP 排障还得靠日志，一行的修改现在就做。
- **补 404/500 `errorhandler` 页面**：现在全站没有任何 errorhandler，500 时用户看到 Werkzeug 裸页。

## 3. 防滥用：开放注册 + 反馈表单零限流（搭 HA 阶段 2 的车）

**现状**：`/register` 直接创建账号（现走 LDAP，HA 阶段 2 后进 SQLite），`/feedback` 直接入库，都没有频率限制或人机验证，全站没有限流组件。

**为什么**：广告方案上线后是主动希望流量涨的，流量涨了爬虫和 spam 一定跟着来。

**方案**：HA 计划附录 A 已定稿 Flask-Limiter（redis-cache 存储、按 `CF-Connecting-IP` + 用户名限速）用于登录防爆破，**不要单独引入第二套限流**，在阶段 2 落地 Flask-Limiter 时把覆盖面从 `/login` 扩到 `/register`、`/feedback`、点赞收藏这几个 POST 端点即可。Cloudflare 免费 rate limiting rule 同理可以多建一条罩住 `/register`。注册表单加蜜罐字段（隐藏 input，有值即拒），成本几乎为零，不打扰真人。

**如果阶段 2 排期太远而 spam 先来了**：单独提前 Flask-Limiter 这一小步（不用等 LDAP 退役），它对认证后端没有依赖。

**关于取真实 IP**：不必上 nginx realip 模块——限流 key 直接读 `CF-Connecting-IP` 头即可（HA 附录 A 的做法）。前提是这个头可信：HA 阶段 0 已把 Linode Cloud Firewall 入站 80/443 收窄到 Cloudflare IP 段，头不可伪造的边界已经满足。**这两件事要一起看**：Cloud Firewall 不只是安全兜底，也是限流生效的前提。nginx 日志想看真实 IP 再考虑 realip，属可选。

## 4. SQLite 并发：开 WAL（一行配置，且是 Litestream 的配套）

**现状**：gunicorn 是 4 个 sync worker，SQLite 默认 journal 模式下写锁整库互斥。点赞/浏览计数走 Redis 没事，但收藏、上传建报告、编辑这些写路径并发时会开始出现 `database is locked`。

**与 HA 计划的关系**（这项的分量因此变了）：
- HA 阶段 0 的 Litestream 就是靠持续读 WAL 工作的——接入时会把库切到 WAL 模式。所以 WAL 不再是"可选优化"，而是阶段 0 的必然结果；应用侧要**配套**在 `SQLALCHEMY_ENGINE_OPTIONS` / engine connect 事件里设 `busy_timeout`（Litestream 自身长期持有读锁，没有 busy_timeout 的写入会更容易直接报锁）。
- HA 阶段 2 LDAP 退役后，登录校验、找回密码、session 吊销全压进 SQLite，读写量上一个台阶，WAL + busy_timeout 是前提而不是锦上添花。

**方案**：应用侧设 `busy_timeout`（约 5s）+ 确认 WAL 生效即可，WAL 切换本身交给 Litestream 接入时统一做，避免两处各切一次。

顺带：`gunicorn_config.py` 里的 `debug = True` 在 gunicorn 19+ 已不是合法配置项（被忽略），可删掉避免误导。

## 5. SEO：广告方案的"分子"（与广告方案直接协同）

**现状**：`base.html`/`report_details.html` 没有 meta description、Open Graph 标签、canonical，全站没有 sitemap.xml（robots.txt 有）。而 `view_report`、`view_category`、搜索页都是公开可爬的。

**为什么**：广告方案优化的是单页 RPM（分母侧），但 coverage/impression 的天花板是流量本身。战报详情页有现成的结构化数据（`ReportDetails` 的副本名、服务器、职业等一堆字段）却完全没喂给搜索引擎。

**方案**：
- `report_details.html` 加 `<meta name="description">`（用 report.description 截断）+ OG 标签（title/description/url）。
- 加 `/sitemap.xml` 路由，从 `Report.query.filter(status==None)` 生成，纯模板渲染，几十行的事。
- 每页 `<title>` 没按页面区分的补上战报名。

## 6. 运维：`/healthz` 路由（备份/监控已并入 HA 计划）

本项原本的主体（备份自动化、uptime 监控）已被 HA 计划阶段 0 完整覆盖且方案更好（Litestream 秒级 RPO 替代 cron `.backup`、Healthchecks.io、UptimeRobot），**以 ha-plan.md 为准，此处不再重复**。

代码侧已完成：

- **`/healthz` 路由已落地**（检查 db、redis、数据挂载点可达），UptimeRobot 应监控这个端点而不是首页。理由：首页不触碰数据目录（`disk_info` 那段有缓存且全 try/except 包着），JuiceFS 挂载悄悄掉线时首页照常 200，UptimeRobot 看不出异常——而代码里到处在防御挂载掉线，说明这是真实发生过的故障模式。HA 阶段 3 的切换脚本里的"冒烟检查"也可以直接复用这个端点。

## 7. 低优先级 / 顺手清理

- **搜索是 `LIKE %q%` 全表扫**（`controllers/report.py` 的 `search`）：数据量小时无所谓，慢了再上 SQLite FTS5。另外 `models/report.py` 的 `ReportQuery.search` 是无人调用的死代码（真正的搜索在 controller 里），可删。
- **CI 缺失**：`tests/` 有 584 行测试但没有任何 CI 配置。加个跑 `make test` 的 GitHub Actions，十几行 YAML，防住下次依赖升级这类大动作的回归。
- **`report_raw` 无 HTTP 缓存**：每次请求都从 JuiceFS（S3 后端）整读文件再做字符串替换。战报基本不可变，加 `Cache-Control`/ETag 能省 S3 读取和响应时间。HA 计划的存储归一化落地后**所有**战报读取都走 JuiceFS，这项的收益会变大（JuiceFS 本地 cache 能挡一部分，但省掉的是整条请求路径）。

## 8. 存储归一化的代码侧配套（依赖 HA 阶段 1）

ha-plan 的存储归一化说"`DISK_USAGE_THRESHOLD` 溢出逻辑和三处软链接的复杂度全部消亡"，但没有列出对应的代码任务。归一化做完后代码侧要跟着清理，否则死代码和误导性的容量面板会留下来：

- `app.py` 的 `inject_disk_usage` 上下文处理器：硬编码 `/mnt/extra-report` 的那整段 `extra` 逻辑删掉；根盘统计的语义也变了（数据不在本地盘），面板改成以 JuiceFS 用量为主。
- `views/upload.py` 的上传前磁盘检查：`shutil.disk_usage(UPLOAD_DIR)` 针对的是本地盘写满的场景，归一化后 DATA_DIR 在 JuiceFS 上近乎不会满，这段检查要么删、要么改成检查 JuiceFS 侧配额。
- `templates/usage.html` 里对应的展示块。
- `ohmywod/scripts/` 下的三个 migrate-*.sh 是软链接时代的产物，归一化后归档。

单独列出来的原因：这些改动必须**跟着阶段 1 的存储操作同步上线**（面板读不存在的挂载点虽然有防御不会炸，但会常年显示 unavailable 误导人），属于 HA 计划里容易漏掉的应用侧尾巴。

## 实施顺序建议（对齐 HA 阶段后更新）

1. 第 1 项（CSP sandbox，一行头）+ 第 2 项（bug 修复）——已完成。
2. 第 5 项（SEO）赶在广告方案上线前后完成——主体已完成，剩余可继续补页面级细节。
3. 第 4 项的应用侧 `busy_timeout` + 第 6 项 `/healthz` 已完成；WAL 切换随 HA 阶段 0 的 Litestream 接入一起上。
4. 第 3 项（限流）搭 HA 阶段 2 的 Flask-Limiter 一起做；spam 先来了就单独提前。
5. 第 8 项跟着 HA 阶段 1 的存储归一化同步上线。
6. 第 7 项其余内容有空再说。
