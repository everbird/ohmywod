---
document_id: ohmywod-password-reset-plan
schema_version: 1
document_status: draft
source_of_truth_for: "邮箱找回密码（重置令牌、邮件发送基建、前后端流程）的实现边界、工作项状态与 wave changelog"
language: zh-CN
created_at: "2026-07-26"
last_updated: "2026-07-26"
review_commit: "f0643df"
review_worktree: "clean"
next_item_id: "PWR-005"
---

# 找回密码计划

> 本文是战报网“忘记密码 → 邮件重置”的最省事落地计划。核心思路：**用 Flask 自带的 `itsdangerous` 签发无状态一次性令牌（零新依赖、不动数据库）**，配上**一套最小的邮件发送基建（先用 Gmail SMTP + Flask-Mail）**，加**两个路由 / 两个表单 / 两个页面**，复用现有的 Flask-Limiter 限流与“通用错误提示”防枚举策略。
>
> **当前结论：先做 Wave 1（令牌模块 + 邮件基建 + 找回流程），用 Gmail SMTP 把功能跑通上线；令牌无状态、以“密码哈希指纹 + TTL”实现一次性与自动失效，不新增数据库字段、不做 alembic 迁移。发件人升级到自有域名（Resend / SPF/DKIM）作为 Wave 2 可选增强，切换成本很低。个人兴趣项目，以能用、简单、清晰为准，不追求工业级严密性。**

## 1. 背景、现状与原则

### 1.1 本文负责什么

- 记录“邮箱找回密码”功能的实现边界、未来事项与完成证据：重置令牌的生成 / 校验、邮件发送基建与凭据管理、找回密码的前后端流程。
- 目标是用最小实现与运维成本，让忘记密码的用户能自助重置，而不必找站长手动改库。
- **不负责**注册时的邮箱验证（“确认这个邮箱确实属于本人”）。这是相关但独立的方向，本文明确不含，仅在待决策清单里记下它对找回可靠性的影响（见第 5、6 节）。
- **不负责**短信 / 手机号找回、安全问题找回、账号锁定与登录验证码等更重的认证方向（见第 6 节）。

### 1.2 2026-07-26 当前基线

| 项 | 当前状态 | 证据与含义 |
|---|---|---|
| 用户邮箱 | 已有且唯一 | `ohmywod/models/user.py` 的 `User.email`（`unique=True, index=True`）；找回密码所需的收件地址与查找入口已就绪 |
| 按邮箱查用户 | 现成可复用 | `ohmywod/controllers/user.py` `get_db_user_by_email()` |
| 设置新密码 | 现成可复用 | `ohmywod/controllers/user.py` `set_password()`（Argon2 重哈希 + 更新 `password_updated_at`） |
| 密码哈希 | Argon2id，自描述 | `ohmywod/security.py` `hash_password()`；`password` 列每次改密都会变，可作令牌一次性指纹 |
| 令牌签发 | 无需新依赖 | Flask 自带 `itsdangerous`（已装 2.2.0），`URLSafeTimedSerializer` 可用现成的 `SECRET_KEY` 签发带 TTL 的无状态令牌 |
| 邮件发送 | **完全缺失** | 全仓 grep 无 `smtplib` / `flask_mail` / 任何 SMTP 配置；这是本计划唯一需要新建的基建 |
| 限流 | 现成可复用 | `ohmywod/extensions.py` `limiter`；`login` / `register` 已按 IP + 账号维度限流，找回路由照抄即可 |
| 防枚举策略 | 已有先例 | `views/frontend.py` 登录用“用户名或密码错误”通用提示避免泄露账号是否存在，找回流程沿用同一口径 |
| 密钥管理 | 现成可复用 | `config.py` 用 `<secret:...>` 占位，`gen.py` 渲染，`ohmywod-ops` 用 sops+age 管理（现有多个密钥字段）；SMTP 凭据按同一套路新增即可 |

### 1.3 已拍板的原则

1. **令牌无状态、不落库**：用 `itsdangerous` 签一个 `{uid, 密码哈希指纹}` 的载荷，靠 `max_age` 控制过期、靠“改密后哈希变化”实现一次性作废。**不新增数据库字段、不写重置表、不做 alembic 迁移。** 令牌坏了 / 过期让用户重发即可。
2. **防账号枚举**：找回入口无论邮箱是否存在，都返回同一句“如果该邮箱已注册，我们已发送重置邮件”，与登录页的通用错误提示口径一致；只有命中真实用户才实际发信。
3. **敏感凭据只进 sops**：SMTP 密码（Gmail App Password 或后续服务商 API key）作为新 `<secret:...>` 字段进 `ohmywod-ops`，仓库不留明文，不写进日志 / 异常 / 模板。
4. **邮件发送不得拖垮请求**：发信设超时与异常兜底；发信失败不向用户暴露栈信息、不返回 500，按“已发送”提示优雅收尾（防枚举同时也防抖动）。
5. **复用而非新造**：限流用现成 `limiter`，表单用 Flask-WTF，CSRF 用现成 `csrf`，重哈希用 `security` / `set_password()`；只有邮件发送是新增。
6. **令牌短时效**：重置链接 30 分钟过期（实施时可调），把可用性与被盗用窗口平衡好。

### 1.4 成功判断

- 用户在登录页点“忘记密码”，填邮箱，收到一封含重置链接的邮件；点链接能设新密码并用新密码登录。
- 同一链接**改密后立即失效**、**超过 TTL 失效**；旧链接不可复用。
- 找回入口**不泄露**某邮箱是否注册（响应文案、状态码、耗时都不区分）。
- 找回 / 重置路由都受 IP（及邮箱维度）限流；SMTP 凭据只在 sops，仓库 grep 无明文。
- 全程**无新增 SQLite 字段 / 表 / migration**；DR / litestream 备份链不受影响。

## 2. 这份计划怎么维护

沿用 [afdian-integration-plan.md](afdian-integration-plan.md) 与 [maintenance-support-plan.md](maintenance-support-plan.md) 的同一套约定：个人兴趣项目，不需要 owner / RACI。事项通常由一个 AI 工具推进，另一个 AI 工具独立检查；涉及站外账号（Gmail App Password、域名 DNS、邮件服务商）时由用户最后决定并执行。

每个事项两个可选角色：

- `Drive AI`：调查现状、提出选项、实施改动，并更新本文和 changelog。
- `Review AI`：独立检查代码、隐私、安全与剩余风险，不只复述 Drive AI 结论。

### 2.1 状态枚举

`todo`（方向已确认未开始）｜`assessing`（需用户选择或外部信息）｜`in_progress`（正在实施）｜`blocked`（有明确阻塞，须写解除方式）｜`done`（完成判断满足且有可复核证据）｜`cancelled`（明确不做，记录理由与重看触发条件）。

### 2.2 更新规则

1. 每个 `PWR-NNN` ID 永久不变、不可复用。新增用 front matter 的 `next_item_id` 并同步递增。
2. 开始工作前先读本文和 `git status`，保留未提交改动。
3. `状态` 是事项主真值；状态变化、代码改动、changelog 放同一波。
4. `done` 需可复核证据；只加了页面、只发了一封测试邮件、或只签发一次令牌都不算整个事项完成。
5. `blocked` 写清卡点与解除方式；`cancelled` 写清为何不做与何时重看。
6. SMTP 凭据、App Password、任何用户邮箱明文不写进本文或仓库任何位置。
7. 涉及 Gmail App Password / 域名 DNS / 邮件服务商注册等站外操作时，先由用户确认并执行；本文不构成外部账号操作授权。
8. 每波在文末按时间正序追加 changelog；旧记录不重写，纠错追加新记录。
9. 每次变更更新 front matter 的 `last_updated`。

### 2.3 固定工作项格式

- 元信息：`状态`、`优先级`、`波次`、`Drive AI`、`Review AI`、`依赖`、`最后更新`、`结论置信度`
- 内容：`问题与影响`、`证据`、`方向与要点`、`完成判断`、`Review 关注`、`执行证据`

优先级：`P1` 建立可用找回流程所必需；`P2` 可选增强，不影响主路径成立。

## 3. 建议推进顺序

### Wave 1：可用的邮件找回流程（P1）

范围：PWR-001、PWR-002、PWR-003。按“令牌模块 → 邮件基建 → 前后端流程”推进；做完即可上线一条完整的自助找回路径。PWR-001 纯代码可先行；PWR-002 需要用户提供 Gmail App Password（`assessing`）；PWR-003 把两者接进页面。

### Wave 2：发件域名与送达率升级（P2，可选）

范围：PWR-004。只有在不想用私人 gmail 当发件人、或想要更好送达率时才做；把 `MAIL_*` 三个值指向 Resend 等服务商并配 DNS 即可，Wave 1 的流程代码不用动。

## 4. 工作项

### PWR-001 — 重置令牌的生成与校验（itsdangerous，无状态 / 一次性 / 不动库）

- 状态：`todo`
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-26
- 结论置信度：`recommended`

问题与影响：找回密码需要一个“证明持有此邮箱”的凭据。若为此新建重置表 / 令牌字段，会牵连 SQLite / litestream / DR 一致性链，对个人项目过重。用无状态签名令牌可完全避免动库。

证据：Flask 自带 `itsdangerous`（已装 2.2.0），`URLSafeTimedSerializer` 支持 `max_age`；`config.py` 已有 `SECRET_KEY`；`models/user.py` 的 `password` 列每次改密都会变（`set_password` 重哈希），可作一次性指纹。

方向与要点：

- 新增一个小模块（如 `ohmywod/tokens.py`，或并入 `security.py`）：
  - `generate_reset_token(user)`：`serializer.dumps({"uid": user.id, "pw": user.password[-12:]})`，固定 `salt`（如 `"pwd-reset"`），密钥复用 `SECRET_KEY`。
  - `verify_reset_token(token, max_age=1800)`：`loads` 带 `max_age` 捕获 `SignatureExpired` / `BadSignature` 返回 `None`；再按 `uid` 取用户并比对 `user.password[-12:]` 是否仍等于载荷里的指纹。**改密后哈希变化 → 指纹不符 → 旧链接自动失效（天然一次性）。**
- 令牌只放进链接的 path / query，不入库、不入日志。
- 单元测试覆盖：有效令牌、过期（`max_age`）、篡改（`BadSignature`）、改密后旧令牌失效四条路径。

完成判断：本地能签发并校验令牌；四条测试路径全绿；全仓无新增 SQLite 字段 / 表 / migration。

Review 关注：`salt` 与密钥使用是否正确；指纹长度是否足以区分不同哈希；令牌是否可能被写进日志 / 异常；`SignatureExpired` 与 `BadSignature` 是否都被吞成“无效令牌”而非 500。

执行证据：尚无。

### PWR-002 — 邮件发送基建与凭据管理（Flask-Mail + Gmail SMTP）

- 状态：`assessing`
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：用户开启 Gmail 两步验证并生成 App Password
- 最后更新：2026-07-26
- 结论置信度：`recommended, external setup required`

问题与影响：全仓无任何邮件能力，这是找回流程唯一必须新建的基建。发信凭据敏感，必须走既有 sops 密钥管理，不能进公开仓库。

证据：全仓 grep 无 `smtplib` / `flask_mail` / SMTP 配置；`config.py` 用 `<secret:...>` 占位并由 `gen.py` 渲染，`ohmywod-ops` 用 sops 管理密钥（现有多个密钥字段可参照）。

方向与要点：

- `requirements.txt` 新增 **`Flask-Mail`**（本计划唯一新依赖；`itsdangerous` 已随 Flask 存在）；在 `extensions.py` 加 `mail = Mail()` 并在 app 初始化时 `mail.init_app(app)`。
- `config.py` 加一组邮件配置（先走 Gmail SMTP）：
  - `MAIL_SERVER = "smtp.gmail.com"`、`MAIL_PORT = 587`、`MAIL_USE_TLS = True`
  - `MAIL_USERNAME` = 发件 Gmail 地址、`MAIL_DEFAULT_SENDER = ("Ohmywod", <该地址>)`
  - `MAIL_PASSWORD = "<secret:gmail_app_password>"` —— 作为**新密钥字段**加入 `ohmywod-ops` 的 sops，渲染进 `local_config.py`，沿用现有密钥同一套路。
- 封装一个 `send_reset_email(user, reset_url)` 辅助函数：纯文本正文即可（含链接与有效期说明），设发送超时，异常只记日志不外抛。
- 注意 Gmail 限制：发件人被强制为该 Gmail 地址（可自定义显示名）；免费额度约 500 封/天，找回量级远够用；勿把 From 硬设成未验证的域名地址（会进垃圾箱）。

完成判断：本地用真实 App Password 能成功发出一封测试邮件并收到；密码只存在于 sops，仓库 grep 无明文；发信失败路径不抛 500、只记日志。

Review 关注：App Password 是否泄漏进日志 / 异常 / 模板 / 版本库；`MAIL_USE_TLS` / 端口组合是否正确；发送超时与失败兜底是否健壮；`MAIL_DEFAULT_SENDER` 是否与真实发件账号一致。

执行证据：尚无；等待用户开启 Gmail 2FA 并提供 App Password。

### PWR-003 — 找回密码前后端流程（路由 / 表单 / 页面 + 限流 + 防枚举）

- 状态：`todo`
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：PWR-001、PWR-002
- 最后更新：2026-07-26
- 结论置信度：`recommended`

问题与影响：把令牌与邮件基建接成用户可见的两步流程，并在入口处防住账号枚举与暴力尝试。

证据：`views/frontend.py` 已有 `LoginForm` / `RegistrationForm` 范式、`@limiter.limit(...)` 用法、按账号维度限流的 `_login_username_key`、通用错误提示与 `is_safe_next_url`；`templates/login.html:62` 的 `form-actions` 区已放“注册账号”按钮，可并列加“忘记密码”。

方向与要点：

- 两个路由加进 `views/frontend.py`，各挂 `@limiter.limit`（照抄 login/register 的 IP + 邮箱维度力度）：
  - `GET/POST /forgot-password`：`ForgotPasswordForm(email)` → 校验通过后**无论邮箱是否命中都渲染同一句“如果该邮箱已注册，我们已发送重置邮件”**；仅当 `get_db_user_by_email` 命中时才 `generate_reset_token` + `send_reset_email`（`url_for(..., _external=True)` 生成外链）。
  - `GET/POST /reset-password/<token>`：先 `verify_reset_token`，失败提示“链接无效或已过期，请重新申请”；成功则渲染 `ResetPasswordForm(new1, new2)`（`EqualTo` 校验），提交后调 `set_password()` 重哈希、闪现成功并跳转登录。
- 新增两个模板 `forgot_password.html`、`reset_password.html`（沿用 `base.html` 与现有表单样式），一段纯文本邮件正文；在 `login.html` 的 `form-actions` 加“忘记密码？”链接。
- 令牌校验失败、表单错误一律走友好文案，不暴露内部错误。

完成判断：端到端跑通——申请 → 收信 → 点链接 → 改密 → 用新密码登录；改密后旧链接失效；找回入口对存在 / 不存在的邮箱响应完全一致；两路由均被限流；CSRF 生效。

Review 关注：防枚举是否彻底（文案 + 状态码 + 是否存在时序差异）；限流力度；重置页是否要求登录（应**不**要求，靠令牌授权）；`_external` 链接的 scheme / host 是否正确（HTTPS）；成功改密后是否顺带登出其它会话的必要性（可在待决策记录）。

执行证据：尚无。

### PWR-004 — 发件域名与送达率升级（可选：Resend / 自有域名 + SPF/DKIM）

- 状态：`assessing`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：PWR-003 上线；用户拥有域名并可改 DNS
- 最后更新：2026-07-26
- 结论置信度：`optional`

问题与影响：Gmail SMTP 能用但发件人是站长私人 gmail，暴露隐私且不够“产品化”；且无法做本域的 SPF/DKIM/DMARC 对齐。若在意可升级到事务邮件服务商，用 `noreply@<域名>` 发信、送达率更好。

证据：PWR-002 采用 Gmail SMTP，From 受限于私人地址；行业惯例低量找回信用 Resend / Brevo 免费额度即可覆盖（如 Resend 免费约 100 封/天、3000 封/月）。

方向与要点：

- **不自建邮件服务器、不买 Google Workspace**（对个人项目过重）；改用事务邮件服务商，验证域名（加 2 条 DNS 记录）后以 `noreply@<域名>` 发信。
- 若服务商支持 SMTP：Wave 1 代码零改动，只把 `MAIL_SERVER` / `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_DEFAULT_SENDER` 换成服务商的值（新密钥同样进 sops）。
- 若改走 HTTP API：需评估是否引入 `requests`（当前未装）；除非有明显收益，否则优先 SMTP 路径以复用 PWR-002。
- 配好 SPF / DKIM（DMARC 可选）以保证送达。

完成判断：找回邮件以 `noreply@<域名>` 发出且落收件箱；SPF/DKIM 通过校验；密钥只在 sops；Wave 1 流程行为不变。

Review 关注：DNS / DKIM 是否正确；是否引入了不必要的新依赖；From 与实际发送域是否对齐（否则进垃圾箱）；服务商 API key 是否只在 sops。

执行证据：尚无；等待用户决定是否升级及提供域名。

## 5. 待决策清单

不阻塞 Wave 1，可在处理对应事项时回答：

1. 发件方式起步用 Gmail SMTP + App Password，确认吗？（PWR-002）
2. 是否做 Wave 2 域名发件？若不做，PWR-004 可标 `cancelled`，Gmail 方案长期成立。（PWR-004）
3. 重置链接有效期取多久（默认建议 30 分钟）？（PWR-001）
4. 成功改密后是否要同时失效该用户的其它已登录会话？（PWR-003；无状态令牌本身不强制，个人项目可暂不做）
5. **注册邮箱当前未做验证**：找回可靠性依赖“用户填的邮箱确实是本人”。是否需要单开一个“注册邮箱验证”方向？（本文范围外，见第 6 节）
6. 找回入口放登录页链接即可，还是也在个人资料页提供？（PWR-003）

## 6. 明确不做

- 不新增任何重置相关的 SQLite 字段 / 表 / migration，不纳入 litestream / DR 备份链（令牌无状态）。
- 不做短信 / 手机号找回、安全问题找回。
- 不自建邮件服务器，不购买 Google Workspace / 企业邮箱来发这一类系统邮件。
- 不在仓库保存 SMTP 凭据、App Password、服务商 API key 或任何用户邮箱明文。
- 不在本计划内做**注册时的邮箱验证**（确认邮箱归属）——这是相关但独立的方向，仅在待决策清单记录其对找回可靠性的影响。
- 不做登录验证码 / 账号锁定等更重的认证增强（登录已有 IP + 账号维度限流兜底）。
- 不把找回失败的具体原因（邮箱不存在 / 令牌过期细节）暴露给用户，一律友好通用文案。

## 7. Changelog（append-only，旧 -> 新）

> 每波改动在本节末尾追加。不得改写旧记录；如旧记录有误，追加 correction wave。

### Changelog 条目模板

复制以下模板并追加到本节末尾；条目 ID 使用 `WAVE-YYYYMMDD-NN`：

```markdown
### WAVE-YYYYMMDD-NN — 简短标题

- 日期：YYYY-MM-DD
- Drive AI：工具名称；未使用则写“无”
- Review AI：工具名称；尚未 review 则写 `unassigned`
- 关联事项：PWR-NNN, PWR-NNN
- 状态变化：例如 PWR-001 `todo` -> `in_progress` -> `done`
- 改动：文件、站内页面或站外设置摘要
- 关键取舍：选择和理由；无则写“无”
- 验证：检查、测试或人工确认摘要，不含凭据和用户邮箱
- 发生的问题：无则写“无”
- 剩余风险：本波未解决的内容
- 下一步：下一事项或需要用户决定的问题
```

### WAVE-20260726-01 — 找回密码计划建档

- 日期：2026-07-26
- Drive AI：Claude Code（Opus 4.8）
- Review AI：`unassigned`
- 关联事项：创建 PWR-001 至 PWR-004
- 状态变化：新增 2 个 `todo`（PWR-001、PWR-003）、2 个 `assessing`（PWR-002、PWR-004）
- 改动：新增 `docs/password-reset-plan.md` 草案；沿用 afdian-integration-plan / maintenance-support-plan 的 front matter、工作项与 append-only changelog 结构；未修改应用代码或站外账号
- 关键取舍：令牌走 `itsdangerous` 无状态方案（复用 `SECRET_KEY` + `password` 哈希指纹实现一次性与 TTL 失效），**刻意不新增数据库字段 / migration**，与站点“SQLite 为唯一真值 + litestream 备份一致性”的洁癖对齐；邮件基建先用 Gmail SMTP + Flask-Mail（唯一新依赖）把功能跑通，域名发件（Resend / SPF-DKIM）降级为 Wave 2 可选、切换成本仅三个 `MAIL_*` 值 + DNS
- 验证：核对现状——`User.email` 唯一且带索引、`get_db_user_by_email` / `set_password` 现成、`itsdangerous 2.2.0` 已装、全仓无任何邮件基建、`limiter` 与防枚举先例可复用、sops 可承载 SMTP 凭据；worktree clean @ `f0643df`
- 发生的问题：无
- 剩余风险：PWR-002 依赖用户开启 Gmail 2FA 并提供 App Password（站外事项，`assessing`）；找回可靠性隐含依赖“注册邮箱属实”，而注册邮箱验证本文不含（第 5 节待决策 5）
- 下一步：确认草案后先做 PWR-001（纯代码、可先行并补测试），并请用户准备 Gmail App Password 以解锁 PWR-002
