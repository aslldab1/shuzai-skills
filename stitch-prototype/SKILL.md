---
name: stitch-prototype
description: 使用 Google Stitch MCP 进行产品原型设计。从需求确认到交付完整原型，包含需求细化、Project 管理、Screen 生成、验收修改全流程。
---

# Stitch Prototype — 产品原型设计

使用 Google Stitch MCP 工具完成从需求到可交付原型的全流程。

---

## 前置条件

- Stitch MCP 已配置并可用（`mcp__stitch__*` 工具）
- 用户已登录 Google 账号（Stitch 权限）

---

## 执行流程（固定 5 步）

### Step 1 — 需求理解与设计补全

**目标：** 从用户输入和对话上下文中提取信息，结合行业通用产品设计惯例，自主完成 Screen 清单，无需用户交互确认。

#### 1.1 信息提取

从用户提供的内容和对话上下文中提取以下信息（能提取多少算多少）：

| 字段 | 提取来源 | 缺省处理 |
|------|---------|---------|
| 产品名称 | 用户直接提供 / 对话上下文 | 用产品类型命名，如"学习助手" |
| 核心功能 | 用户描述 / 关键词推断 | 按产品类型套用常见功能集 |
| 目标用户 | 用户描述 / 场景推断 | 按产品类型推断（如 B2C 教育 → 学生） |
| 设备类型 | 用户明确指定 / 场景推断 | 移动端优先（MOBILE） |
| 设计风格 | 用户提及 / 品牌关键词 | 简洁现代风 |

#### 1.2 设计补全规则

用户未提供的内容，按以下优先级自主补全：

1. **行业标准页面**（必须包含）
   - 所有 App：启动页、首页/仪表盘
   - 需要账户体系的：登录页、注册页、个人中心
   - 内容类产品：详情页、列表页
   - 工具类产品：主功能页、结果页

2. **核心用户流程覆盖**（结合产品类型补充）
   - 新用户引导 / Onboarding（若用户旅程需要）
   - 主任务完成流程（从入口到结果）
   - 关键空状态 / 加载状态（主流程涉及的）

3. **产品类型参考模式**
   - 教育/学习类：课程列表 → 课程详情 → 学习页 → 完成/成就
   - 电商类：商品列表 → 商品详情 → 购物车 → 结算 → 订单确认
   - 社交类：Feed 流 → 内容详情 → 个人主页 → 消息/通知
   - 工具类：功能入口 → 参数配置 → 执行中 → 结果展示
   - SaaS 管理类：数据仪表盘 → 列表管理 → 详情/编辑 → 设置

#### 1.3 输出：Screen 清单

直接输出完整 Screen 清单，说明补全依据：

| # | Screen 名称 | 功能描述 | 用户流程位置 | 来源 |
|---|------------|---------|------------|------|
| 1 | 启动页 | 品牌展示 + 加载 | 入口 | 行业标准 |
| 2 | ... | ... | ... | 用户需求/行业惯例 |

「来源」列说明该页面是来自用户明确需求还是设计补全，帮助用户理解设计决策。

**直接进入 Step 2，无需等待用户确认。**

---

### Step 2 — Project 管理

**目标：** 创建或复用 Stitch Project。

#### 复用已有 Project

如果上下文中已有近期使用的 project（如对话历史、memory 中记录的 projectId），优先复用：

```
mcp__stitch__get_project(name="projects/{projectId}")
```

确认 project 状态正常后直接进入 Step 3。

#### 创建新 Project

```
mcp__stitch__create_project(title="产品名称 - 原型")
```

从返回结果中提取 `projectId`（数字 ID），后续步骤使用。

---

### Step 3 — Screen 生成

**目标：** 按 Screen 清单逐一生成原型页面。

#### 生成策略

- 使用 `generate_screen_from_text` 逐个生成 Screen
- 推荐 model：`GEMINI_3_1_PRO`（质量最佳）或 `GEMINI_3_FLASH`（速度优先）
- 每个 prompt 必须包含：
  - Screen 的功能描述
  - 该 Screen 在用户流程中的位置和上下文
  - 关键 UI 元素和交互说明
  - 与其他 Screen 的导航关系

#### Prompt 模板

```
为「{产品名称}」设计「{Screen名称}」页面。

功能描述：{功能描述}
用户流程：{该页面在整体流程中的位置，上一步/下一步是什么}
设备类型：{MOBILE/DESKTOP}

关键元素：
- {元素1}
- {元素2}
- ...

导航关系：
- 从「{上一页}」点击「{按钮}」进入本页
- 点击「{按钮}」跳转到「{下一页}」

设计要求：
- {风格/品牌要求}
- 页面底部添加注释说明本页的功能和流程位置
```

#### 调用方式

```
mcp__stitch__generate_screen_from_text(
  projectId="{projectId}",
  prompt="{完整prompt}",
  deviceType="{MOBILE|DESKTOP}",
  modelId="GEMINI_3_1_PRO"
)
```

#### 错误处理

generate 和 edit 涉及多模态生成，耗时较长（可能数分钟）。API 调用失败≠生成失败，后端可能仍在异步处理。

**失败后处理流程（适用于超时、连接错误、任意非成功响应）：**

1. **不要立即重试。** 记录当前已知的 screen 数量（通过 `list_screens` 获取）
2. **等待 2 分钟**（使用 `sleep 120`）
3. 调用 `list_screens` 获取最新 screen 列表，与之前对比：
   - **新增了目标 screen** → 生成已成功，用 `get_screen` 确认内容，继续下一个
   - **未新增** → 确认生成确实失败，此时再发起重试（最多重试 1 次）
4. 重试仍失败时，简化 prompt（减少复杂描述）后再尝试一次

**关键原则：宁可多等，不可多生成。** 重复生成会产生大量废弃 screen，清理成本高（没有 delete API）。

- **output_components 包含建议：** 将建议展示给用户，用户选择后以选中的建议作为 prompt 再次调用

#### 并行策略

- 多个 Screen 之间无依赖时，可并行发起 generate 调用
- 但注意 Stitch API 可能有并发限制，如遇限流则改为串行

---

### Step 4 — 交付前验收

**目标：** 确保所有 Screen 内容完整、正确，清理多余页面。

#### 4.1 全量检查

```
mcp__stitch__list_screens(projectId="{projectId}")
```

对每个 screen 调用 get_screen 查看详细内容：

```
mcp__stitch__get_screen(
  name="projects/{projectId}/screens/{screenId}",
  projectId="{projectId}",
  screenId="{screenId}"
)
```

#### 4.2 清理多余 Screen

对于不需要的 Screen（如测试生成的废弃页、重复页），使用 edit_screens 修改为空白页：

```
mcp__stitch__edit_screens(
  projectId="{projectId}",
  selectedScreenIds=["{screenId}"],
  prompt="将此页面清空，替换为一个空白页面，仅显示文字：此页面已废弃"
)
```

> **注意：** Stitch 没有 delete_screen API，空白化是唯一的清理方式。

#### 4.3 内容修正

对于内容不符合预期的 Screen，使用 edit_screens 修改：

```
mcp__stitch__edit_screens(
  projectId="{projectId}",
  selectedScreenIds=["{screenId}"],
  prompt="{修改指令}",
  modelId="GEMINI_3_1_PRO"
)
```

#### 4.4 验收标准

- [ ] Screen 数量与清单一致（多余的已空白化）
- [ ] 每个 Screen 的内容与功能描述匹配
- [ ] Screen 之间的导航关系合理
- [ ] 每个 Screen 包含功能描述注释
- [ ] 无明显 UI 问题（布局混乱、文字截断等）

**向用户报告验收结果，如有问题则循环修改直到通过。**

---

### Step 5 — 交付

**目标：** 提供可访问的原型链接。

1. 构建 Project URL：

```
https://stitch.withgoogle.com/u/1/projects/{projectId}
```

2. 向用户提供：
   - Project 访问 URL
   - Screen 清单摘要（名称 + 简要描述）
   - 如有关联的 GitHub Issue，将 URL 发布到 Issue 评论中

3. 输出格式：

```
原型设计完成！

项目：{产品名称}
链接：https://stitch.withgoogle.com/u/1/projects/{projectId}

包含以下页面：
1. {Screen名称} — {简要描述}
2. {Screen名称} — {简要描述}
...

如需修改，请告知具体页面和修改内容。
```

---

## 注意事项

- `generate_screen_from_text` 和 `edit_screens` 耗时较长，API 报错不代表后端未处理，**必须等待 2 分钟后查询确认再决定是否重试**
- 每次生成后务必用 `list_screens` + `get_screen` 验证实际内容，不要仅依赖 API 返回结果判断
- Screen 的注释/标注是重要交付物，确保每个页面都有清晰的功能说明
- 如用户有关联的 GitHub Issue，完成后将 Stitch URL 发布到 Issue 评论中
