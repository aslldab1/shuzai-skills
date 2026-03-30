# Memory 持久化

## 文件路径

`~/.openclaw/coding-team-loop/memory.json`

## 读取（Step 1 最先执行）

```bash
MEMORY_FILE="$HOME/.openclaw/coding-team-loop/memory.json"
if [ -f "$MEMORY_FILE" ]; then
  cat "$MEMORY_FILE"
else
  echo '{}'
fi
```

文件不存在 → 首次运行，所有字段使用默认值：

```json
{
  "workers": {
    "claude": { "last_dispatched_at": "", "last_issue_number": null },
    "codex": { "last_dispatched_at": "", "last_issue_number": null }
  },
  "notifications": {
    "all_verified_notified_at": null,
    "last_feishu_report_hash": ""
  },
  "codex_orphan_recovered": [],
  "run_lock": false
}
```

## 写回（Step 5 最后执行）

```bash
mkdir -p "$(dirname "$MEMORY_FILE")"
cat > "$MEMORY_FILE" << 'EOF'
{更新后的完整 JSON}
EOF
```

每轮必须写回完整 JSON（不是增量更新），确保文件始终是合法 JSON。

## run_lock 超时保护

读到 `run_lock: true` 时，检查文件修改时间：

```bash
# macOS
FILE_MTIME=$(stat -f %m "$MEMORY_FILE")
# Linux: FILE_MTIME=$(stat -c %Y "$MEMORY_FILE")
NOW=$(date +%s)
ELAPSED=$(( NOW - FILE_MTIME ))
if [ "$ELAPSED" -gt 600 ]; then
  echo "run_lock stale (${ELAPSED}s), forcing clear"
  # 继续执行，Step 5 会写回 run_lock=false
fi
```

阈值 600 秒（10 分钟）= cron 间隔。超过说明上轮崩溃，强制清除 lock 继续执行。

## 字段用途速查

| 字段 | 写入时机 | 读取时机 |
|------|---------|---------|
| `run_lock` | Step 1 开头设 true，Step 5 设 false | Step 1 开头检查 |
| `workers.{w}.last_dispatched_at` | Step 2/3 派发后 | 可用于防重复派发判断 |
| `workers.{w}.last_issue_number` | Step 2/3 派发后 | 可用于防重复派发判断 |
| `codex_orphan_recovered` | Step 1.5 补建后追加 | Step 1.5 排除已处理的父 Issue |
| `notifications.all_verified_notified_at` | 全局异常发送通知后 | 全局异常检查是否已通知 |
| `notifications.last_feishu_report_hash` | Step 4 发送报告后 | Step 4 判断是否跳过重复报告 |
