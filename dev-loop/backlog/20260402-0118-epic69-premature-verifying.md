# P0: Epic #69 被误推进为 verifying（子任务完成信号误判为 epic 完成）

## 发现

- 轮次: R8 (session ea01e19e-7de7-45bb-8844-7a4a16dcfe01)
- 时间: 2026-04-02 01:18

## 现象

Agent 在 #69 评论中检测到 `【CLAUDE】【完成】Issue #69 子任务 B — 开发任务包初版`，
将其误判为 #69 整体完成，执行了 label 变更 `in-progress -> verifying`。

实际上 #69 是 epic，有 4 个子 Issue (#70/#71/#72/#73) 全部仍为 open 状态。
按 SKILL.md 规则"子 Issue 全部关闭 -> 父 Issue label 改 verifying"，不应推进。

## 根因

SKILL.md 的完成信号规则对 epic 场景不够明确：
- 规则写了"检测到 `【CLAUDE】【完成】` → label 改 `verifying`"
- 也写了"子 Issue 全部关闭 → 父 Issue label 改 `verifying`"
- 两条规则冲突时，agent 选择了前者（按评论信号推进）而非后者（按子 Issue 状态推进）

## 修复

1. 已手动回退 #69 label: `verifying -> in-progress`
2. 已在 #69 添加修正评论
3. 需修改 SKILL.md: 明确 epic Issue（带 `epic` label）的完成信号处理优先级——
   epic 的状态推进必须基于子 Issue 状态，不受评论中完成信号影响

## 影响

- #69 被错误推进为 verifying，可能触发不必要的 validator 验收
- 已及时回退，无持续影响
