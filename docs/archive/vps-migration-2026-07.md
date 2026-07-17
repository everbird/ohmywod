# VPS 迁移记录（2026-07）

从 Linode Nano（CentOS 9，1GB RAM）迁移到新的 Linode Nano（Ubuntu 24.04 LTS），顺带把依赖栈从 Python 3.9 / Flask 2 升级到 Python 3.12 / Flask 3。老机器已下线（保留了几天做回退保险后释放）。

## 为什么迁移

- Python 3.9 已 EOL（2025-10-31），Flask/Werkzeug/Flask-Admin 一系列老版本存在已知 CVE，但直接在老机器上编译新 Python（pyenv）会被 OOM killer 干掉——1GB 内存编译 OpenSSL/`_ctypes` 这类大编译单元扛不住。
- 与其在跑着生产服务的老机器上原地升级冒风险，改为整机搬到新机器，全程验证完再切 DNS，老机器全程不受影响，出问题也不用回滚只需要不切换。

## 最终生产拓扑

| 组件 | 老机器（CentOS 9） | 新机器（Ubuntu 24.04） |
|---|---|---|
| Python | 3.9.13 | 3.12.8（apt 直接装，不用编译） |
| Web 框架 | Flask 2.2.2 / Werkzeug &lt;3.0 / Flask-Admin &lt;2.0 | Flask 3.1 / Werkzeug 3.1 / Flask-Admin 2.2 |
| 反向代理 | Apache/httpd | **nginx**（内存占用更低，且老机器配置本身很简单，翻译成本低） |
| venv 位置 | `/var/ohmywod/venv`（**没有点**，`configs/config.py` 的 `GUNICORN_BIN_PATH` 默认公式决定的） | 同样是 `/var/ohmywod/venv`（保持跟公式一致，没有改公式去迁就本地开发的 `.venv` 习惯） |
| LDAP | 自建 OpenLDAP，suffix `dc=everbird,dc=me` | 同左，LDIF 导出导入迁移 |
| 战报存储 - 本地 | `/data/ohmywod/report` | 同左（rsync 迁移） |
| 战报存储 - JuiceFS | `/mnt/jfs`（S3 后端，元数据在 `redis-store` db 2） | 同左，元数据用 `juicefs dump`/`load` 迁移，S3 数据本身零迁移 |
| 战报存储 - Block Storage | `/mnt/test001`（占位名） | `/mnt/extra-report`（迁移完成后改的名字，见下文） |
| 点赞/浏览计数 | Redis (`redis-store`，`/stats/report/*`) | 同左，`redis-cli --rdb` 快照迁移 |
| DNS | Cloudflare，`wod.everbird.me` 灰云（DNS only） | 迁移后维持灰云，后来又手动切换成**橙云代理 + Full (strict)** |

## 迁移步骤（精简版，最终跑通的顺序）

1. **准备新机器**：apt 装 Python 3.12、nginx、slapd、redis-server（装完立刻 `systemctl disable` 掉，避免跟 supervisord 自己拉起的 `redis-store`/`redis-cache` 抢 6379/7379 端口）。
2. **迁移 LDAP**：`slapcat -b "dc=everbird,dc=me"`（按 suffix 导，不猜数据库序号）→ 传到新机器 → `dpkg-reconfigure slapd` 把默认的 `dc=nodomain` 改成正确后缀 → `slapadd -b "dc=everbird,dc=me"` 导入。**只导了 `data.ldif`（数据树），没导 `config.ldif`（cn=config）**——如果 app 配置的 `LDAP_BIND_USER_DN` 走的是 `olcRootDN`/`olcRootPW` 机制（而不是数据树里一条带 `userPassword` 的普通记录），这个密码就完全没跟着迁移过来，`dpkg-reconfigure` 时随手填的临时密码会成为新机器实际生效的 rootPW，导致服务账号 bind 失败（后续详细排查见下）。
3. **部署代码**：`git clone`（用只读 Deploy Key，不是个人 SSH key）→ 建 venv → `gen.py product` 生成 `supervisord.conf`/redis 配置 → 手动传 `ohmywod/local_config.py`（含真实密钥，不进 git）。
4. **迁移数据**：
   - SQLite：`sqlite3 .backup` + rsync
   - `report/`、`upload/`：rsync（`-a` 默认不解引用软链接，安全）
   - JuiceFS：**先**挂载好验证内容一致，**再** rsync report 目录（软链接指向 `/mnt/jfs`，挂载没起来就是断链）
   - Block Storage 卷：新建同尺寸卷，格式化 ext4，rsync 真实数据
   - Redis 计数：`redis-cli --rdb` 快照，落到 `redis-store` 的 `dir` 下，文件名必须叫 `dump.rdb`（Redis 默认只认这个文件名），且必须在 supervisord **第一次启动前**放好（RDB 只在启动时加载）
5. **nginx + 证书**：DNS-01 challenge（Cloudflare API Token，`Zone:DNS:Edit`，图方便不用等域名先切过去）→ 手写 nginx server block（老机器 Apache 配置里其实有强制跳转，翻译过来保留了同样的行为）。
6. **切换前全链路验证**：本机 hosts 文件临时指向新 IP，把登录/上传/点赞/admin 面板全测一遍，尤其是真实 LDAP 登录（这是唯一没法本地 mock 测的环节）。
7. **切 DNS**：最后一次增量同步 → Cloudflare 改 A 记录 → 老机器停 web 进程。
8. **切换后**：确认没问题，老机器关机留几天做回退保险，稳定后释放。

## 踩过的坑（下次migrate/参考用）

- **`slapcat -n <index>` 不要猜序号**，CentOS/Ubuntu 的 config/monitor/data 数据库编号不一样，直接用 `-b "<suffix>"` 按后缀导最稳。
- **新装的 `slapd` 默认后缀是 `dc=nodomain`**，得先 `dpkg-reconfigure slapd` 配成真实域名，才能 `slapadd` 导入。
- **JuiceFS `dump` 会把 S3 secret key 从导出文件里抹掉**（安全考虑），`load` 完之后必须用 `juicefs config <meta-url> --secret-key ... --force` 补回去，否则 mount 报 `format decrypt: secret was removed`。
- **`GUNICORN_BIN_PATH` 默认公式是 `{VAR_PATH}/{APP_NAME}/venv/bin/gunicorn`**（`venv` 不带点），跟本地开发用的嵌套 `.venv` 习惯不一样——按这个公式建 venv，不要改 `configs/config.py` 去迁就本地习惯（那是两台机器共用的文件，改了可能坑到还在跑的另一台）。
- **apt 装的 `redis-server`/`apache2`/`nginx` 默认会自动启动 systemd 服务**，会跟这个项目自己用 supervisord 拉起的同名/同端口服务冲突，装完记得 `systemctl disable` 关掉不需要的那个。
- **Cloudflare 的 SSL/TLS 模式（Flexible/Full/Full strict）只对"橙云代理"的记录生效**，灰云（DNS only）记录完全不受这个设置影响——排查"为什么证书没变"之类问题时，先确认代理状态，再谈 SSL 模式。
- **Apache 的 `Redirect permanent` 强制跳转 + Cloudflare Flexible 模式会导致无限重定向循环**，但如果记录是灰云直连就不受影响——这条记录当时就是灰云，所以老机器的强制跳转配置本身从来没触发过这个问题。
- **venv 目录不能简单 `mv` 挪位置**，`bin/` 下的脚本 shebang 写死了绝对路径，挪了地方这些脚本就找不到自己的解释器了，需要删了在正确位置重建。
- **本机 gpg-agent 的 `pinentry-program` 配置是从 Mac 同步过来的**（指向不存在的 `/opt/homebrew/bin/pinentry-mac`），导致这台 WSL 机器上 `git commit` 一直卡住等一个永远不会出现的密码输入框，改成 `/usr/bin/pinentry-curses` 后签名本身能跑通，但在这个非交互会话里 gpg 进程签完之后依然不正常退出（怀疑是 `gpg-agent --supervised` 模式的会话/tty 问题），后续都用 `--no-gpg-sign` 绕过。
- **登录成功一瞬间又被弹回登录页，且没有任何报错日志**：根因是 LDAP 服务账号（`LDAP_BIND_USER_DN`，这里是 `cn=admin,dc=everbird,dc=me`）的密码走的是 `olcRootDN`/`olcRootPW`（cn=config 里的配置项），不是数据树里一条带 `userPassword` 的普通记录——迁移时只导入了 `data.ldif`，没导入 `config.ldif`，`dpkg-reconfigure slapd` 时随手填的临时密码就成了新机器实际生效的 rootPW。表现很有迷惑性：用户自己的账号密码登录 (`LDAPLoginForm` 直接拿用户自己的 DN+密码 bind) 完全正常，POST /login 也正确返回 302；但 Flask-Login 每次请求都要用**服务账号**重新查一次用户信息（`load_user` → `get_user_info` → 内部用 `LDAP_BIND_USER_DN`/`PASSWORD` bind），这一步因为 rootPW 不对而失败，`load_user` 返回 `None`（异常被业务代码的 `except: print()` 吞掉，且这次失败本身不算致命异常，不会有明显报错），Flask-Login 于是认为当前请求匿名，直接弹回登录页。排查时加了几行临时 `print` 到 `load_user` 里才看清是在这一步失败、失败原因是 `LDAPInvalidCredentialsResult`。修复：`ldapsearch -Y EXTERNAL -H ldapi:/// -b cn=config "(olcRootDN=*)"` 找到对应的 `olcDatabase={n}mdb,cn=config` 条目，用 `slappasswd` 生成跟 `LDAP_BIND_USER_PASSWORD` 一致的哈希，`ldapmodify -Y EXTERNAL -H ldapi:///` 替换 `olcRootPW`。**以后再迁移自建 OpenLDAP，`config.ldif`（cn=config）该不该一起认真导入、或者至少确认 rootDN/rootPW 是否也需要手动对齐，是要提前想清楚的一步，不能只顾着导数据树。**

## 迁移后又做的事

- 把 `/mnt/test001`（占位名）改成 `/mnt/extra-report`：卸载重挂载到新路径 + 批量重写 `data/ohmywod/report/` 下所有指向它的软链接（写了个 dry-run 脚本先确认列表再真正执行）+ 改 `ohmywod/app.py`/`ohmywod/templates/usage.html` 里两处硬编码路径。
- Cloudflare 从灰云切到橙云代理 + SSL 模式设为 Full (strict)：源站已有的 Let's Encrypt 证书直接满足 Full (strict) 的校验要求，零额外证书工作。好处：源站 IP 不再直接在 DNS 里暴露、Cloudflare 边缘帮忙挡流量、Full (strict) 保证 Cloudflare 到源站这段不会被中间人冒充。副作用：nginx 访问日志里的来源 IP 会变成 Cloudflare 边缘节点 IP，想要真实访客 IP 需要装 `ngx_http_realip_module` 配合 `CF-Connecting-IP` 头（当时评估为可选优化，未做）。

## 相关 commit

- `9d85bb6` — 依赖升级到 Python 3.12 / Flask 3 / Flask-Admin 2.x / SQLAlchemy 2.0
- `fb7a775` — `/mnt/test001` 改名为 `/mnt/extra-report`
