# 广告展示优化方案（2026-07）

目标：提高 AdSense 的 coverage 和 impression，同时不破坏作为工具网站的使用体验。本文档是方案记录，截至撰写时**尚未实施**。

## 现状诊断

coverage/impression 低的根本原因不是"广告位太少"这么简单，而是唯一的广告位恰好躲开了几乎所有的真实浏览场景：

1. **全站只有一个 AdSense 位**：`ohmywod/templates/base.html` 的 `sidebar_ad` block（slot `3406257966`），位于侧边栏底部，`data-ad-format="auto"` + `data-full-width-responsive="false"`。
2. **移动端基本为零展示**：`base.html` 里移动端默认收起侧边栏（`remember_sidebar = ! is_mobile` 那段逻辑），侧边栏是唯一广告载体，所以移动流量几乎贡献不了任何 impression。
3. **用户停留最久的页面完全没有广告**：阅读模式 `report_reader.html` 是独立 HTML（不继承 base，没有 adsbygoogle 脚本）。用户读一篇长战报可能停留几分钟，这是全站价值最高的注意力，目前收益为零。
4. **战报详情页的主体是 iframe**：`report_details.html` 用 iframe 加载 `report_raw`，iframe 内是原始战报，外层页面除了侧边栏没有任何广告位。
5. **侧边栏单元自身填充率可能不佳**：335px 宽（`--app-sidebar-width`）、auto format、位于 `mt-auto` 底部，viewability 低，unfilled 时直接拉低 coverage。
6. 登录/注册/编辑/设置等页面用 `base_noadsense.html`（sidebar_ad block 替换为 WoD 游戏推广图）——这个设计是对的，**保留不动**。

## 方案（按 ROI 和体验代价排序）

### 第一优先：阅读模式页加"内容尾部"广告位

在 `report_reader.html` 的战报内容**结束之后**（`gadgettable` 表格下方）加一个响应式横幅。

- 读完战报后的自然停顿点，不打断阅读流，是广告干扰最小、注意力质量最高的位置。
- 该页面目前零广告，这一个位置大概率就能带来全站最大的增量。
- 需要在该页面引入 adsbygoogle 脚本（目前没有）。
- 给广告容器设 `min-height` 预留空间，避免 CLS。

### 第二优先：移动端锚定广告（anchor ad）

在 AdSense 后台**只开启 Auto Ads 的锚定格式**（不要全开 Auto Ads），或手动加 anchor 单元。

- 移动端底部悬浮条、用户可主动关闭，是工具站公认体验代价最小的移动变现方式。
- 移动端现在是零 impression，这一项等于凭空多出一个流量池的收入。
- 主要在 AdSense 后台操作，代码侧改动很小或为零。

### 第三优先：战报详情页加一个横幅

在 `report_details.html` 的 action bar（浏览/点赞/收藏按钮那一排）下方加一条横幅。

- 位于 iframe 之后，不推挤战报内容，不影响"看战报"这个核心动作。

### 第四优先：修复现有侧边栏位

- auto format 换成固定 `300x250`（中矩形是填充率最高的尺寸），或 `300x600` 提升桌面 CPM。
- 位置从 `mt-auto` 底部上移到导航菜单之后，提高首屏可见性。

### 可选（工作量较大，先不做）：列表页 in-feed 原生广告

在 `root.html` / `category.html` / 搜索结果里每 8–10 个条目插一个 in-feed 单元，样式匹配 list/card 双布局。收益不错但要适配两套布局，等前三项数据出来后再决定。

## 明确不做的

- **战报内容中间插广告**：内容在自己控制的 iframe（`report_raw`）里，往自建 iframe 塞 AdSense 违反政策，而且毁掉核心体验。
- **全开 Auto Ads**：会在工具型界面里乱插（比如表单和按钮之间），得不偿失。
- **插页/vignette 全屏广告**：对回访型工具站是留存杀手。

## 配套事项

- 每个新广告位需要先在 AdSense 后台建好对应的 slot ID。
- 确认 `ads.txt` 在生产环境根路径可访问（模板里有 `templates/ads.txt`，需核实生产上路由和 nginx 实际 serve 情况，不要凭假设）。
- 所有新广告容器预留最小高度，守住 CLS，别为了广告伤了 Core Web Vitals。
- GA4 已接好（`G-TYGCT601XW`），建议分两周对比：先上第一、二优先级，观察 pages/session 和跳出率有没有恶化，再决定是否继续加位。

## 实施顺序建议

1. AdSense 后台建 slot → 阅读模式页尾部位（第一优先）
2. AdSense 后台开锚定广告（第二优先）
3. 观察两周数据（收入 + GA4 体验指标）
4. 数据没恶化 → 上详情页横幅（第三优先）+ 侧边栏调整（第四优先）
5. 再评估是否做列表页 in-feed
