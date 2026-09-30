---
document_id: ohmywod-pwa-plan
document_status: planned
language: zh-CN
created_at: "2026-09-30"
last_updated: "2026-09-30"
---

# PWA 桌面安装与独立窗口计划

## 1. 目标与范围

用户希望在手机 Firefox / Chrome 中将战报网添加到桌面，之后点击桌面图标，像打开一般 App 一样浏览战报，没有浏览器地址栏、标签栏等常驻界面。

本期交付以这个实际体验为准：**从桌面图标启动，在站内浏览、登录、进入阅读模式和返回时，都保持独立应用窗口。** 仅生成一个打开普通浏览器标签页的快捷方式，不算满足目标。

项目是个人兴趣项目，以实用、简单、清晰为主。沿用 Flask + Jinja 多页面网站，在现有界面上补充安装信息和必要的导航适配。预计半天至一天完成主要改动，真机兼容问题另计。

本期不做离线战报、离线操作、后台同步、推送、应用商店上架，也不引入前端框架或新的构建系统。离线阅读仅为 nice to have，不排期、不作为本期前置条件。

当前状态：已完成代码与官方资料调研；尚未实施，也未进行真机安装验证。本文件记录计划，不代表实现或部署已获验证。

## 2. 显示方式与浏览器边界

采用 Web App Manifest 的 `display: "standalone"`。这种模式面向独立应用窗口，隐藏通常的浏览器导航界面；系统时间、电量、手势区域可以正常保留。`minimal-ui` 仍可能显示浏览器控件，不符合本次目标；也无需通过 Fullscreen API 或强制 `fullscreen` 隐藏整个系统界面。[MDN：display](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/display)

直接在普通浏览器标签页访问网站时，地址栏仍然存在，这是正常行为。验收对象是用户完成安装后，从桌面图标启动的窗口。

用户尚未限定手机系统，按下表安排兼容验证，记录实际设备、系统和浏览器版本，不将某一平台的结果直接推广到另一平台。

| 平台 | 安装路径与预期 | 验证要求 |
|---|---|---|
| Android / Firefox | 通过浏览器菜单的 Install / 安装应用等入口添加到桌面；名称随版本可能变化 | 必验：从图标启动及站内导航均无常驻地址栏 |
| Android / Chrome | 通过“添加到主屏幕 → 安装应用”等入口安装 | 必验：确认实际进入独立窗口；只有普通快捷方式时不能记为通过 |
| iPhone / Firefox、Chrome | 根据系统与浏览器版本，通过分享菜单添加到主屏幕；有“作为 Web App 打开”选项时保持开启 | 单独记录安装入口和启动表现；未实测时标记未验证，若用户使用 iPhone，则作为目标设备必验 |

Mozilla 提供了 Firefox Android 的 Web App 安装流程，Chrome 也提供了移动端手动安装入口；不同浏览器的系统集成程度可能不同，本项目不要求图标角标、应用列表或卸载入口完全相同。[Mozilla 安装说明](https://support.mozilla.org/en-US/kb/use-web-apps-firefox-android)、[Chrome 安装说明](https://developer.chrome.com/blog/how_chrome_helps_users_install_the_apps_they_value)

iOS 的添加入口与 Android 不同，不能依赖 `beforeinstallprompt` 实现统一安装按钮；较新的 iOS 还允许用户选择是否作为 Web App 打开。若某个目标浏览器没有相应入口，记录具体限制和可用的 Safari 路径，不把替代路径计为该浏览器已验收。[MDN：安装与平台差异](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)、[WebKit：主屏幕 Web App 行为](https://webkit.org/blog/16993/news-from-wwdc25-web-technology-coming-this-fall-in-safari-26-beta/#every-site-can-be-a-web-app-on-ios-and-ipados)

## 3. 现有基础与改动位置

| 现状 | 对本期实现的影响 |
|---|---|
| 主站页面使用 [`base.html`](../ohmywod/templates/base.html) | 可以集中接入 manifest、图标和主题色 |
| [`report_reader.html`](../ohmywod/templates/report_reader.html) 是独立模板 | 必须单独接入同一份安装信息，避免从阅读页安装时遗漏 |
| 已有移动端 viewport、响应式布局、阅读器“返回”入口 | 按真机表现补少量样式和导航，无需重做界面 |
| [`landing.html`](../ohmywod/templates/landing.html) 的部分站内示例链接使用 `target="_blank"` | 调整为当前窗口导航，减少从应用跳到新窗口的情况 |
| 现有 Logo 位于 `ohmywod/static/img/` | 复用图形，导出适合安装的尺寸与留白 |
| 部署模板已配置 HTTPS，静态资源由现有应用提供 | 初步不需要新增服务、修改数据库或调整运维架构；实施时检查实际响应 |
| 当前没有 manifest 或 Service Worker | 首版从 manifest 与图标开始，不增加离线缓存层 |

## 4. 实施步骤

### PWA-001：接入 manifest 与安装图标

状态：`todo`

- 新增 `ohmywod/static/manifest.webmanifest`，由现有静态资源路径提供，无须为此增加动态接口。
- 固定应用身份与入口：`id: "/"`、`name: "OhMyWoD 战报网"`、`short_name: "战报网"`、`lang: "zh-CN"`、`start_url: "/r/all"`、`scope: "/"`、`display: "standalone"`。启动页使用无需登录的全部战报页；所有页面共用同一份 manifest。
- 设置与现有界面协调的 `theme_color` 和 `background_color`，不锁定屏幕方向，保留横屏阅读长表格的能力。
- 从现有 Logo 导出 192×192、512×512 PNG，以及 180×180 Apple Touch Icon；为 Android 准备有适当安全留白的 maskable 图标，避免系统裁切主体。
- manifest 中的图标使用明确的站点根路径，如 `/static/img/pwa-192.png`，避免相对路径解析错误。
- 新增小型共享模板 `ohmywod/templates/_pwa_head.html`，包含 manifest 链接、主题色、Apple Touch Icon 及必要的 Apple Web App 兼容标签；由 `base.html` 和 `report_reader.html` 引入。
- 检查 manifest 与图标均能匿名通过 HTTPS 取得，manifest 返回合适的 MIME 类型（优先 `application/manifest+json`）。若当前静态服务映射不正确，再作最小修正。

`scope` 显式设为 `/`，覆盖 `/r/`、`/login`、`/profile` 等站内路径；它定义应用内导航范围，与 Service Worker 的 scope 是不同概念。跨出范围的页面可能触发浏览器界面，因此不能仅把范围设成 `/r/`。[MDN：scope](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/scope)

完成判断：从普通页面和独立阅读页都能读取同一份有效 manifest；图标正确；在目标手机上完成一次真实安装与独立窗口启动，再继续细化体验。

### PWA-002：补齐独立窗口内的导航与布局

状态：`todo`，依赖：PWA-001

- 主站内部链接优先使用当前窗口，调整 `landing.html` 中打开战报和阅读器的 `_blank` 链接；不全局拦截所有链接。
- 验证“全部战报 → 战报详情 → 阅读模式 → 子页 → 返回详情”的完整路径，以及“登录 → 我的目录 / 收藏”的路径，都停留在应用窗口中。
- 保留清晰的首页、目录、返回入口。阅读器现有“返回”指向战报详情，可以继续使用，不依赖浏览器工具栏，也不只依赖 `history.back()`。
- WoD 官网、赞助等站外链接允许交给浏览器处理。外部页面出现地址栏属于正常边界，不要求把站外网站包进本应用。
- 根据真机结果调整屏幕顶部、底部安全区和可视高度。需要时使用 `env(safe-area-inset-*)`、动态视口单位；若增加 `viewport-fit=cover`，配套处理控件留白，避免直接套上后被刘海或手势区遮挡。
- 检查软键盘、横竖屏切换、长战报滚动、浮窗与链接复制。只修影响日常使用的问题，不进行整站视觉重设计。
- 登录继续使用现有会话机制，验证安装窗口中的登录、登出和重开表现；不要求跨浏览器共享登录态，也不顺带改造成永久登录。

完成判断：关键路径无需地址栏或浏览器返回按钮即可完成，页面控件可见、可操作，阅读与登录功能正常。

### PWA-003：提供简短的安装说明

状态：`todo`，依赖：PWA-001

- 在现有帮助页 `ohmywod/templates/help.html` 增加“添加到手机桌面”说明，侧边栏已有帮助入口，可以直接复用。
- 分别说明 Android Firefox、Android Chrome 和 iPhone 的操作路径；文案以真机菜单为准，说明“完成后从桌面图标打开”。
- 首版使用浏览器自带安装入口即可，不依赖自动安装横幅、弹窗或站内安装按钮。
- 已经添加过旧版普通快捷方式的用户，提示移除旧图标后按新流程重新安装。
- 说明需要联网使用；不宣传离线能力。

完成判断：用户能按简短说明安装，并理解普通网页访问与桌面应用启动的区别。

### PWA-004：验证并记录结果

状态：`todo`，依赖：PWA-001～003

本地先检查 manifest JSON、资源响应与两个模板的实际输出；按改动范围运行现有相关测试。核心验收使用手机实际安装，不以桌面模拟移动视口或 Lighthouse 分数代替。

| 检查项 | 通过标准 |
|---|---|
| 安装 | 目标浏览器可完成添加，桌面名称与图标正确 |
| 从桌面启动 | 打开约定入口，页面稳定后没有常驻地址栏、标签栏 |
| 站内导航 | 浏览列表、搜索、战报详情、阅读子页和返回均保持独立窗口 |
| 登录流程 | 登录、收藏、我的目录、登出正常；相关跳转不落入普通浏览器页 |
| 阅读体验 | 长表格可滚动，横屏可用，浮窗、锚点复制和返回入口正常 |
| 移动布局 | 系统状态栏、手势区及软键盘不会遮挡主要操作 |
| 外链与重开 | 外链可访问，能返回战报网；关闭后再次点图标仍能正常进入 |
| 普通网页回归 | 在普通浏览器标签页中仍可浏览、登录和上传 ZIP |

若已安装后仍有地址栏，优先检查：是否误建成普通快捷方式、是否沿用了旧安装信息、manifest 是否被正确读取、`display` 是否生效、当前 URL / 登录重定向是否在同源 `scope` 内、是否打开了新窗口。不要直接把“补一个 Service Worker”当作默认修复。

当前真机验证记录如下；实施后填写设备和版本。缺少目标设备时保留“待验证”，不能把代码完成等同于该平台验收通过。

| 设备 / 系统 | 浏览器与版本 | 从图标启动无地址栏 | 站内导航 | 状态 |
|---|---|---|---|---|
| Android，待填写 | Firefox，待填写 | 待验证 | 待验证 | 未开始 |
| Android，待填写 | Chrome，待填写 | 待验证 | 待验证 | 未开始 |
| iPhone，待填写 | Firefox / Chrome 分别记录 | 待验证 | 待验证 | 未开始 |

## 5. 保持实现简单

首版不注册 Service Worker，不引入 Workbox、Cache Storage 或 IndexedDB。安装与独立窗口是本期目标；Chrome 已放宽菜单安装对 Service Worker 的要求，不能沿用旧教程把离线缓存当作安装的必做项。[Chrome：安装条件调整](https://developer.chrome.com/blog/update-install-criteria)

如果目标手机实测遇到安装兼容问题，先查明实际原因，再决定最小兼容处理；即使最终需要 Service Worker，也不自动扩展为离线战报项目。文档和代码都不承诺任意浏览器、任意系统版本具有完全相同的外观。

应用更新沿用网站发布流程。首版没有新增应用缓存层，不需要设计缓存版本迁移、离线内容失效、数据冲突合并或同步队列。图标和安装信息的更新由浏览器处理，开发验证时可重新安装确认。

## 6. 后续可选项

以下仅记录方向，不纳入本期工作量和验收：

- 离线战报：只有未来确实需要断网阅读时，再评估“手动下载某份战报”的最小方案。
- 系统分享菜单、阅读位置记忆、站内安装按钮：使用一段时间后，按实际便利程度决定是否增加。

## 7. 变更记录

- 2026-09-30：创建计划。明确本期只围绕手机桌面安装和无浏览器地址栏的独立窗口体验；离线战报降为未排期的 nice to have。仅完成文档，尚未实施。
