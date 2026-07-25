# `ohmywod` 代码评审与三方交叉评估

- **日期**：2026-07-25
- **评审者**：Antigravity
- **评审基线**：`ohmywod` 仓库代码
- **交叉评审对象**：
  - `2026-07-25-review.md`（Claude / Opus 4.8）
  - `2026-07-25-cross-review-codex.md`（Codex）
- **定位与标准**：个人兴趣项目，以**实用、清晰、高性价比（投入产出比）**为唯一衡量标准，不搞工业级形式主义。

---

## 总体评估与结论

针对 `ohmywod` 应用仓，综合分析 Claude 与 Codex 的评审报告并核对源码后，**综合结论如下**：

1. **Claude 的初评**抓住了基础安全与运维隐患（Open Redirect、Zip 暂存堆积、用户名大小写），但**漏掉了两个极其关键的路径逃逸与数据逻辑缺陷**。
2. **Codex 的二次交叉评审非常精准**，通过深入源码发现了用户名/分类名路径逃逸、以及软删除对 raw/ID 视图失效的严重问题，并指出了 Claude 推荐修复函数在特定依赖版本不存在的问题。
3. **Antigravity 在源码层面的验证结果**：完全证实 Codex 提出的两大核心风险。针对个人兴趣项目，无需引入复杂校验库，仅需增加几处极简的字符限制与条件过滤即可解决 95% 以上的隐患。

目前测试集中为 **`67 passed, 180 warnings`**（180 项均为 Python/SQLAlchemy 废弃告警）。项目整体架构简洁清晰，只需针对以下几点做极小成本的收尾。

---

## 三方交叉对比与逐项裁决

### 1. [高风险] 用户名与分类名可能导致文件路径逃逸出 `DATA_DIR` / `UPLOAD_DIR`

- **代码位置**：
  - `ohmywod/views/frontend.py:103-109`（注册用户名校验）
  - `ohmywod/views/report.py:511-518`（新建分类名校验）
  - `ohmywod/views/upload.py:75-103`（解压与上传落盘路径 `Path(DATA_DIR) / category.owner / category.name / filename`）
- **问题分析**：
  - **Claude 判定**：漏报。仅关注了 Zip 内部成员的 Zip-Slip 逃逸。
  - **Codex 判定**：**正确捕获**。在 Python 中，`Path('/var/data') / owner / '/tmp/abc'` 遇上以 `/` 开头的绝对路径时，前面的根目录会被直接丢弃；包含 `..` 时会向上级目录逃逸。加上生产环境 Gunicorn 以 root 运行，风险极其显著。
  - **Antigravity 评估**：**完全同意 Codex**。即使 Zip 成员文件名安全，根目录逃逸也能让文件落到系统任意位置。
- **实用修法（最简且有效）**：
  - 在注册 `validate_username` 和创建分类 `validate_name` 表单校验中，加入正则限制：仅允许字母、数字、中文、下划线、中划线和空格，拒绝包含 `/`、`\`、`..` 或绝对路径。
  - 在 `upload.py` 写入前加一行兜底断言：`tpath.resolve().is_relative_to(Path(data_dir).resolve())`。

---

### 2. [中高风险] 战报/分类“删除”后，已有链接与 `/raw/` 路径仍可被公开访问

- **代码位置**：
  - `ohmywod/controllers/report.py:50-75`（删除仅置 `status = 1`）
  - `ohmywod/views/report.py:145-189`（`/raw/...` 完全不查数据库，只看磁盘文件）
  - `ohmywod/views/report.py:192-210`, `:325-342`（按 id 获取分类/战报时不过滤 `status`）
- **问题分析**：
  - **Claude 判定**：漏报。
  - **Codex 判定**：**正确捕获**。用户界面显示“删除”，但拿着旧 ID 链接或 raw 路径依然能看内容，属于符合直觉的逻辑 BUG。
  - **Antigravity 评估**：**完全同意 Codex**。个人分享站的删除诉求通常就是“让分享链接失效”。
- **实用修法**：
  - `ReportController.get_report` / `get_category` 默认增加 `status == None` 过滤。
  - `/raw/<username>/<category>/<name>/` 路由增加一次极轻量的 DB 状态查询，若分类或战报已置为已删除（`status == 1`），直接 `abort(404)`。

---

### 3. [中风险] 上传 Zip 暂存文件成功后未删除，坏 Zip 抛 500 且遗留垃圾

- **代码位置**：
  - `ohmywod/views/upload.py:85-128`
  - `tests/test_views.py:403-408`, `:438-442`
- **问题分析**：
  - **Claude 判定**：正确发现成功路径没有删除 `UPLOAD_DIR` 中的 zip，磁盘满会导致全站无法上传。
  - **Codex 判定**：同意 Claude，并补充指出：现有 `test_views.py` 测试断言中错误地将“Zip 必须保留”写成了预期；且未捕获 `BadZipFile` 异常。
  - **Antigravity 评估**：**三方达成一致**。
- **实用修法**：
  - 使用 `try...finally` 结构，确保解压流程结束后无条件执行 `fpath.unlink(missing_ok=True)`。
  - 显式捕获 `zipfile.BadZipFile`，向前端返回 400 错误提示，而不是触发 500 服务器崩溃。
  - 同步修改 `test_views.py` 中对应的断言，使其符合删除 Zip 的正确预期。

---

### 4. [低风险] 登录 `next` 参数存在开放重定向（Open Redirect）

- **代码位置**：
  - `ohmywod/views/frontend.py:67-69`
- **问题分析**：
  - **Claude 判定**：正确指出 `/login?next=https://evil.com` 风险，但建议使用 `flask_login.utils.url_has_allowed_host_and_scheme`。
  - **Codex 判定**：指出 **Flask-Login 0.6.3 并没有该函数**，建议直接判断 `next.startswith('/') and not next.startswith('//')`。
  - **Antigravity 评估**：**同意 Codex 的纠错**。单行字符串判断最干净可靠，无需依赖第三方 API。
- **实用修法**：
  - 跳转前检查 `if next_url and next_url.startswith('/') and not next_url.startswith('//'):` 允许跳转，否则回首页。

---

### 5. [低风险] 用户名大小写重名导致登录歧义

- **代码位置**：
  - `ohmywod/controllers/user.py`（注册精确匹配，登录 `lower().first()`）
- **三方共识**：
  - 属于极边角逻辑矛盾。按 Claude/Codex 共同建议：注册查重时改为不区分大小写的 `get_by_login` 逻辑即可，堵住新数据，不需去动 SQLite 存量数据库。

---

### 6. 其余低优先级项目总结

| 事项 | 三方评估结论 | 建议处理方式 |
|---|---|---|
| `per_page` 无上限 | 三方一致认定为小瑕疵 | 在 `utils.py` 中加上 `min(per_page, 100)` |
| Zip 解压展开体积限制 | Codex 提出解压配额防护 | 属于防御性加固，有空可加，优先级不高 |
| Admin HTTP Basic & CSRF 豁免 | 三方一致认定：个人单人运维，**不必管** | 维持现状 |
| `datetime.utcnow()` 警告 | 仅属于 Python 升级告警，**不必管** | 维持现状 |

---

## 推荐的最小动作清单（按优先级排序）

1. **[必做] 堵住路径逃逸**：对用户名和分类名格式做表单字符限制（禁止 `/`, `\`, `..`）。
2. **[必做] Zip 清理与坏包处理**：`upload.py` 用 `finally` 清理 zip，捕获 `BadZipFile` 返回 400，更新单元测试。
3. **[必做] 修复删除生效逻辑**：`get_report`/`get_category` 和 `/raw/` 增加 `status` 过滤。
4. **[顺手做] 修复 `next` 重定向**：使用 `startswith('/') and not startswith('//')`。
5. **[顺手做] 修复注册用户名大小写查重**。
