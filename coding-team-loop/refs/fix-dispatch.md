# Fix 请求派发

## 触发条件

Issue label=`changes-requested`，Codex 空闲。

## PR commit 时间检测（Step 1 执行）

在 Step 1 读信号阶段，对所有 `changes-requested` Issue 执行：

```bash
pr_commit_time=$(gh pr view {pr_number} --json commits --jq '.commits[-1].committedDate')
pr_review_time=$(gh pr view {pr_number} --json reviews --jq '.reviews[-1].submittedAt')
```

若 `pr_commit_time > pr_review_time` → Codex 已在上轮修复并推送，openclaw 自动将 label 从 `changes-requested` 更新为 `needs-review`，本轮不再派发 fix。

## 获取修改意见

从 GitHub 原文读取，不得由 openclaw 自行改写：

```bash
# 优先读最新 review body
gh pr view {pr_number} --json reviews --jq '.reviews[-1].body'

# 若 review body 为空（使用 comment fallback 的情况），读最后一条 comment
gh pr view {pr_number} --json comments --jq '.comments[-1].body'
```

## 派发消息格式

```
【OPENCLAW】【Fix Request】
PR #{pr_number}（Issue #{N}：{Issue标题}）review 有以下阻塞项，请逐项修复：

{Claude review comment 原文，完整逐字复制，不得摘要或改写}

修复完成后 push 到同一分支（无需重新开 PR）。
分支：{headRefName}

⚠️ 禁止执行 gh issue edit / gh issue close / gh pr merge —— 所有状态推进由 openclaw 自动处理。
```

**重要**：修改意见必须原文转发，不得 openclaw 自行摘要、精简或重新表述，防止信息失真。
