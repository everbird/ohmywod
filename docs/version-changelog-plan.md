---
document_id: ohmywod-version-changelog-plan
document_status: active
verification_status: pending_release
language: zh-CN
created_at: "2026-10-04"
last_updated: "2026-10-04"
---

# 网站版本展示与更新日志计划

## 1. 目标与边界

每次正式发布都有一份简短、可读的 changelog；用户能够在网站上看到当前运行版本和应用 Git commit，并进入页面查看具体变化。

沿用 Flask + Jinja 和现有 Git tag 部署方式，以个人项目的**实用、简单、清晰**为准。本期不增加数据库表、后台编辑器、发布管理平台、前端框架或自动版本号系统，也不在运行时调用 GitHub API。

**当前状态：** 已在 `feature/version-changelog` 实现并完成本地预览与反馈调整，按用户授权进入提交/PR 阶段；尚未合并到 main、创建发布 tag 或部署生产。下文的 `v2.4` 仅为下一版格式示例，不表示已经决定下一版编号或创建了该 tag。

## 2. 实施前基础

下表保留 2026-10-04 开始实施前的基线；当前完成情况见第 7、9 节。

| 现状 | 对方案的影响 |
|---|---|
| 应用当前为 `v2.3`，commit `2d6da9a` | 版本标签与代码提交已有明确对应关系 |
| ops 已支持显式 fetch tags，当前 `app_ref: "v2.3"` | 不需要另造发布流程，继续按 tag 部署 |
| 应用 checkout 中保留 `.git`，服务器已安装 Git | 可以在 web 启动时只读识别版本，不必新增生成文件 |
| [`app.py`](../ohmywod/app.py) 已有模板 context processor | 可以统一向页面提供版本信息 |
| 普通页面共用 [`base.html`](../ohmywod/templates/base.html) | 统一补版本行和更新日志入口 |
| 手机 standalone 模式隐藏版权 `#footer` | 版本行独立放在主内容区底部，版权块隐藏时仍可见；按用户反馈不增加侧栏信息 |
| [`report_reader.html`](../ohmywod/templates/report_reader.html) 是独立的旧 WoD 布局 | 首版不强行加入版本栏，保留返回战报详情的入口 |
| 尚无 changelog 文件、页面或版本 helper | 本次需要新增这些小型组件 |
| 生产 `local_config.py` 整体替代默认配置类 | 不靠新增 `DefaultConfig.VERSION` 等字段传版本，避免多处维护或改变配置继承语义 |

这里的 commit 是**应用仓 `everbird/ohmywod` 的提交**，不是 ops 仓的提交。

## 3. 推荐的最小方案

1. **记录：** `docs/changelog.md` 是用户更新记录的唯一真值，和代码一起评审、提交、进入 tag。
2. **识别：** web 启动时从应用 checkout 读取实际 HEAD、精确指向 HEAD 的正式 tag、工作区修改状态。
3. **展示：** 普通页面用一行低调版本信息；匿名 `/changelog` 页面展示历史记录和当前运行信息。
4. **更新：** 正常 tag 部署并重启 web 后，版本信息和 changelog 一起更新，不额外做同步系统。

实际改动位置：

| 位置 | 内容 |
|---|---|
| `docs/changelog.md`（新增） | 人工维护的版本记录 |
| `ohmywod/release.py`（建议新增） | 只读 Git 识别、状态降级、changelog 读取与渲染 |
| `ohmywod/app.py` | 每个 Flask app 实例启动时加载并缓存快照，context processor 只返回缓存 |
| `ohmywod/views/frontend.py` | 匿名 GET `/changelog` |
| `ohmywod/templates/changelog.html`（新增） | 当前运行信息、版本目录及更新内容 |
| `ohmywod/templates/_release_info.html`（建议新增）与 `base.html` | 共用版本行，避免各处拼接规则不一致 |
| `requirements.txt`、相关测试 | 一个轻量 Markdown 渲染依赖及必要回归 |

## 4. Changelog 怎么写

### 4.1 单文件、人工整理

- 新版本放在顶部，每版优先写 3～8 条用户能理解的变化；有意义的维护事项也可以记录。
- 分组建议为「新增」「改进」「修复」「移除」，没有内容的组不写。
- 不自动把所有 Git commit 倒进日志；merge、格式调整和零碎文档提交不必逐条展示。
- 有使用方式变化、兼容性影响或需要用户操作时，直接说明，例如「仍需联网使用」。
- 不包含凭据、用户数据、私有 ops 配置或内部机器信息；不把未解决的 review 问题写成已修复。
- 版本号兼容现有 `v2.3` 两段格式，也允许以后使用 `v2.3.1`。不要为了格式统一重命名历史 tags。

建议格式如下；这是样例，不是本次新增的实际 changelog 文件：

```markdown
# 更新日志

## [Unreleased]

### 新增
- 网站版本信息与更新日志页面。（完成后记录，发布前移入正式版本）

## [v2.3] - 2026-10-04

### 修复
- 桌面端不再出现手机快捷导航标题和搜索图标，手机端继续保留顶栏。
- 更新自定义样式的缓存标识，避免发布后继续使用旧样式。

## [v2.2] - 2026-10-04

### 新增
- 手机桌面安装所需的 manifest 和图标，及独立窗口内的站内导航适配。

### 改进
- 战报宽表在阅读内容区横向滚动，不再撑大页面。

> 战报仍需联网查看，本版本不提供离线缓存。
```

网站默认不展示 `[Unreleased]` 段，开发计划继续放在计划文档里。日期是**版本发布日**，不能简单取 commit 日期：例如 `v2.1` 的标签创建于 2026-10-04，但对应 commit 日期是 2026-09-30；轻量 tag 也没有可直接使用的 tagger 日期。历史日期不足以确认时如实注明，不猜。

### 4.2 首批历史记录

首版先补齐事实清楚的 `v2.1`、`v2.2`、`v2.3`，以后每次正式发布都必须有记录。旧 `v1.x` / `v2.0` 可分批补录，不把全面历史考古作为功能上线前提。

| 版本 | 对应应用 commit | 回填依据 |
|---|---|---|
| `v2.3` | `2d6da9a` | 桌面顶栏隐藏保护、自定义 CSS 缓存版本；PR #11 |
| `v2.2` | `2bdd7c6` | PWA 元信息、手机导航、阅读器布局与交互收尾；PR #10。不要写成所有真机安装已通过 |
| `v2.1` | `97f463a` | 比较 `v2.0..v2.1`，按实际改动整理认证、支持方式、性能、反馈等记录；不能因为它标记 PWA 前基线，就误写成只改了一份 PWA 计划 |

具体内容应以对应 tag 的代码差异和已交付结果为准，不仅照抄计划中的状态或 commit 标题。

## 5. 当前运行版本怎么识别

### 5.1 读取真实代码，启动时缓存

- 以应用代码位置定位 checkout 根目录，不依赖进程 cwd，不误读到旁边的 ops 仓或其他父仓库。
- 读取完整 HEAD SHA；显示短 SHA（建议 7 位），外链使用完整 SHA。
- 找到**精确指向 HEAD**、符合 `v数字.数字` 或 `v数字.数字.数字` 的正式 tag；兼容轻量和 annotated tag。
- 不取仓库中最大的 tag，不取远端最新 main，也不直接把 ops 的 `app_ref` 当作已经运行的版本。尤其不能把 `git describe` 的“最近祖先 tag”当作当前正式版本。
- 工作区修改检查包括 staged、unstaged 和未忽略的新文件；`.venv`、`.data`、`local_config.py`、生成的 Supervisor/Redis 配置等既有 ignored 文件不算本地修改。
- Git 调用使用固定 argv、固定目录和短超时；沿用 ops 的**单次 `safe.directory=<应用根目录>`** 处理 root/everbird 属主差异，不改全局 Git 配置，不使用 `safe.directory=*`。
- 设置 `GIT_OPTIONAL_LOCKS=0`（或使用 `--no-optional-locks`），避免 `git status` 顺手刷新索引，以及多个 worker 启动时争抢可选锁；不执行 fetch、checkout 或任何 Git 写操作。
- 版本与已渲染 changelog 缓存在当前 Flask app 实例内；这条展示路径在请求期间不执行 Git、不重新扫描文件、不访问网络，也不把缓存放进 Redis。现有业务请求的数据库、Redis 等行为不变。

建议降级口径：

| 启动时状态 | 页面展示 |
|---|---|
| 工作区干净，HEAD 对应唯一正式 tag | `v2.4 · abc1234` |
| HEAD 有效，但没有精确正式 tag | `未打标签 · abc1234`，不冒充最近的正式版本 |
| 工作区有本地修改 | `v2.3 + 本地修改 · 2d6da9a`，或 `未打标签 + 本地修改 · abc1234` |
| 多个不同正式版本 tag 指向同一 HEAD | `版本待确认 · abc1234`；记录警告，不静默猜 ops 想部署哪一个 |
| 无 `.git`、Git 不可用、权限错误或超时 | `版本信息暂不可用`；页面正常工作，不伪造版本或 commit |

dirty 状态下的 SHA 只是**基准提交**，不是本地修改内容的哈希。未知状态不生成错误的 GitHub commit 链接，也不向用户输出内部路径或 Git stderr。

### 5.2 启动快照与发版边界

正在运行的旧 worker 不能因为磁盘先 checkout 了新代码，就提前显示新版本。版本和 changelog 都在启动时加载，随正常 web 重启切换到新快照；不做零停机一致性平台。

开发时修改 Markdown、模板或补打 tag 后，需明确重启本地 `web` 来刷新快照，不假设 Gunicorn 的 Python `--reload` 会监听这些文件。

正常发版中，changelog 更新本身会产生新 commit，因此现有 ops 的「HEAD 变化 → 重启 web」已够用。若只在**同一个 commit** 后补 tag，ops 可能不会重启 web；届时须明确刷新 web，不能以 fetch 成功推断页面版本已刷新。首版无需为这个特殊情况新增部署元数据文件或平台。

## 6. 页面与入口

### 普通页和 PWA

推荐一行低调文字，例如：`v2.4 · abc1234 · 更新日志`。

- 只在主内容区域底部展示一条版本行，不在侧栏加入版本、commit 或更新日志信息，恢复原有侧栏底部账号/收起按钮布局。
- 使用一个模板片段，不增加固定顶栏、悬浮徽章或独立的大面板，不占用阅读主内容空间。
- 版本行位于版权 `#footer` 外、主内容容器内；手机 standalone 隐藏版权块时仍保留版本入口，不恢复完整网页式页脚。
- 版本号链接到 `/changelog#v2-4`，更新日志链接到 `/changelog`；站内导航保持当前窗口。没有对应记录时链接到日志页并提示「当前版本记录尚未补录」，不要生成死锚点。
- 有明确正式 tag 的 commit 可链接到公开应用仓的 `https://github.com/everbird/ohmywod/commit/<完整SHA>`，站外链接按现有习惯处理；未打标签的本地 commit 只显示文本，避免尚未 push 时生成 GitHub 404 链接。
- 页面只显示短 SHA，完整 SHA 可放在日志页当前运行信息中；长字符串必须可换行，不能撑大手机 viewport。
- 不改变 manifest 的 scope（已有 `/` 覆盖新页面），不改独立阅读器栏高，不向 `/r/raw/...` 的用户战报插入站点版本。

### `/changelog`

- 匿名可访问，继承站点现有深色布局；标题用「更新日志」。
- 顶部明确展示**当前运行版本和完整 commit**，下面是从当前 checkout 读取的历史记录，不用文件中的最高版本代替运行版本。
- 首版一个页面就够：版本目录、各版本条目及稳定锚点，如 `v2-3`。暂不做单版本路由、搜索、分页或版本切换器。
- 使用一个轻量 Markdown 库（建议 `markdown-it-py`，实施时选择并固定依赖版本），默认关闭原始 HTML，限制危险链接协议；只渲染仓库中的固定 `docs/changelog.md`，不接收用户上传或任意文件路径，不复用 WoD 报告 sanitizer。
- 版本锚点由受控版本号生成。实际实现使用 Markdown token 流区分顶层版本与 Unreleased，正文由关闭原始 HTML 的渲染器生成，标题、日期与 ID 由 Jinja 输出；不另引入前端插件或手写完整 Markdown 解析器。
- 未打标签或 dirty 的开发预览应明确标记；文件里的下一版条目不能被解释为已在生产发布。
- 文件缺失或渲染失败时记录日志，更新日志页显示说明，不让全站启动失败。回退到旧版本时展示旧 checkout 自带的记录；回退到尚无此功能的历史 tag，不要求旧代码凭空出现新页面。

若实施时新增自定义 CSS，记得更新现有 CSS 缓存版本并覆盖旧缓存场景；本计划不顺带新增资产构建系统。

## 7. 实施清单

本轮为一次小型功能实现，不要求拆成多轮平台建设。分支实现、本地预览及反馈调整已完成，用户已授权提交、push 并开 PR；合并、打 tag 与正式发布留待后续明确授权。

| ID | 状态 | 工作与完成判断 |
|---|---|---|
| REL-001 | `done` | 已建立 `docs/changelog.md`，回填 v2.1～v2.3；标题唯一、事实有 tag 差异依据，没有私人信息 |
| REL-002 | `done` | 只读 Git 识别与 app 启动快照完成，含 dirty/未知/多 tag 降级；固定目录、单次 safe.directory、禁用可选锁及隔离 Git 仓库选择环境变量均有回归 |
| REL-003 | `done` | 匿名 `/changelog`、稳定锚点和主内容底部版本行已实现；按用户反馈移除侧栏版本信息 |
| REL-004 | `in_progress` | 221 项测试、本地 HTTP/HTTPS 与 43 条浏览器检查通过；本地反馈已调整，进入 PR 审核阶段。正式发布及生产验收尚未进行 |

建议最小测试覆盖：

- 精确 tag（轻量/annotated）、无精确 tag、多个 tag、本地修改及 ignored 文件、Git 不可用/超时。
- 固定应用目录和单次 safe.directory；版本、日志按 app 实例缓存，不因其他测试实例或磁盘 HEAD 更新而串状态。
- 匿名日志页 200、正确内容和锚点、隐藏 Unreleased、原始 HTML/危险链接不执行、缺文件时可用。
- 展示短 SHA、链接完整 SHA、当前版本不等于最新历史条目；普通页面只有一条主内容版本行，侧栏不包含该组件。
- 320/390px 手机、768px 断点、1440px 桌面、侧栏收起及短屏；standalone 版权块隐藏时主内容版本行仍可见，旧 CSS 不造成左上角堆叠。

不为此改 `/healthz` 的健康判定，也不把真实手机安装、DR 演练或大量无关测试当作新增日志功能的前置。

## 8. 以后每次怎么发版

1. 开发过程中把已完成、拟随本版发布的变化放入 `[Unreleased]`，计划和未完成事项仍留在计划文档。
2. 发布前整理该段，改为本次确定的版本号与发布日期；**changelog 必须和代码一起提交到发布 commit 中**。
3. 运行测试和开发预览，通过 PR 合并到 `main`。
4. pull 最新 `main`，确认目标版本记录存在，再创建并 push 对应 tag；不要在打 tag 后才补记录并移动原 tag。
5. ops 将 `app_ref` 更新为这个已 push 的 tag；先检查改动，再按现有 `make dry-run` / `make deploy` 流程部署。
6. 验收网站版本/commit、对应日志锚点、首页/登录/阅读路径；源站 HEAD、tag 解析值和页面信息应一致。
7. 成功后提交并 push ops 的版本目标变更。失败或回退不改写既有 tag，不把原发布记录删掉。

**不要把本次发布自己的 commit SHA 硬编码进 changelog 或 VERSION 文件。** 写完它再 commit，SHA 又会变化；合并后的 SHA 也可能不同。当前完整 SHA 从运行 checkout 读取，历史记录通过 tag 链接定位，避免这个自引用问题。

GitHub tag 链接可用 `/tree/v2.4`，相邻版本 diff 可用 `/compare/v2.3...v2.4`。目前并未要求创建 GitHub Release，因此不要把 `/releases/tag/...` 当作一定存在的页面，也不必在 GitHub 和站内各手写一份内容。

## 9. 计划记录

- 2026-10-04：创建草案。确定推荐方向为「一份 Markdown 记录＋启动时 Git 快照＋匿名日志页＋紧凑版本入口」；当时只写计划，没有新增功能、修改 ops、提交/push 或部署。
- 2026-10-04：按用户授权在 `feature/version-changelog` 实现。直接固定现有环境已安装的 `markdown-it-py==4.2.0`，没有升级其他依赖、修改配置类或新增数据库字段。回填 v2.1～v2.3，在 Unreleased 记录本轮功能。
- 2026-10-04：自动验证为 221 项 pytest 通过（268 个已有类别的警告），`pip check` 无依赖冲突。新增 38 个回归用例，含实际临时 Git 仓库、轻量/annotated tag、Git worktree、索引不写入、环境变量隔离、启动快照、HTML/链接安全及页面输出。
- 2026-10-04：仅重启既有 Supervisor `web`，本地 `http://127.0.0.1:8013` 与 `https://agy.everbird.me` 的 healthz、日志页、列表、登录和帮助均 200；Redis、数据库、HTTPS 代理和开发配置保持不变。
- 2026-10-04：Chromium 在 320×500、390×844、767×720、768×900、1024×500、1440×900 检查版本行、短屏侧栏、完整 SHA 换行、锚点和同窗口导航；43 条记录通过。发现原有帮助页的长邮箱在 320px 溢出，增加一行信息卡换行规则，并更新 CSS 缓存版本。
- 2026-10-04：Headless Shell 无法真实模拟 `display-mode: standalone`，仅在隔离浏览器上下文强制启用既有 standalone CSS 条件，确认页脚隐藏后侧栏入口可用；这不是实际安装或真实 standalone 窗口验收。旧 CSS 强制回放下桌面快捷导航仍隐藏。
- 2026-10-04：按本地验收反馈移除侧栏版本信息，恢复侧栏底部账号/收起布局；只在主内容区域底部保留一条版本行，并独立于 standalone 隐藏的版权块。更新相应回归、文档和 CSS 缓存版本，重新运行 221 项测试与 43 条浏览器检查均通过；只重启本地 web 继续预览，Redis、数据库和生产不变。本轮检查与截图位于 `/tmp/ohmywod-version-changelog-main-only/`。
- 2026-10-04：用户授权提交、push 和开 PR，计划进入 PR/后续发布阶段；不合并、不创建 tag、不部署生产。分支提交后本地 web 的版本快照可刷新为「未打标签」与实际分支 SHA，不把新 SHA 硬编码进本文。
- 本轮预览入口：[更新日志](https://agy.everbird.me/changelog)、[全部战报](https://agy.everbird.me/r/all)。版本信息取自当前 web 启动快照；新功能尚未成为正式发布版本。证据位于 `/tmp/ohmywod-version-changelog/` 与 `/tmp/ohmywod-version-changelog-main-only/`（临时目录），正式回归留在 `tests/test_release.py`。
