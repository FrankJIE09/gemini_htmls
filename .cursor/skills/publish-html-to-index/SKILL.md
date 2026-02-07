---
name: publish-html-to-index
description: Renames a given HTML file with mv to a user-specified name, adds a new list item to the <ul> in index.html (lines 37-51), then commits and pushes. Use when the user provides an HTML file and asks to rename it, publish to index, or add to the index list and push.
---

# 将 HTML 重命名并发布到 index

当用户传入一个 HTML 文件并要求「重新命名」或「发布到 index」时，按以下流程执行。

**重要**：写入 index 是指**在 index.html 的 `<ul>` 中新增一个列表项**（一条链接），**不是**把源 HTML 的内容复制/覆盖到 index.html。index.html 保持为入口列表页，只在其 `<ul>` 里追加 `<li><a href="...">显示名</a></li>`。

## 触发条件

- 用户明确指定了一个 HTML 文件路径（或当前仓库内的 HTML 文件名）
- 用户给出了新的文件名（重命名目标）
- 用户意图包含：重命名、发布到首页、更新 index、提交并推送 等

## 执行步骤

### 1. 确认输入

- **源 HTML**：用户指定的文件（如 `1.html`、`xxx.html`）
- **新文件名**：用户要求的新名字（如 `my-tool.html`），仅文件名，扩展名保持 `.html`
- **显示名**（可选）：index 列表里该链接的文案。若用户未提供，用新文件名去掉 `.html` 并做可读化（如 `car_dashboard.html` → `Car dashboard`）作为显示名。

若用户未给出新文件名，主动询问「新文件名要叫什么？」。

### 2. mv 重命名 + 在 index 的列表 (ul) 中追加一项

1. 用 **mv** 把源文件直接重命名为新文件名：`mv 源文件 新文件名`  
   路径相对于仓库根，正斜杠。新文件名若含子目录则先建目录再 mv。

2. **在 index.html 的 `<ul>` 中追加一条链接**（不要用源 HTML 内容覆盖 index.html）：编辑 `index.html`，在 `<ul>...</ul>` 内（约第 37–51 行），在 `</ul>` 前**新增一行**：
   ```html
   <li><a href="./新文件名">显示名</a></li>
   ```
   - `href` 用新文件名（含子路径时如 `./demos/foo.html`）。
   - 中文等需保留原样；若文件名含中文，href 可用 URL 编码（与现有条目如 Mermaid 一致）。

### 3. Git 提交与推送

1. `git add` 涉及的文件（新文件名、index.html、以及被 mv 掉的源文件名）。
2. `git commit`，提交信息建议格式：`publish: 将 xxx 发布为 [新文件名] 并更新 index`（可据实际情况微调）。
3. `git push`（若用户仅要求提交不要求推送，则只做到 commit）。

若仓库无远程或 push 失败，在回复中说明结果并提示用户检查远程与权限。

## 示例

**用户**：「把 1.html 改名为 car-dashboard.html，显示名写“车况看板”，更新到 index 并推送」

1. `mv 1.html car-dashboard.html`
2. 在 index.html 的 `</ul>` 前插入：`<li><a href="./car-dashboard.html">车况看板</a></li>`
3. `git add index.html 1.html car-dashboard.html`
4. `git commit -m "publish: 将 1.html 发布为 car-dashboard.html 并加入 index"`
5. `git push`

**用户**：「把 1.html 改名为 portfolio_dashboard.html，更新 index 然后提交」（未给显示名）

1. `mv 1.html portfolio_dashboard.html`
2. 在 index.html 的 `</ul>` 前插入：`<li><a href="./portfolio_dashboard.html">Portfolio dashboard</a></li>`（由文件名推导显示名）
3. `git add` 后 commit，按用户是否要求推送决定是否 push

## 注意

- 所有文件路径以**项目根目录**为基准，不要使用 Windows 反斜杠。
- 在 PowerShell 中可用 `Move-Item` 替代 mv，或使用 `git mv` 以便 Git 正确识别重命名。
- **禁止**将源 HTML 文件内容复制或覆盖到 index.html。index 的更新**仅限**在 `<ul>` 与 `</ul>` 之间（约第 37–51 行）追加一个 `<li><a>...</a></li>` 条目。
