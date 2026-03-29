# Review 并 Merge

## 触发条件

Issue label=`needs-review`，Claude 空闲。

从该 Issue 关联的 open PR 中获取 PR 编号（通过 Step 1 已建立的关联关系）。

## 派发消息格式

```
【OPENCLAW】【Review Request】
Issue #{N}：{Issue标题}
PR #{pr_number}：{PR标题}
分支：{headRefName}

请 review 此 PR，完成后将结论写入 GitHub：

步骤 1 — 提交 GitHub review：
- 通过：
  gh pr review {pr_number} --approve --body "APPROVED: {一句话总结}"
- 需修改：
  gh pr review {pr_number} --request-changes --body "$(cat <<'EOF'
## Review 结论
状态：CHANGES_REQUESTED
阻塞项：
- {blocker 1}
- {blocker 2}
EOF
)"

步骤 2 — 若 gh pr review 返回 HTTP 422（own-PR 限制）：
改用 comment 写入：
  gh pr comment {pr_number} --body "$(cat <<'EOF'
## Review 结论
状态：APPROVED | CHANGES_REQUESTED
阻塞项（CHANGES_REQUESTED 时填写）：
- {blocker}
EOF
)"

完成标准：GitHub 上可查到 review 或 comment 记录。
```

## openclaw 后续动作

等待 Claude 完成（每 20 秒抓 pane，最多等待 5 分钟），然后查询 GitHub 确认：

```bash
gh pr view {pr_number} --json reviews,comments
```

**Claude APPROVED：**
1. 执行 merge：`gh pr merge {pr_number} --squash --auto`
2. Issue label：`needs-review` → `verifying`
3. 留 【OPENCLAW】 评论：PR #{pr_number} 已合并，label → verifying

**Claude CHANGES_REQUESTED：**
1. Issue label：`needs-review` → `changes-requested`
2. 留 【OPENCLAW】 评论，记录 review 结论时间
3. 下轮 Step 3-P1 处理 fix 派发
