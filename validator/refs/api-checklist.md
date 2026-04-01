# API 验收清单

通过 curl / httpie / Playwright 等方式逐项验证 API 接口。

## A. 端点可达性（阻断级）

| # | 检查项 | 操作 | FAIL 条件 |
|---|--------|------|----------|
| A1 | 服务启动 | 发送 health check 请求 | 连接拒绝、超时 |
| A2 | 所有声明端点可达 | 逐个发送基础请求 | 404（端点不存在）、405（方法不支持） |
| A3 | 认证流程 | 如需认证，执行认证获取 token | 认证失败、token 无效 |

## B. 数据正确性

| # | 检查项 | 操作 | FAIL 条件 |
|---|--------|------|----------|
| B1 | 响应结构 | 对照 API 文档检查 JSON 结构 | 字段缺失、字段类型错误（number 返回 string） |
| B2 | 数据完整 | 检查列表接口返回数量 | 返回空数组（应有数据时）、分页参数无效 |
| B3 | CRUD 流程 | 创建 → 查询 → 更新 → 删除 | 创建后查不到、更新不生效、删除后仍存在 |
| B4 | 响应格式 | 检查 Content-Type 和编码 | 非 JSON 响应（期望 JSON 时）、编码错误导致乱码 |

## C. 错误处理

| # | 检查项 | 操作 | FAIL 条件 |
|---|--------|------|----------|
| C1 | 无效输入 | 发送空 body、缺少必填字段 | 返回 500（应返回 400/422）、无错误消息 |
| C2 | 越权访问 | 无 token 或错误 token 访问受保护端点 | 返回 200（应返回 401/403） |
| C3 | 不存在资源 | 请求不存在的 ID/路径 | 返回 500（应返回 404）、返回空 200 |
| C4 | 错误消息质量 | 检查错误响应的 body | 无 message 字段、message 为内部错误信息（暴露 stack trace） |

## D. 边界条件

| # | 检查项 | 操作 | FAIL 条件 |
|---|--------|------|----------|
| D1 | 超长输入 | 发送超长字符串（>10000 字符） | 500 崩溃（应返回 413 或 422） |
| D2 | 特殊字符 | 发送含 `<script>`、SQL 注入、emoji 的输入 | XSS 内容被原样返回、SQL 错误暴露 |
| D3 | 并发请求 | 同时发送 5 个相同请求 | 数据不一致、重复创建 |
| D4 | 大批量数据 | 请求大量数据（无分页 limit） | 响应超时、内存溢出 |

## 操作模板

```bash
# 标准 API 测试流程
# 1. Health check
curl -s -o /dev/null -w "%{http_code}" {base_url}/health

# 2. 正常请求
curl -s {base_url}/api/resource | python3 -m json.tool

# 3. 创建资源
curl -s -X POST {base_url}/api/resource \
  -H "Content-Type: application/json" \
  -d '{"field": "value"}' | python3 -m json.tool

# 4. 错误请求
curl -s -X POST {base_url}/api/resource \
  -H "Content-Type: application/json" \
  -d '{}' -w "\n%{http_code}"
```
