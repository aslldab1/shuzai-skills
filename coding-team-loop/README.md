# coding-team-loop

openclaw 协调 Claude + Codex 双 worker 开发循环。

## 测试验证

### 套件划分

场景通过 `suite` 字段分为主干用例和模块用例：

| 套件 | 触发条件 | 说明 |
|------|---------|------|
| `core` | **每轮必跑** — 任何 SKILL.md 或 refs/ 变更 | 路由优先级、busy 检测、完成信号、双侧派发、handoff |
| `module:task-dispatch` | refs/task-dispatch.md 变更 | 派发格式、HUMAN 反馈检测、原型设计指令 |
| `module:completion-signal` | SKILL.md 完成信号/子 Issue 联动部分变更 | 子 Issue 时序、死锁防护 |
| `module:progress-confirm` | refs/progress-confirm.md 变更 | 重复发送防护、worker 回复处理 |
| `module:review-and-merge` | refs/review-and-merge.md 变更 | review 派发 |
| `module:fix-dispatch` | refs/fix-dispatch.md 变更 | fix 派发 |
| `module:deliverable-verify` | refs/deliverable-verify.md 变更 | 验收派发 |
| `module:session-recovery` | refs/session-recovery.md 变更 | stale 自愈 |
| `module:human-handoff` | refs/human-handoff.md 变更 | owner/shuzai 状态机 |
| `module:memory` | refs/memory-persistence.md 变更 | run_lock、memory 持久化 |

### 验证规则（开发时必须遵守）

1. **改动 SKILL.md 或多个 refs/ 文件** → 跑全量：`python3 scripts/validate_skill.py`
2. **只改动单个 refs/ 文件** → 跑 core + 对应模块：
   ```bash
   python3 scripts/validate_skill.py --suite core
   python3 scripts/validate_skill.py --suite task-dispatch
   ```
3. **新增场景时**，必须标注 `suite` 字段（`core` 或 `module:{name}`）
4. core 套件覆盖状态机主干路径，不应超过 20 个场景

### 常用命令

```bash
# 全量验证（默认 4 并行）
python3 scripts/validate_skill.py

# 只跑主干用例
python3 scripts/validate_skill.py --suite core

# 只跑某个模块
python3 scripts/validate_skill.py --suite task-dispatch

# 单场景调试
python3 scripts/validate_skill.py --scenario CS01 --verbose

# 自定义并行度
python3 scripts/validate_skill.py --concurrency 8
```
