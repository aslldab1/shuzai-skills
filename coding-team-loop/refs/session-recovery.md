# Session 恢复

## Stale In-Progress 处理

**已由 refs/progress-confirm.md 接管。**

Step 1 检测 `in-progress` + 20 分钟无活动 → 标记为"待确认"，Step 2/3 向 worker 发送进度确认消息，由 worker 回复决定后续动作。不再自动 reset label。

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
