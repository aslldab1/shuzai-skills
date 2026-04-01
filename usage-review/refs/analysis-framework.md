# 对比分析框架

## 分析维度

### 1. 工具使用效率

| 指标 | 健康范围 | 说明 |
|------|---------|------|
| Bash 比率 | < 40% | 过高说明未充分利用专用工具（Read/Write/Edit/Glob/Grep） |
| 专用工具比率 | > 30% | Read/Write/Edit/Glob/Grep 应是主力 |
| Agent 比率 | 5-15% | 过低说明未利用并行能力，过高可能浪费 token |
| Bash 中的 cat/grep/find | 尽量为 0 | 应使用 Read/Grep/Glob 替代 |

### 2. 会话管理

| 指标 | 健康范围 | 说明 |
|------|---------|------|
| 平均会话时长 | 30-120 分钟 | 过长说明任务拆分不足 |
| 平均输入/会话 | 10-30 | 过高可能在重复纠错 |
| 上下文压缩次数 | < 每会话 1 次 | 频繁压缩说明会话过长或任务过泛 |
| 压缩/会话比 | < 0.5 | 高比率需要拆分任务或使用子 agent |

### 3. 工作流成熟度

| 实践 | 评估方式 |
|------|---------|
| CLAUDE.md 使用 | 是否有项目级和用户级配置 |
| Slash 命令使用 | 使用种类和频率 |
| 多项目切换 | 日均活跃项目数 |
| 持续集成 | 是否有 commit/PR 相关命令 |

### 4. 成本效益

| 指标 | 关注点 |
|------|-------|
| 日均成本 | 趋势是否合理 |
| Token 输入/输出比 | 输出远小于输入可能说明 prompt 不够精炼 |
| 模型选择 | 是否根据任务复杂度选择合适的模型 |

## 建议优先级规则

- **HIGH**: 直接影响效率的习惯问题（如大量使用 Bash 替代专用工具）
- **MEDIUM**: 有改进空间但不紧急的实践（如缺少 Agent 并行）
- **LOW**: 锦上添花的优化建议（如尝试新功能）

## 对比逻辑

1. 计算各指标当前值
2. 与健康范围对比，标记偏离项
3. 结合外部经验，为偏离项生成具体建议
4. 识别已经做得好的方面（strengths）
5. 优先推荐有外部实践验证的改进方案

---

## 操作手册标准

**每条建议必须包含操作手册**，格式要求：

```json
{
  "title": "建议标题",
  "description": "问题描述 + 为什么重要",
  "your_value": "用户当前数值",
  "best_practice": "社区推荐标准",
  "action": "一句话总结",
  "playbook": {
    "steps": [
      {
        "do": "具体操作（要打开什么、输入什么命令、改什么文件）",
        "example": "完整的命令或代码示例",
        "expect": "操作后应该看到什么结果"
      }
    ],
    "before_after": {
      "before": "改进前的典型用法示例",
      "after": "改进后的正确用法示例"
    },
    "measure": "如何衡量改进效果（下周复查的指标）"
  }
}
```

### 各改进方向的操作手册模板

#### A. 降低 Bash 比率

```
步骤：
1. 在 CLAUDE.md 中添加规则
   打开: ~/.claude/CLAUDE.md
   追加:
     ## Tool Usage Rules
     - 读取文件内容时使用 Read tool，不要用 cat/head/tail
     - 搜索文件时使用 Glob tool，不要用 find/ls
     - 搜索文件内容时使用 Grep tool，不要用 grep/rg
     - 编辑文件时使用 Edit tool，不要用 sed/awk

改进前 → 改进后：
  Before: Bash("cat src/app.ts | head -20")
  After:  Read("src/app.ts", limit=20)

  Before: Bash("grep -r 'TODO' src/")
  After:  Grep(pattern="TODO", path="src/")

  Before: Bash("find . -name '*.test.ts'")
  After:  Glob(pattern="**/*.test.ts")

衡量: 下周 Bash 比率应从 58% 降至 < 45%
```

#### B. 利用 Agent 并行

```
步骤：
1. 识别可并行的场景
   - 需要在多个目录搜索不同内容时
   - 需要同时跑测试 + 做代码审查时
   - 需要调研多个方案进行比较时

2. 在提示中明确要求并行
   输入: "帮我并行做这三件事：1) 搜索所有 TODO 注释 2) 检查测试覆盖率 3) 审查最近 3 个 commit 的安全性"

3. 使用 background agent
   输入: "用 background agent 跑测试，同时你继续帮我写代码"

改进前 → 改进后：
  Before: "先搜索 auth 模块的所有文件" → 等结果 → "再搜索 api 模块" → 等结果
  After:  "并行搜索 auth 和 api 模块中所有包含 validateToken 的文件"

  Before: 一条一条串行执行代码审查
  After:  "同时启动 3 个 agent：1) security-reviewer 审查安全 2) code-reviewer 审查质量 3) 跑 pytest"

衡量: 下周 Agent 比率应从 1.1% 提升至 > 5%
```

#### C. 缩短会话 / 减少压缩

```
步骤：
1. 单任务完成后清理上下文
   完成一个功能后输入: /clear
   或者直接开新会话: claude（新终端标签）

2. 用命名会话管理不同任务
   输入: claude --session "feature-auth"
   切换: claude --resume "feature-auth"
   新任务: claude --session "bugfix-login"

3. 大任务拆分为子任务
   不要: "帮我重构整个 auth 模块并加测试并更新文档"
   而是分 3 个会话:
     会话1: "重构 auth 模块的数据层"
     会话2: "给重构后的 auth 模块补测试"
     会话3: "更新 auth 模块的文档"

改进前 → 改进后：
  Before: 一个会话跑 4 小时，压缩 3 次，后期输出质量下降
  After:  3 个 focused 会话各 40 分钟，0 次压缩，输出质量稳定

衡量: 下周压缩/会话比应从 0.9 降至 < 0.5
```

#### D. 前端设计闭环

```
步骤：
1. 需求 → Stitch 原型
   输入: "/stitch-prototype 设计订单列表页，包含筛选、排序、分页"
   期望: Stitch 生成可交互的 screen

2. 原型 → 代码实现
   输入: "参考 Stitch screen #XX 实现前端页面，使用 React + TailwindCSS"
   期望: 生成与原型一致的代码

3. 代码 → Playwright 截图验收
   输入: "用 Playwright 打开 localhost:3000/orders，截图与 Stitch 原型对比"
   期望: 截图显示页面与原型基本一致

4. 差异 → 迭代修复
   输入: "截图与原型对比，导航栏颜色不对，修复它"
   期望: 修复后再次截图确认

改进前 → 改进后：
  Before: Stitch 出图 → 手动实现 → 手动截图 → 手动对比 → 来回沟通
  After:  Stitch 出图 → Claude 实现 → Playwright 自动截图验收 → 自动迭代

衡量: 前端任务的来回修改次数减少 50%
```

#### E. Git Worktree 并行开发

```
步骤：
1. 创建 worktree
   终端输入:
     git worktree add ../my-project-feature-a feature-a
     git worktree add ../my-project-feature-b feature-b

2. 每个 worktree 启动独立 Claude 会话
   终端 Tab 1: cd ../my-project-feature-a && claude
   终端 Tab 2: cd ../my-project-feature-b && claude

3. 独立开发，互不干扰
   Tab 1 的 Claude 只看到 feature-a 的代码
   Tab 2 的 Claude 只看到 feature-b 的代码

4. 完成后清理
   git worktree remove ../my-project-feature-a

改进前 → 改进后：
  Before: feature-a 做完 → 切分支 → feature-b 做完 → 串行耗时 2 小时
  After:  feature-a 和 feature-b 同时进行 → 并行耗时 1 小时

衡量: 同时进行的独立任务数 > 2
```

#### F. CLAUDE.md 持续改进

```
步骤：
1. 每次纠正 Claude 时，判断是否值得加规则
   问自己: "这个错误以后还会犯吗？"
   如果是 → 立刻在 CLAUDE.md 追加

2. 追加格式
   打开: 项目根目录的 CLAUDE.md
   追加:
     - 描述错误行为 + 正确做法
     - 一行即可，不需要长篇大论

3. 示例
   Claude 犯错: 用了 any 类型
   追加到 CLAUDE.md: "- 禁止使用 any 类型，始终使用具体类型或 unknown"

   Claude 犯错: 修改了不相关的文件
   追加: "- 只修改与当前任务直接相关的文件，不要顺手重构"

改进前 → 改进后：
  Before: 反复口头纠正同一个错误
  After:  纠正一次，写入规则，永不再犯

衡量: CLAUDE.md 每周至少新增 2-3 条规则
```
