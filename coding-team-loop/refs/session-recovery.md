# Session 恢复

## Stale In-Progress 自愈

Step 1 中检测：Issue label=`in-progress` + 对应 worker 空闲 + 无关联 open PR。

```bash
# 检查是否有以 issue-{N} 命名的分支
git ls-remote --heads origin | grep "issue-{N}"
# 或通过 GitHub API
gh api repos/{owner}/{repo}/git/refs/heads --jq '.[].ref' | grep "issue-{N}"
```

**有分支：**
- label 保持 `in-progress`
- 下轮派发"恢复执行"消息（见 refs/task-dispatch.md 中断恢复部分）

**无分支：**
- Issue label 重置为 `pending`（保留 owner label）
- 留 【OPENCLAW】 评论：
  ```
  【OPENCLAW】检测到执行中断（worker 空闲，无 PR 也无对应分支）。
  已重置为 pending，下轮重新派发。检测时间：{datetime}
  ```

## Codex 会话缺失

```bash
# 检测
tmux has-session -t {codex-session} 2>/dev/null || echo "missing"
```

重建步骤：
1. `tmux new-session -d -s {codex-session} -c {codex-workdir}`
2. `tmux send-keys -t {codex-session} "export GH_TOKEN={codex-bot-token}" Enter`
3. 验证账户：`tmux send-keys -t {codex-session} "gh api user --jq .login" Enter`，确认为 codex-bot
4. `tmux send-keys -t {codex-session} "codex --full-auto" Enter`
5. 等待 trust 提示（如有），发送确认
6. 等待 pane 出现空闲状态后，从 Step 1 重新开始当轮

## Claude 会话缺失

```bash
tmux has-session -t {claude-session} 2>/dev/null || echo "missing"
```

重建步骤：
1. `tmux new-session -d -s {claude-session} -c {project-dir}`
2. `tmux send-keys -t {claude-session} "claude" Enter`
3. 等待启动完成（pane 出现 `❯` 提示符）
4. 从 Step 1 重新开始当轮
