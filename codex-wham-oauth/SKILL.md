---
name: codex-wham-oauth
description: 使用 Codex CLI 的 OAuth token（~/.codex/auth.json）调用 OpenAI WHAM API，适合在 cron/后台脚本中替代需要交互刷新的 Claude OAuth
---

# Codex WHAM OAuth 集成

在 cron 环境或后台脚本中，Claude OAuth token 有效期只有 24 小时且 refresh 在非 Claude Code 环境失败。
Codex CLI 的 OAuth token（`~/.codex/auth.json`）有效期约 7 天，任意 `codex` 命令都会自动刷新，适合定时任务场景。

## Token 来源

Codex CLI 登录后自动维护 `~/.codex/auth.json`：

```json
{
  "access_token": "eyJ...",
  "refresh_token": "...",
  "expires_at": 1745000000
}
```

- `expires_at`：Unix 秒级时间戳，约 7 天有效期
- 刷新方式：运行任意 `codex` 命令（如 `codex "hello"`）即可自动刷新

## WHAM API 规格

```
POST https://chatgpt.com/backend-api/wham/responses
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "model": "gpt-5.4-mini",     // 或 gpt-5.4、gpt-5.3-codex
  "store": false,
  "stream": true,               // 必须为 true，否则报 400
  "instructions": "<system>",
  "input": [
    {
      "role": "user",
      "content": [
        {"type": "input_text", "text": "<prompt>"}  // 必须用 input_text，不能用 text
      ]
    }
  ]
}
```

SSE 响应中解析 `response.output_text.delta` 事件拼接文本：

```
data: {"type": "response.output_text.delta", "delta": "Hello"}
data: {"type": "response.output_text.delta", "delta": " world"}
data: [DONE]
```

## Python 实现

```python
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

WHAM_URL = "https://chatgpt.com/backend-api/wham/responses"
DEFAULT_MODEL = "gpt-5.4-mini"  # 可选: gpt-5.4, gpt-5.3-codex


def get_codex_token() -> str | None:
    """读取 ~/.codex/auth.json 的 access_token，过期时返回 None 并打 warning。"""
    path = Path.home() / ".codex" / "auth.json"
    if not path.exists():
        return None
    try:
        auth = json.loads(path.read_text())
        token = auth.get("access_token")
        expires_at = auth.get("expires_at", 0)
        if token and expires_at > time.time():
            return token
        logger.warning("Codex token 已过期（expires_at=%s），请运行 `codex hello` 刷新", expires_at)
    except Exception as e:
        logger.warning("读取 ~/.codex/auth.json 失败: %s", e)
    return None


async def call_wham(token: str, system: str, user_prompt: str, model: str | None = None) -> str:
    """调用 WHAM API，返回完整文本。依赖 httpx（pip install httpx）。"""
    import httpx

    model = model or os.getenv("CODEX_MODEL", DEFAULT_MODEL)
    full_text = ""

    async with httpx.AsyncClient(timeout=60) as http:
        async with http.stream(
            "POST",
            WHAM_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "store": False,
                "stream": True,
                "instructions": system,
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_prompt}],
                    }
                ],
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and not line.endswith("[DONE]"):
                    try:
                        d = json.loads(line[6:])
                        if d.get("type") == "response.output_text.delta":
                            full_text += d.get("delta", "")
                    except json.JSONDecodeError:
                        pass

    return full_text


# 同步封装（适合非 async 脚本）
def call_wham_sync(token: str, system: str, user_prompt: str, model: str | None = None) -> str:
    import asyncio
    return asyncio.run(call_wham(token, system, user_prompt, model))
```

## 集成到现有脚本

典型用法（带 fallback）：

```python
def get_llm_client():
    token = get_codex_token()
    if token:
        return ("codex-wham", token)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        import anthropic
        return ("anthropic", anthropic.Anthropic(api_key=api_key))

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        import openai
        return ("openai", openai.OpenAI(api_key=openai_key))

    raise RuntimeError("未找到 LLM 凭证：请登录 Codex CLI 或设置 ANTHROPIC_API_KEY")


async def score(backend, client, system, prompt):
    if backend == "codex-wham":
        return await call_wham(token=client, system=system, user_prompt=prompt)
    elif backend == "anthropic":
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    else:
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
```

## 注意事项

- **stream 必须为 True**：`{"stream": false}` 会返回 `400 Bad Request: Stream must be set to true`
- **content type 用 `input_text`**：用 `"type": "text"` 会导致空响应
- **codex-open-client v0.2.2 有 bug**：该库的 `responses.create()` 返回 `output_text: ''`，直接用 httpx 更可靠
- **token 过期处理**：`expires_at` 是 Unix 秒级时间戳，直接用 `time.time()` 对比即可
- **WHAM 是非官方内部接口**：OpenAI 可能随时修改，若调用失败先检查 endpoint 和认证方式

## 模型选择

| 模型 | 适用 | 备注 |
|------|------|------|
| `gpt-5.4-mini` | 默认，高性价比 | ChatGPT Plus 可用 |
| `gpt-5.4` | 更强推理 | ChatGPT Plus 可用 |
| `gpt-5.3-codex` | 代码任务 | 部分账号可用 |

通过环境变量覆盖：`CODEX_MODEL=gpt-5.4 python3 script.py`

## 参考实现

完整实现见：`/Users/lin/workspace/AI/git/AboutMe/job-hunter/matcher/llm_matcher.py`
