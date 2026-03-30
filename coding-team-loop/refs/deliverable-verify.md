# 验收请求

## 触发条件

以下两种 Issue 均由本流程处理（Claude 空闲时）：

| 来源 | Issue 特征 | 含义 |
|------|-----------|------|
| Step 2-P2 | `verifying` + `owner/claude` | 子 Issue 验收 **或** 父 Issue 最终验收 |
| Step 2-P4 | `verifying` + `owner/codex` | Codex 实现验收 |

（`owner/shuzai` 的 verifying Issue 由 human-handoff 流程处理，不经过此流程）

## 派发消息格式

### 标准验收（子 Issue 或普通 Codex 实现）

```
【OPENCLAW】【验收请求】
Issue #{N}：{Issue标题}

PR 已合并，请验证此功能的主干使用流程是否正常。

需确认：
① 核心功能端到端可用
② 主要用户路径无阻断性问题
③ 无明显回归

验收要点（来自 Issue 验收标准）：
{从 Issue 正文提取的验收条件，若无则省略此行}

完成后请回复：
- 通过：回复【验收通过】并简述验证内容
- 有问题：列出具体问题描述（每条一行）
```

### 父 Issue 最终验收（有子任务的 HUMAN Issue）

**识别方式：** Issue 的 `owner/claude` 且 body **不含** `related to #N`（是 HUMAN 创建的父 Issue），且存在 body 含 `related to #{此Issue编号}` 的已关闭子 Issue。

```
【OPENCLAW】【最终验收请求】
Issue #{N}：{Issue标题}

所有子任务已完成并通过 Claude 验收：
{列出每个子 Issue 编号和标题}

请进行最终验收：
① 运行 Playwright E2E 测试，覆盖完整用户流程
② 验证子任务的实现在主干上协同工作
③ 确认无回归

验收要点（来自 Issue 验收标准）：
{从 Issue 正文提取的验收条件，若无则省略此行}

完成后请回复：
- 通过：回复【验收通过】并简述 Playwright 验证内容
- 有问题：列出具体问题描述（每条一行）
```

## openclaw 后续动作

### Claude 回复【验收通过】

**根据 Issue 类型执行不同操作：**

**子 Issue**（body 含 `related to #N`）：
1. openclaw 留 【OPENCLAW】 评论：「子任务验收通过，已自动关闭。」
2. openclaw 直接关闭 Issue：`gh issue close {N} -R {repo}`
3. **不推 verified、不推 owner/shuzai** — 子 Issue 生命周期到此结束
4. 下一轮 Step 1.6 会检测到子 Issue 关闭，触发父 Issue 最终验收联动

**HUMAN Issue**（body 不含 `related to #N`）：
1. Issue label：`verifying` → `verified`，owner → `owner/shuzai`
2. Claude 的回复内容以 【CLAUDE】 评论写入 Issue（Claude 自己写入）
3. openclaw 留 【OPENCLAW】 评论：验收通过，label → verified，等待 HUMAN 确认
4. Feishu 通知 HUMAN

### Claude 列出问题

1. 为每个问题自动创建新 Issue（label=`pending`，无 owner，等待路由）
2. 新 Issue 正文中使用 `fix for #{N}`（**不是** `related to #N`，以区分修复 Issue 和子 Issue）
3. 原 Issue 标记为 `verifying` + 添加 `blocked` label，等待修复后重验
4. 在原 Issue 写 【OPENCLAW】 评论列出新建的修复 Issue 编号

> **`related to` vs `fix for` 区分规则：**
> - `related to #N` — 子 Issue（由 Claude/openclaw 拆解创建），验收通过后 openclaw 自动关闭
> - `fix for #N` — 修复 Issue（验收发现问题后创建），走正常路由和验收流程，不自动关闭

### 修复后重验（Re-Verification Trigger）

**触发条件：** Step 1 检测到 `verifying + blocked` 的 Issue，且其所有修复 Issue（body 含 `fix for #{此Issue编号}`）均已关闭（至少存在一个修复 Issue）。

**openclaw 执行：**
1. 移除 `blocked` label
2. 在 Issue 写 【OPENCLAW】 评论：「修复 Issue #{...} 已关闭，重新触发验收。」
3. Issue 保持 `verifying`，下一轮 Step 2-P2/P4 正常命中并重新派发验收请求

## 按任务类型细化验收要点

- **功能类任务**：端到端操作验证，覆盖主路径和常见边界
- **测试类任务**：运行测试套件，确认覆盖率达标、无失败用例
- **文档类任务**：检查关键章节是否准确、示例可运行、链接有效
