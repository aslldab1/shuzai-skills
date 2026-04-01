# Claude 忙碌判断

## 判断规则

只判断一个信号：**Claude pane 底部是否有忙碌行首符号**。有 → 忙碌，没有 → 空闲。

> Codex 不再有独立 tmux pane，Codex 任务通过 Claude 的 Codex 插件调度。只需检查 Claude pane。

### 忙碌行首符号

Claude 工作时，状态行以特定符号开头（完成后被结果替换，不会留在历史中）：

| 符号 | 示例 |
|------|------|
| `✢` `✦` `✳` `✶` `✻` `✽` | `✢ Generating… (49s · ↓ 87 tokens)` |
| `•` + 动名词 | `• Working (5s · esc to interrupt)` |
| `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` | 旋转进度指示（通用 spinner） |

**注意：** 单独出现 dingbat 或 `•` 不一定是忙碌！
- `✻ Conversation compacted` — dingbat 开头但不是忙碌（"Conversation" 不是动名词）
- `• Context compacted` — `•` 开头但不是忙碌（"Context" 不是动名词）

**必须要求：符号 + 动名词（`[A-Z][a-z]+ing`）才算忙碌。**

**匹配规则：**
```
^\s*[✢✦✳✶✻✽•] [A-Z][a-z]+ing|^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]
```
- 行首符号 + 空格 + 大写动名词（如 `✢ Generating`、`• Working`）
- Braille spinner：行首 spinner 字符单独即匹配（spinner 不带文字）
- **不匹配裸关键字**（如 `Reading`、`Writing`），因为这些词在历史输出中也会出现

**判断命令：**
```bash
bash scripts/busy_check.sh {claude_pane}
```
脚本内部逻辑：`tmux capture-pane | grep -v '^$' | tail -5` → Python regex 匹配（避免 grep -E 在不同 exec 环境下的 Unicode 行为差异）。

**双重限制：只检查最底部 5 行非空行 + 符号必须配合动名词。**

- 输出 `BUSY` → **忙碌**，跳过本轮（同时输出匹配到的行，便于事后排查）
- 输出 `IDLE` → **空闲**，可以派发

### 为什么用行首符号而不是内容关键字

| 方案 | 问题 |
|------|------|
| **全文匹配 `[A-Z][a-z]+ing[.…]`** | 历史输出包含 "Reading file…"、"Writing to…" 等正常文本 → 空闲 worker 被误判为忙碌 |
| **检测提示符** `❯`/`›` | 状态栏压在提示符下面导致检测失败；两种 CLI 用不同提示符 |
| **光标位置** | 增加复杂度，无明显收益 |
| **行首符号 `✢✦✳✶✻✽`/`• Verb`/spinner** | dingbat 符号只在忙碌时出现在行首；`•` 要求后跟动名词 ✅ |

### Pane 底部布局参考

**Claude Code 忙碌时：**
```
✢ Generating… (49s · ↓ 87 tokens)     ← 行首 ✢
────────────────────
  [Sonnet 4.6] │ branch
  Context ████ │ Usage █
```

**空闲时：** 底部无 `✢`/`•`/spinner 符号，只有提示符和状态栏。

万一误判为空闲并发送了消息，后续 ack 机制会兜底。

## 注意事项

- 忙碌时本轮跳过，不发送任何消息，等下一轮
- 若 Claude pane 不存在，视为会话缺失 → 参考 session-recovery.md
