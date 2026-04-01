# shuzai-skills

本仓库存放用户级自定义 Claude Code Skills，每个 skill 是一个子目录，包含 `SKILL.md`。

## 目录结构

```
shuzai-skills/
├── CLAUDE.md               # 本文件，说明安装规则和开发规范
├── coding-team-loop/       # OpenClaw 开发循环 skill v1（规则驱动，350+ 行状态机）
│   └── SKILL.md
├── dev-loop/               # OpenClaw 开发循环 skill v2（极简版，目标+约束驱动）
│   └── SKILL.md
├── cron-log-review/        # OpenClaw cron 定时任务日志分析 skill
│   └── SKILL.md
├── stitch-prototype/       # Google Stitch 产品原型设计 skill
│   └── SKILL.md
├── validator/              # AI 产出物验收 skill（视觉+用户旅程+交互）
│   ├── SKILL.md
│   └── refs/
└── validator-eval/         # Validator 验收质量评测 skill
    ├── SKILL.md
    └── scripts/analyze_runs.py
```

## 安装规则

**使用软连接方式安装**，不要用 `cp` 复制，否则 skill 更新后无法同步：

```bash
# 安装单个 skill（用户级，所有会话可用）
ln -s /Users/lin/workspace/AI/git/shuzai-skills/<skill-name> ~/.claude/skills/<skill-name>

# 查看已安装的 skill
ls -la ~/.claude/skills/
```

新增 skill 后，在此文件的目录结构中补充说明，并按上述命令安装软连接。

## 已安装 Skills

| Skill | 触发命令 | 说明 |
|-------|---------|------|
| stitch-prototype | `/stitch-prototype` | 使用 Google Stitch MCP 进行产品原型设计，包含需求确认、Screen 生成、验收交付全流程 |
| coding-team-loop | `/coding-team-loop` | OpenClaw 开发循环 v1（规则驱动，350+ 行状态机） |
| dev-loop | `/dev-loop` | OpenClaw 开发循环 v2（极简版，~100 行，目标+约束驱动） |
| cron-log-review | `/cron-log-review` | 分析 OpenClaw cron 定时任务的执行日志，重点检查状态推进错误和流程执行问题 |
| validator | 由 coding-team-loop 派发 | AI 产出物验收：视觉质量分析、用户旅程验证、交互测试、设计稿对比 |
| validator-eval | `/validator-eval` | 评测 validator 验收质量：三阶段执行审计、截图分析率、用户旅程覆盖、视觉检测能力 |

## 飞书通知规则

每次开发任务完成、进入等待用户指令的状态时，必须通过 openclaw 发送飞书消息通知用户：

```bash
openclaw message send --channel feishu --target "ou_c5bd4c88f78cbf338f76dbb5e8f64fed" -m "通知内容"
```

通知内容应简明扼要，包含：完成了什么、当前状态、是否需要用户操作。

## Skill 文件隔离规则

**不同 skill 之间文件完全隔离，禁止复用：**
- 禁止用软连接（`ln -s`）引用其他 skill 的文件
- 每个 skill 的脚本、refs、配置必须独立存放在自己目录下
- 即使逻辑相同，也要各自持有独立副本
- 原因：skill 独立演进，修改一个不应影响另一个

## Skill 开发规范

### 测试验证规则（必须遵守）

每个 skill 的测试场景通过 `suite` 字段分为主干用例（`core`）和模块用例（`module:{name}`）。

**验证时机：**

1. **改动 SKILL.md 或多个 refs/ 文件** → 跑全量验证
2. **只改动单个 refs/ 文件** → 跑 core + 对应模块
3. **新增测试场景时**，必须标注 `suite` 字段（`core` 或 `module:{name}`）
4. core 套件覆盖状态机主干路径，不应超过 20 个场景

**coding-team-loop 验证命令：**

```bash
# 全量验证（默认 4 并行）
python3 scripts/validate_skill.py

# 只跑主干用例
python3 scripts/validate_skill.py --suite core

# 只跑某个模块
python3 scripts/validate_skill.py --suite task-dispatch

# 单场景调试
python3 scripts/validate_skill.py --scenario CS01 --verbose
```

### 场景套件说明

| 套件 | 触发条件 | 说明 |
|------|---------|------|
| `core` | 每轮必跑 | 路由优先级、busy 检测、完成信号、派发、handoff |
| `module:task-dispatch` | refs/task-dispatch.md 变更 | 派发格式、HUMAN 反馈检测、原型设计指令 |
| `module:completion-signal` | SKILL.md 完成信号部分变更 | 子 Issue 时序、死锁防护 |
| `module:progress-confirm` | refs/progress-confirm.md 变更 | 重复发送防护、worker 回复处理 |
| `module:review-and-merge` | refs/review-and-merge.md 变更 | review 派发 |
| `module:fix-dispatch` | refs/fix-dispatch.md 变更 | fix 派发 |
| `module:deliverable-verify` | refs/deliverable-verify.md 变更 | 验收派发 |
| `module:session-recovery` | refs/session-recovery.md 变更 | stale 自愈 |
| `module:human-handoff` | refs/human-handoff.md 变更 | owner/shuzai 状态机 |
| `module:memory` | refs/memory-persistence.md 变更 | run_lock、memory 持久化 |
