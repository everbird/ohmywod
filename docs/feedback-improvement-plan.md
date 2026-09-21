---
document_id: ohmywod-feedback-improvement-plan
schema_version: 1
document_status: in_progress
source_of_truth_for: "用户反馈（提交入口、通知、可回访性、后台处理）的优化边界、工作项状态与 wave changelog"
language: zh-CN
created_at: "2026-07-27"
last_updated: "2026-09-21"
review_commit: "app b43e5a4"
review_worktree: "clean"
next_item_id: "FBK-005"
---

# 用户反馈优化计划（草稿）

> 本文是战报网“用户反馈”功能的优化计划。核心判断（**经 2026-07-27 线上数据核实**）：**现存 272 条反馈里约 96% 是自动化冷推广 spam，现有的 IP 限流对这种低频滴灌完全无效；真反馈仅约 4% 且被淹没，站长还得主动开 Flask-Admin 才看得到。** 所以最高价值、最省事的改动不是重做表单，而是**先止血（挡住 spam）、再敲门（有通知）**。
>
> 落地思路（Wave 1，均零数据库改动、零新依赖）：**① 反馈改为登录后才能提交（FBK-002）**——针对本站 spam 近乎清零，且登录后天然拿到提交者身份（**2026-09-21 拍板：不做链接拦截**，登录用户发的反馈就足够，避免误伤“某某页面打不开”这类带链接的真反馈）；**② 复用 password-reset 刚建好的 Resend 邮件基建（`ohmywod/mailer.py`）做新反馈邮件通知（FBK-001）**，让站长第一时间看到剩下的真反馈。后台“已处理”状态（FBK-003）作为可选增强。
>
> 个人兴趣项目，以能用、简单、清晰为准，不追求工业级严密性。**防滥用方向（仅登录门槛，不拦链接）已拍板；Wave 1 已于 2026-09-21 在 `feature/feedback-improvement` 分支实施（见第 7 节 changelog）。**

## 1. 背景、现状与原则

### 1.1 本文负责什么

- 记录“用户反馈”从提交、防滥用、到被站长看见这条链路的优化边界、工作项与完成证据。
- 目标：用最小改动，让反馈**挡得住 spam**（登录门槛）、**不再石沉大海**（有通知）、**能定位到人**（带登录用户名）、**好处理**（后台可分辨新旧）。
- **不负责**做站内工单 / 客服系统、公开的反馈列表 / 投票、多轮对话式反馈 / 站内回复流程，这些对个人项目过重（见第 6 节）。
- **不负责**注册邮箱验证、账号体系改造——本文只复用现成登录态与 `username`，不改认证方向。

### 1.2 2026-07-27 当前基线

| 项 | 当前状态 | 证据与含义 |
|---|---|---|
| 反馈模型 | 极简、无关联 | `ohmywod/models/feedback.py` `Feedback(id, content, username, created_at, updated_at)`；`username` 是自由文本字符串，**不关联 `User`**，无邮箱 / 无状态 / 无分类 |
| 提交入口 | 开放、免登录 | `ohmywod/views/frontend.py:250` `/feedback`（GET/POST），`FeedbackForm(username, feedback)`；成功后渲染 `feedback_submitted.html` |
| 限流 | 已有 | `@limiter.limit("5 per minute; 20 per hour", methods=["POST"])`（IMP-006 已按 IP 兜住开放 POST 的 spam 面） |
| 通知 | **完全缺失** | 提交后无任何外发通知；站长只能主动去后台翻，容易漏看、延迟 |
| 读取出口 | 仅 Flask-Admin | `ohmywod/app.py:176` 把 `Feedback` 挂进 admin（Misc 分类，HTTP Basic）；无排序 / 无“已处理”标记，新旧混在一起 |
| 可回访性 | **无** | 反馈里没有 `user_id`、没有邮箱；即便想回复用户也无从联系（`username` 可乱填） |
| 邮件基建 | **现成可复用** | `ohmywod/mailer.py`（PWR-002）已封装 best-effort 的 Resend SMTP 发信；`emails/reset_password.txt` 是现成的纯文本邮件模板范式 |
| 登录态 | 现成可复用 | `views/frontend.py` 已 `from flask_login import current_user`；`current_user.display_name / email / username` 随手可得 |
| 落库改动成本 | 需评估 | 项目用 alembic；给 `Feedback` 加列（状态 / 分类）需一次迁移，牵连 SQLite / litestream / DR，应尽量批量、可空、少动 |

### 1.2.1 线上真实数据画像（2026-07-27 SSH 抽样，`/data/ohmywod/ohmywod_d.sqlite` `feedback` 表）

**结论先行：现有的 IP 限流对当前的 spam 完全无效，现存 272 条反馈里约 96% 是垃圾。**

- **总量 272 条**（约 2023–2026 三年），其中**真反馈仅约 11 条（≈4%）**：短、中文、无链接、问产品功能（要删除功能、目录排序、密码找回、上传后中文文件名丢失、Internal Server Error 求助等）。这是要保护的核心用户。
- **其余约 96% 是自动化冷推广 spam**：SEO / 外链 / 视频推广 / Instagram 涨粉 / 日本 MEO / 加密货币卡等推销，英文日文为主，内容偏长（258/272 超 200 字），**约 80%（219 条）带 URL** 且常直接点名 `wod.everbird.me`。特征是典型的**表单填充机器人**。
- **为什么现有 IP 限流拦不住**：这类 spam 是**低频滴灌**——按天分布峰值仅 3 条/天，单 IP 通常一天一两次，永远碰不到 `5/min; 20/hour` 阈值。限流防的是瞬时爆刷，不是细水长流的冷推广机器人；两者是不同的滥用模型。
- **最强、几乎零误伤的信号**：真反馈**零链接**，而 spam 约八成带链接；且真反馈几乎都来自真实（多为登录）用户，机器人都没登录。故**登录门槛**是针对本站数据 ROI 最高的一招；链接拦截原拟作为第二道带子，2026-09-21 拍板不做（登录已足够，且避免误伤带链接的真反馈）。

### 1.3 已拍板 / 拟定原则

1. **防滥用是本轮第一优先**（据 1.2.1 数据）：反馈入口改为**登录后才能提交**。机器人都没登录，仅此一条即可把本站 spam 近乎清零。**不做链接拦截**——登录用户发的反馈就足够，不再按内容过滤（2026-09-21 拍板，取代 2026-07-27 的“登录 + 拦链接”组合）。
2. **登录门槛顺带解决“可回访”**：登录才能提交后，提交者身份天然已知——把 `current_user.username` 落进已有 `username` 列即可，**Wave 1 无需新增 `user_id` 列 / 无 alembic 迁移**。
3. **登不上的用户走论坛兜底**：登录门槛的唯一真实代价是“注册/登录本身出问题”的用户（三年里确有一例）无法自助反馈。落地页已挂 WoD 论坛帖 `[post:16014199]` 作为逃生通道，需在反馈页/登录引导处明确指向它。
4. **先解决“看不见”**：邮件通知是零数据库、零新依赖的最高性价比项，与登录门槛一并进 Wave 1（FBK-001）。
5. **复用而非新造**：发信复用 `mailer.py`（Resend），登录态复用 `current_user` + `@login_required`，后台复用 Flask-Admin，限流保留现成 `limiter`（作为登录用户的兜底，不再是主防线）；不引入新服务 / 新依赖 / 无需验证码。
6. **发信不得拖垮提交**：通知走 best-effort（沿用 `send_reset_email` 的“异常只记日志、不外抛”），发信失败不影响用户看到“已提交”。
7. **落库改动能省则省**：Wave 1（FBK-001/002）不动库；仅 P2 的后台状态列（FBK-003）需一次可空、对存量安全的迁移。
8. **不泄露敏感信息**：通知邮件只发给站长自己（收件人来自配置，不硬编码明文邮箱进仓库）；用户邮箱不写日志、不外显。

### 1.4 成功判断

- **spam 近乎清零**：登录门槛上线后，新的自动化推广基本进不来（可对照上线后一段时间的新增反馈验证）。
- 用户提交反馈后，**站长在邮箱里就能第一时间看到内容与提交者**，不必主动开后台。
- 登录用户的反馈能一眼看出**是谁提交的**（用户名已随反馈落库）。
- 后台里能分辨**哪些反馈还没处理**、按时间倒序看最新的（FBK-003）。
- 上述改动**不破坏现有反馈数据**，且发信 / 通知失败都不影响用户正常提交；登不上的用户能在页面上看到论坛兜底入口。

## 2. 这份计划怎么维护

沿用 [password-reset-plan.md](archive/password-reset-plan.md)、[afdian-integration-plan.md](archive/afdian-integration-plan.md) 的同一套约定：个人兴趣项目，不需要 owner / RACI。事项通常由一个 AI 工具推进，另一个 AI 工具独立检查；涉及站外账号（邮件服务商、DNS）或会改动生产数据的操作，由用户最后确认并执行。

每个事项两个可选角色：

- `Drive AI`：调查现状、提出选项、实施改动，并更新本文和 changelog。
- `Review AI`：独立检查代码、隐私、安全与剩余风险，不只复述 Drive AI 结论。

### 2.1 状态枚举

`todo`（方向已确认未开始）｜`assessing`（需用户选择或外部信息）｜`in_progress`（正在实施）｜`blocked`（有明确阻塞，须写解除方式）｜`done`（完成判断满足且有可复核证据）｜`cancelled`（明确不做，记录理由与重看触发条件）。

### 2.2 更新规则

1. 每个 `FBK-NNN` ID 永久不变、不可复用。新增用 front matter 的 `next_item_id` 并同步递增。
2. 开始工作前先读本文和 `git status`，保留未提交改动。
3. `状态` 是事项主真值；状态变化、代码改动、changelog 放同一波。
4. `done` 需可复核证据；只加了页面或只发了一封测试邮件不算整个事项完成。
5. `blocked` 写清卡点与解除方式；`cancelled` 写清为何不做与何时重看。
6. 涉及 alembic 迁移的项，改动须可回滚、对存量数据安全（新列可空 / 有默认）。
7. 站长收件邮箱、用户邮箱等不写进本文或仓库任何位置；收件人来自配置。
8. 每波在文末按时间正序追加 changelog；旧记录不重写，纠错追加新记录。
9. 每次变更更新 front matter 的 `last_updated`。

### 2.3 固定工作项格式

- 元信息：`状态`、`优先级`、`波次`、`Drive AI`、`Review AI`、`依赖`、`最后更新`、`结论置信度`
- 内容：`问题与影响`、`证据`、`方向与要点`、`完成判断`、`Review 关注`、`执行证据`

优先级：`P1` 让反馈“到得了人、找得到人”所必需；`P2` 可选增强，不影响主路径成立。

## 3. 建议推进顺序

### Wave 1：让反馈到得了人、找得到人（P1）

范围：FBK-001、FBK-002。两项都**零数据库改动、可立即上线**：**FBK-002（登录门槛）**是本轮防滥用主防线，把 spam 近乎清零、并顺带让每条反馈都带真实用户名；**FBK-001（邮件通知）**让站长第一时间看到剩下的真反馈。做完这波，反馈就从“被 spam 淹没的黑洞”变成“干净、会敲门、且知道是谁提的”。两项无先后硬依赖，建议 FBK-002 先落（先止血），FBK-001 紧随。

### Wave 2：后台处理体验（P2，可选）

范围：FBK-003。让后台能分辨新旧 / 已处理、按时间倒序看最新。需一次可空、对存量安全的 alembic 迁移（加状态列）。原草案的 FBK-004（蜜罐 / 分类 / 匿名联系方式等表单增强）在“登录门槛”拍板后**大部分已无必要**，见 FBK-004（`cancelled`）。

## 4. 工作项

### FBK-001 — 新反馈邮件通知（复用 Resend，best-effort，零数据库改动）

- 状态：`in_progress`（代码完成、单测通过；待配置收件人并上线联调）
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`Claude Code (Opus 5)`
- Review AI：`unassigned`
- 依赖：无（PWR-002 的邮件基建已上线）
- 最后更新：2026-09-21
- 结论置信度：`recommended`

问题与影响：当前反馈提交后没有任何外发通知，站长得主动开 Flask-Admin 才看得到，极易漏看或延迟数天。这是“反馈是黑洞”的根因，也是最省事就能补的一环。

证据：`ohmywod/mailer.py`（PWR-002）已有 best-effort 的 Resend 发信封装与 `emails/*.txt` 纯文本模板范式；发信基建、密钥（sops `smtp_password`）、发件域名（`wod.everbird.me`）都已就绪，无需任何新基建。

方向与要点：

- 在 `mailer.py` 加一个 `send_feedback_notification(feedback)`（沿用 `send_reset_email` 的 try/except、异常只记日志不外抛）：主题含“新反馈”，正文含提交时间、名称 / 用户、内容，可附后台链接。
- 收件人用**配置项** `FEEDBACK_NOTIFY_TO`，**不把站长邮箱明文写进代码或本文**。实施时未采用“回落到 `MAIL_DEFAULT_SENDER`”——发件人是 `noreply@wod.everbird.me`，不是可收信的邮箱，回落只会产生退信；改为**未配置则记 warning 并跳过发信**，反馈照常入库、后台可见。
- 在 `feedback_page` 成功创建后调用一次；发信失败不影响用户看到 `feedback_submitted.html`。
- 新增邮件模板 `templates/emails/feedback_notification.txt`（纯文本）。

完成判断：本地提交一条反馈能收到一封通知邮件（含内容与提交者）；发信失败路径不抛 500、只记日志、用户照常看到“已提交”；无新增数据库字段 / 迁移。

Review 关注：收件人是否来自配置而非硬编码；发信是否真的 best-effort（不阻塞、不 500）；反馈正文里是否有需要转义 / 截断的超长内容；登录门槛（FBK-002）已把“开放 POST 刷邮件”的面基本堵死，仍应确认单个登录用户狂刷时通知不至于轰炸（可复用现有 `limiter` 兜底）。

执行证据（2026-09-21，分支 `feature/feedback-improvement`）：
- `ohmywod/mailer.py` 新增 `send_feedback_notification(feedback)`：try/except 全包、异常只 `logger.exception` 不外抛；收件人取 `FEEDBACK_NOTIFY_TO`，为空则 warning + 跳过、返回 False。主题 `[战报网] 新反馈来自 <username>`，正文含提交者、UTC 时间、内容、后台链接（`url_for('feedback.index_view', _external=True)`）。
- 新模板 `ohmywod/templates/emails/feedback_notification.txt`（纯文本，`.txt` 不经 Jinja autoescape，内容原样呈现）。
- `ohmywod/config.py`、`configs/templates/ohmywod_local_config.py.template` 加 `FEEDBACK_NOTIFY_TO = ""`（仅 schema，真值走 ops 渲染）。
- `views/frontend.py` `feedback_page` 在 `create_feedback` 之后调用一次通知。
- 超长内容：表单 `Length(max=5000)` 兜住，邮件无需截断；轰炸：保留 `5/min; 20/hour` 的 IP 限流。
- 单测 `tests/test_feedback.py`：发信内容 / 收件人（`mail.record_messages`）、未配置收件人时不发信且提交成功、`mail.send` 抛异常时提交仍 200 且已入库、`send_feedback_notification` 不外抛。全套 164 用例通过。
- **未完成**：生产 `FEEDBACK_NOTIFY_TO` 尚未在 ohmywod-ops 配置（需站长给地址）；尚未真实发信联调。

### FBK-002 — 防滥用主防线：登录才能反馈（零数据库改动；不做链接拦截）

- 状态：`in_progress`（代码完成、单测通过；待合并上线并对照验证 spam 降幅）
- 优先级：`P1`
- 波次：Wave 1
- Drive AI：`Claude Code (Opus 5)`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-09-21
- 结论置信度：`recommended`（方向已拍板；无迁移、无新依赖）

问题与影响：线上 272 条反馈约 96% 是自动化冷推广 spam（1.2.1），现有 IP 限流对这种低频滴灌完全无效。这是反馈体验最大的问题——真反馈被淹没、站长也懒得翻。同时现有 `username` 是自由文本、可乱填，反馈无从定位到人、无法跟进。

证据：1.2.1 数据显示真反馈几乎都来自真实（多为登录）用户，spam 都未登录。`views/frontend.py` 已引入 `current_user` 与 `@login_required`（`/profile` 等已用）；`Feedback.username` 列现成，写入 `current_user.username` 即可定位到人，**无需新列 / 无需迁移**。

方向与要点：

- **登录门槛**：给 `/feedback` 路由加 `@login_required`（沿用站内现成用法）。未登录访问被引导到登录页；提交者身份从此天然已知。
- **身份落库（复用现有列）**：提交时把 `current_user.username`（或 `display_name`）写进已有的 `username` 列，后台 / 通知即可定位到人。**不新增 `user_id` 列、不做 alembic 迁移**（要更强的关联可留到以后，见第 5 节）。
- ~~**链接拦截**~~：**不做**（2026-09-21 拍板）。登录用户发的反馈就足够，不再按内容含不含链接过滤——真用户报“某某页面打不开”时贴链接是合理的，拦截反而误伤。
- **表单简化**：去掉自由填写的“你的名称”输入（改用登录身份），只保留反馈内容；顺带并入 FBK-004 遗留的 `DataRequired` + 长度上限校验。
- **兜底入口**：在反馈页 / 登录引导处点明——登不上或不想登录的用户可通过落地页的 WoD 论坛帖 `[post:16014199]` 联系（应对“注册/登录本身出问题”的用户，1.3 原则 3）。
- 保留现有 `limiter` 作为登录用户维度的兜底，不再作为主防线。

完成判断：未登录无法提交反馈（跳登录）；登录用户提交的反馈在后台 / 通知里能看到真实用户名；含链接的内容照常接收；无新增数据库字段 / 迁移；反馈页能看到论坛兜底入口。上线后一段时间新增反馈里的推广 spam 显著减少（可对照验证）。

Review 关注：`@login_required` 是否覆盖 POST 且未登录不泄露内部错误；去掉 username 输入后模板 / 表单是否仍正确（提交的 `username` 字段应被忽略、不可伪造）；兜底论坛入口是否对未登录用户可见；登录用户维度的限流是否仍在。

执行证据（2026-09-21，分支 `feature/feedback-improvement`）：
- `views/frontend.py`：`/feedback` 加 `@login_required`（GET/POST 都覆盖；未登录走现有 `unauthorized_handler` 302 到 `/login?next=/feedback`）；`FeedbackForm` 删掉 `username` 字段，`feedback` 加 `DataRequired` + `Length(max=FEEDBACK_MAX_LENGTH=5000)`；入库写 `current_user.username`、内容 `strip()`；`limiter` 按 IP 的 `5/min; 20/hour` 保留为兜底。
- `templates/feedback.html`：去掉名称输入，显示“将以 `<username>` 的身份提交”，渲染字段错误，页脚加论坛 `[post:16014199]` 兜底文案；`feedback_submitted.html` 文案略丰富并附论坛入口；`login.html` 在 `?next=/feedback` 时提示“提交反馈需要先登录，登录不了可走论坛”。
- 单测：`tests/test_views.py` 改为断言未登录 GET/POST 均 302 到登录；`tests/test_ratelimit.py` 改用 `authenticated_client`；新 `tests/test_feedback.py` 覆盖登录后页面含用户名 / 无 `username` 输入 / 论坛入口、提交伪造 `username` 被忽略并落 `testuser`、空白 / 超长被拒、**含链接内容被正常接收**、登录页兜底提示仅在 `next=/feedback` 时出现。全套 164 用例通过。
- 无 alembic 迁移、无新依赖、无库结构改动。
- **未完成**：合并上线后对照新增反馈验证 spam 降幅。

### FBK-003 — 后台反馈处理体验（已处理状态 + 倒序 + 可读列）

- 状态：`todo`
- 优先级：`P2`
- 波次：Wave 2
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-27
- 结论置信度：`optional`

问题与影响：Flask-Admin 里反馈默认无排序、无“已处理”标记，新旧混在一起，量一多就难分辨哪些还没看 / 没回。（FBK-002 上线后新增 spam 大减，此项紧迫度随之下降。）

方向与要点：

- 给 `Feedback` 加一个轻量状态列（如 `status`：`new` / `handled`，或一个 `handled` 布尔），可空 / 有默认；这是本计划**唯一**需要 alembic 迁移的项。
- 在 `app.py` 的 `_make_model_view(Feedback, ...)` 上配 `column_default_sort=('created_at', True)`（倒序）、`column_list`（挑关键列展示）、可编辑 `status`。
- 无需新页面，全部在现有 admin 内完成。

完成判断：后台默认按最新在前展示；能把一条反馈标为“已处理”并区分未处理项。

Review 关注：admin 是否仍受 HTTP Basic 保护；排序 / 列配置是否只影响展示不改数据；状态列默认值是否对存量安全。

执行证据：（待实施）

### FBK-004 — 表单质量与防滥用（蜜罐 / 分类 / 匿名联系方式）

- 状态：`cancelled`
- 优先级：`P2`
- 波次：（原 Wave 2）
- Drive AI：`unassigned`
- Review AI：`unassigned`
- 依赖：无
- 最后更新：2026-07-27
- 结论置信度：`superseded`

为何取消：本项原是“保留匿名 + 蜜罐 + 人机问题 + 分类”的一揽子表单增强。2026-07-27 拍板**登录才能反馈**（FBK-002）后，其防滥用价值已被更强的登录门槛覆盖——蜜罐、人机问题、匿名联系方式都不再需要。仅剩两点轻量项**并入 FBK-002 顺手做**、不单列：内容 `DataRequired` + 长度上限校验、`feedback_submitted.html` 文案略作丰富（2026-09-21 已随 FBK-002 完成）。

重看触发：若未来决定重新开放匿名反馈（放宽 FBK-002 的登录门槛），再回来评估蜜罐 / 人机问题这类免登录场景的防滥用手段。

执行证据：（不适用，已取消）

## 5. 待决策 / 需你拍板

已拍板（2026-07-27）：

- ✅ **匿名反馈是否保留** → **收紧为“登录才能提交”**（FBK-002）。原待决策 #4。
- ✅ **落库改动接受度** → Wave 1 **零迁移**（身份复用现有 `username` 列）；仅 P2 的 FBK-003 状态列需一次迁移。原待决策 #1。
- ✅ **匿名联系方式 / 分类 / 蜜罐** → 登录门槛后**不做**（FBK-004 `cancelled`）。原待决策 #3、#5 的匿名回访诉求随之消解。
- ✅ **链接拦截**（2026-09-21）→ **不做**。是登录用户发的反馈就足够，不再限制内容是否含链接。原待决策 #2。

仍需你拍板：

1. **通知收件人**：新反馈邮件发到哪个邮箱？代码已读 `FEEDBACK_NOTIFY_TO`（未配置则跳过发信、只记 warning）；需在 ohmywod-ops 渲染进 `local_config.py`（非密钥可放 `group_vars/all/vars.yml`，想避免明文进 ops 仓库则放 sops）。阻塞 FBK-001 真实联调。
2. **是否顺带存 `user_id`（外键）**：Wave 1 用 `username` 文本已够定位到人；若你希望后台能直接跳到用户、或未来按用户聚合反馈，可以后补一列 `user_id`（一次迁移）。非必需，默认先不做。
3. **是否要“回复用户”能力**：登录用户已带 `email`，理论上站长可主动回信。本计划暂**不**做站内回复流程，只让身份可查——确认你认可这个边界。
4. **是否推进 Wave 2（FBK-003）**：需一次 alembic 迁移（可空状态列）；Wave 1 上线后视反馈量再定。

## 6. 明确不做（本文范围外）

- 站内工单 / 客服会话系统、反馈多轮对话 / 站内回复流程。
- 公开的反馈墙 / 投票 / 路线图。
- 反馈自动分类、情感分析等“智能”处理。
- 注册邮箱验证、账号体系改造。
- 面向未登录用户的防滥用（蜜罐 / 验证码 / 人机问题）——已由登录门槛覆盖，除非将来重新开放匿名反馈。

## 7. Changelog

### 2026-09-21 — Wave 1 实施（FBK-001、FBK-002）

- Drive AI：Claude Code (Opus 5)；Review AI：未安排。
- 关联事项：FBK-001 `todo → in_progress`，FBK-002 `todo → in_progress`；`document_status` `draft → in_progress`。分支 `feature/feedback-improvement`（基于 main `b43e5a4`）。
- 拍板变更：**取消链接拦截**——是登录用户发的反馈就足够；FBK-002 标题、要点、完成判断与第 1、5 节同步改写。
- 改动：
  - `ohmywod/views/frontend.py`：`/feedback` 加 `@login_required`；`FeedbackForm` 去掉 `username`、`feedback` 加 `DataRequired` + `Length(max=5000)`；入库用 `current_user.username`；创建后调用 `send_feedback_notification`。
  - `ohmywod/mailer.py`：新增 `send_feedback_notification`（best-effort；收件人 `FEEDBACK_NOTIFY_TO`，未配置则跳过）。
  - `ohmywod/templates/emails/feedback_notification.txt`：新增纯文本通知模板。
  - `ohmywod/config.py`、`configs/templates/ohmywod_local_config.py.template`：加 `FEEDBACK_NOTIFY_TO = ""`。
  - `ohmywod/templates/feedback.html`、`feedback_submitted.html`、`login.html`：表单简化、显示登录身份、字段错误、论坛 `[post:16014199]` 兜底入口。
  - 测试：`tests/test_feedback.py` 新增 8 例；`tests/test_views.py`、`tests/test_ratelimit.py` 随登录门槛调整。
- 关键取舍：收件人未配置时**跳过而非回落到 `MAIL_DEFAULT_SENDER`**（发件地址是 noreply，回落只会退信）；保留按 IP 限流作为登录用户的兜底；不做链接过滤、不做 `user_id` 列、无迁移。
- 验证：`pytest tests/` 164 passed；本地渲染一封通知邮件内容正确（主题含用户名、正文含内容与后台链接）。
- 发生的问题：无。
- 剩余风险：生产 `FEEDBACK_NOTIFY_TO` 未配置前通知静默跳过（有 warning 日志）；未做真实发信联调；spam 降幅需上线后对照。
- 下一步：站长提供收件邮箱 → ohmywod-ops 渲染 `FEEDBACK_NOTIFY_TO` → 合并分支、部署 → 真实提交一条反馈验证邮件 → 一段时间后核对新增反馈中的 spam 比例，满足后把 FBK-001/002 转 `done`；再决定是否做 Wave 2（FBK-003）。
