# Enterprise AI Agent

企业级 AI Agent 后端服务 - 一个生产就绪的 FastAPI + React 应用。当前版本 v1.0。

## 项目介绍

Enterprise AI Agent 是一个企业级 AI Agent 应用，提供 AI 对话、文档管理、RAG（检索增强生成）、工具调用、ReAct Agent、Plan-and-Execute Agent 和 MCP 集成功能。v1.0 Phase 1 新增了 Real Provider + SSE Streaming Chat。

## v1.0 功能清单

- 健康检查 API
- Chat 会话和消息管理
- 文档上传、列表、删除
- RAG 检索与问答
- LLM Provider 可通过配置选择（fake / openai-compatible）
- Embedding Provider 可通过配置选择（fake / openai-compatible）
- **OpenAI-compatible LLM Provider（真实实现，非占位）**
- **OpenAI-compatible Embedding Provider（真实实现，非占位）**
- **Provider factory 支持 fake 或 openai-compatible**
- **Provider 错误体系：ProviderError、ProviderConfigError、ProviderTimeoutError、ProviderResponseError**
- PostgreSQL 环境下 Retriever 使用 pgvector 原生 cosine distance 查询
- SQLite 测试环境下 Retriever 使用 Python cosine fallback
- Citations 追踪
- AuditLog 审计日志
- **Tool Registry 工具注册中心**
- **5 个内置工具：echo、calculator、search_documents、get_system_status、list_documents**
- **Chat 中通过 /tool 命令调用工具**
- **Tool API（GET /api/tools, POST /api/tools/{name}/invoke）**
- **Web UI Tool Panel**
- **ReAct Agent（确定性规划器，非生产级 LLM planner）**
- **Chat API 支持 mode="react" 模式**
- **前端 ReAct Steps 展示**
- **Plan-and-Execute Agent（确定性规划器，非生产级 LLM planner）**
- **Chat API 支持 mode="plan_execute" 模式**
- **前端 Plan & Execute Trace 展示**
- **MCP Demo Integration（3 个 demo MCP tools）**
- **MCP Tools 注册到 Tool Registry**
- **ReAct / Plan-and-Execute 支持 MCP tools**
- **SSE Streaming Chat API 端点**
- **SSE 支持 rag / react / plan_execute 模式**
- **SSE 支持 /tool 命令流式输出**
- **前端 ChatWindow 流式开关和流式显示**
- 基础 Web UI
- Docker Compose 一键部署

## Tool Registry 说明

Tool Registry 是统一工具注册中心，管理所有可用工具。

### 内置工具列表

| 工具名 | 说明 | 输入 | 输出 |
|--------|------|------|------|
| `echo_tool` | 回显输入文本 | `{"text": "hello"}` | `{"text": "hello"}` |
| `calculator_tool` | 安全算术表达式计算 | `{"expression": "1+2*3"}` | `{"result": 7}` |
| `search_documents_tool` | 搜索知识库文档 | `{"query": "API", "top_k": 4}` | `{"results": [...]}` |
| `get_system_status_tool` | 获取系统状态 | `{}` | `{"service": "...", "version": "...", "status": "ok"}` |
| `list_documents_tool` | 列出非删除文档 | `{}` | `{"documents": [...]}` |

### GET /api/tools 示例

```bash
curl http://localhost:8000/api/tools
```

响应：

```json
{
  "tools": [
    {
      "name": "echo_tool",
      "description": "Echo back the input text...",
      "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
      "requires_confirmation": false
    }
  ],
  "total": 5
}
```

### POST /api/tools/{tool_name}/invoke 示例

```bash
# 调用 echo_tool
curl -X POST http://localhost:8000/api/tools/echo_tool/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "hello"}}'

# 调用 calculator_tool
curl -X POST http://localhost:8000/api/tools/calculator_tool/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"expression": "1+2*3"}}'
```

响应：

```json
{
  "tool_name": "calculator_tool",
  "status": "success",
  "output": {"result": 7, "expression": "1+2*3"},
  "error": null,
  "latency_ms": 0.5,
  "trace_id": "abc123..."
}
```

### Chat 中使用 /tool 触发工具调用

在聊天输入框中输入 `/tool <工具名> <JSON输入>` 即可调用工具：

```
/tool echo_tool {"text":"hello"}
/tool calculator_tool {"expression":"1+2*3"}
/tool get_system_status_tool {}
```

- 只有以 `/tool` 开头的消息才触发工具调用
- 工具调用结果作为 assistant message 保存
- 工具调用时 citations 为空
- 普通问题仍走 RAG Agent，不受影响
- 支持 mode="react" 走 ReAct Agent 自动选择工具

### Calculator 安全限制

calculator_tool 使用 AST 白名单解析，确保安全：

- **禁止** eval()、exec()
- **禁止** 函数调用（如 print()、__import__()）
- **禁止** 变量/名称访问（如 x + 1）
- **禁止** 属性访问（如 1 .__class__）
- **允许** 数字字面量和基础算术运算符：+ - * / ** % ()
- 表达式长度限制 200 字符
- 除零返回清晰错误

### Tool AuditLog 说明

每次工具调用写入 AuditLog：

- action: `tool.invoke`
- resource_type: `tool`
- metadata 包含：trace_id、tool_name、input_summary、status、latency_ms、error（如有）

## ReAct Agent 说明

ReAct Agent 使用**确定性规划器（DeterministicPlanner）**进行工具选择，**不是**生产级 LLM planner。

### 重要说明

- 当前 ReAct planner 是 **deterministic（基于规则）**，不是基于 LLM 的自动规划
- 规则稳定可测试，但不具备 LLM 的语义理解能力
- 未来接入真实 LLM 后可替换为 LLM planner

### Deterministic Planner 规则

| 规则 | 匹配条件 | 选择工具 |
|------|----------|----------|
| 1a | 包含 "计算/calculate/算/compute" 关键词 | `calculator_tool` |
| 1b | 包含 "what is" + 数字 | `calculator_tool` |
| 2 | 以 "echo " 或 "回显 " 开头 | `echo_tool` |
| 3 | 包含 "系统状态/system status/health" 等 | `get_system_status_tool` |
| 4 | 包含 "搜索文档/search documents/知识库搜索" 等 | `search_documents_tool` |
| 5 | 无匹配 | fallback 到 RAG |

### Chat API mode 参数

发送消息时可指定 `mode` 参数：

```bash
# RAG 模式（默认）
curl -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "What is AI?"}'

# RAG 模式（显式指定）
curl -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "What is AI?", "mode": "rag"}'

# ReAct 模式
curl -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "计算 1+2*3", "mode": "react"}'
```

优先级：`/tool` 命令 > `mode="react"` > 默认 RAG

### ReAct Response 示例

```json
{
  "user_message": {"id": "...", "role": "user", "content": "计算 1+2*3"},
  "assistant_message": {"id": "...", "role": "assistant", "content": "计算结果：1+2*3 = 7"},
  "citations": [],
  "trace_id": "abc123...",
  "steps": [
    {
      "step_index": 0,
      "thought": "Detected arithmetic expression: 1+2*3",
      "action": "call_tool:calculator_tool",
      "action_input": {"expression": "1+2*3"},
      "observation": "{'result': 7, 'expression': '1+2*3'}",
      "status": "success",
      "tool_name": "calculator_tool",
      "latency_ms": 1.2
    }
  ],
  "tool_calls": [
    {"tool_name": "calculator_tool", "status": "success", "trace_id": "...", "latency_ms": 1.2}
  ],
  "mode": "react"
}
```

### ReAct AuditLog 说明

每次 ReAct 执行写入 AuditLog：

- action: `react.run`
- resource_type: `react_session`
- metadata 包含：trace_id、session_id、question、mode、steps_count、tool_calls_count、used_fallback、final_status

注意：ReAct 调用工具时，ToolService 仍会写 `tool.invoke` AuditLog。

### 前端 ReAct 模式使用方式

1. 在聊天输入框上方选择模式：RAG 或 ReAct
2. 选择 ReAct 模式后，发送消息将走 ReAct Agent
3. 回复下方显示 ReAct Steps（Thought、Action、Observation、Status）
4. 继续支持 `/tool` 手动命令（优先级高于 ReAct 模式）

### ReAct 限制

- **无真实 LLM 自动规划**：当前使用确定性规则，不是 LLM chain-of-thought

## Plan-and-Execute Agent 说明

Plan-and-Execute Agent 使用**确定性规划器（DeterministicPlanPlanner）**将用户问题分解为多步计划，然后逐步执行。

### 重要说明

- 当前 Planner 是 **deterministic（基于规则）**，不是生产级 LLM planner
- 规则稳定可测试，但不具备 LLM 的语义理解能力
- 未来接入真实 LLM 后可替换为 LLM planner

### Deterministic Planner 规则

| 规则 | 匹配条件 | 生成步骤 |
|------|----------|----------|
| 1 | "生成报告/总结" + "文档/知识库" | search_documents_tool → final |
| 2 | "先…再…" / "first…then…" 多步模式 | 多个 tool/rag 步骤 → final |
| 3 | "系统状态" + "文档" | get_system_status_tool → search_documents_tool → final |
| 4 | 单工具任务 | 对应 tool → final |
| 5 | 无匹配 | rag → final |

### 执行流程

1. **Planner**：根据问题生成确定性计划
2. **Executor**：逐步执行计划（tool 步骤调用 ToolService，rag 步骤调用 RAGAgent）
3. **Verifier**：检查执行结果（success / partial_error / max_steps_reached）
4. **Finalizer**：生成最终回答

### Chat API mode="plan_execute" 示例

```bash
curl -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "请先查看系统状态，再搜索文档并总结", "mode": "plan_execute"}'
```

优先级：`/tool` 命令 > `mode="plan_execute"` > `mode="react"` > 默认 RAG

### Plan-and-Execute Response 示例

```json
{
  "user_message": {"id": "...", "role": "user", "content": "计算 1+2*3"},
  "assistant_message": {"id": "...", "role": "assistant", "content": "Plan executed successfully. Step 0: ..."},
  "citations": [],
  "trace_id": "abc123...",
  "plan": [
    {"step_index": 0, "description": "Call calculator_tool", "action_type": "tool", "tool_name": "calculator_tool", "tool_input": {"expression": "1+2*3"}, "status": "success"},
    {"step_index": 1, "description": "Generate final answer", "action_type": "final", "status": "success"}
  ],
  "step_results": [
    {"step_index": 0, "status": "success", "output": "{'result': 7, 'expression': '1+2*3'}", "tool_name": "calculator_tool", "latency_ms": 1.2},
    {"step_index": 1, "status": "success", "output": "Final answer generated"}
  ],
  "tool_calls": [{"tool_name": "calculator_tool", "status": "success", "latency_ms": 1.2}],
  "mode": "plan_execute"
}
```

### Plan-and-Execute AuditLog 说明

每次执行写入 AuditLog：

- action: `plan_execute.run`
- metadata 包含：trace_id、session_id、question、mode、plan_steps_count、step_results_count、tool_calls_count、citations_count、used_fallback、final_status

注意：ToolService 仍写 `tool.invoke`，RAGAgent 仍写 `rag.query`。

### 前端 Plan-and-Execute 模式使用方式

1. 在聊天输入框上方选择模式：RAG / ReAct / Plan-Exec
2. 选择 Plan-Exec 模式后，发送消息将走 Plan-and-Execute Agent
3. 回复下方显示 Plan & Execute Trace（每个步骤的 Description、Action Type、Output、Status）
4. 继续支持 `/tool` 手动命令和 ReAct 模式

### Plan-and-Execute 限制

- **无真实 LLM 规划**：当前使用确定性规则
- **非复杂多智能体**：单 Agent 顺序执行
- **max_steps 限制**：超过最大步数会截断

## MCP Demo Integration 说明

本阶段实现了 MCP (Model Context Protocol) 的 demo 集成，用于企业 Agent 平台内部工具标准化接入。

### 重要说明

- 当前为 **demo MCP integration**，不是生产级 MCP 实现
- 使用 in-process demo server，不实现标准 MCP transport (stdio/HTTP)
- 未来可替换为标准 MCP SDK
- 所有 demo tools 数据 deterministic、可测试

### MCP_DEMO_ENABLED 配置

在 `.env` 中设置：

```
MCP_DEMO_ENABLED=true
```

默认启用。设为 `false` 则不注册 MCP tools。

### MCP Demo Tools

| Tool | 说明 | 输入 | 输出 |
|------|------|------|------|
| `mcp_echo` | Echo 回显 | `{"text": "hello"}` | `{"text": "hello", "source": "mcp"}` |
| `mcp_get_business_metric` | 获取业务指标 | `{"metric": "revenue"}` | `{"metric": "revenue", "value": 1250000.0, "unit": "USD"}` |
| `mcp_create_ticket` | 创建 demo 工单 | `{"title": "...", "description": "..."}` | `{"ticket_id": "DEMO-xxx", "title": "...", "status": "created"}` |

支持的 metric 值：`revenue`、`active_users`、`tickets`

### GET /api/tools 查看 MCP tools

```bash
curl http://localhost:8000/api/tools
```

返回的工具列表包含 `mcp_echo`、`mcp_get_business_metric`、`mcp_create_ticket`。

### POST /api/tools/mcp_echo/invoke 示例

```bash
curl -X POST http://localhost:8000/api/tools/mcp_echo/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "hello MCP"}}'
```

### Chat /tool mcp_echo 示例

```bash
curl -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "/tool mcp_echo {\"text\":\"hello\"}"}'
```

### ReAct 调用 MCP tool 示例

选择 ReAct 模式，输入 "查询 revenue 业务指标"，ReAct planner 会选择 `mcp_get_business_metric`。

### Plan-and-Execute 调用 MCP tool 示例

选择 Plan-Exec 模式，输入 "请先查看业务指标，再创建工单"，plan 会包含 `mcp_get_business_metric` + `mcp_create_ticket` + final。

### MCP 当前限制

- **In-process demo server**：不是标准 MCP transport
- **非生产级 MCP transport**：未实现 stdio/HTTP 传输
- **不访问外部系统**：所有数据为 demo 固定数据
- **不实现标准完整 MCP 协议全部能力**

## SSE Streaming Chat API 说明

v1.0 Phase 1 新增 SSE（Server-Sent Events）流式聊天 API，支持实时流式输出。

### 端点

```
POST /api/chat/sessions/{session_id}/messages/stream
```

### 请求体

与非流式端点相同：

```json
{"content": "...", "mode": "rag|react|plan_execute"}
```

### 响应

- Content-Type: `text/event-stream`
- 每个 SSE 事件格式：`event: <type>\ndata: <json>\n\n`

### SSE 事件类型

| 事件类型 | 说明 | 数据示例 |
|----------|------|----------|
| `trace` | 追踪信息 | `{"trace_id": "abc123..."}` |
| `user_message` | 用户消息 | `{"id": "...", "role": "user", "content": "..."}` |
| `token` | 流式 token（逐字输出） | `{"token": "你"}` |
| `citations` | 引用信息 | `{"citations": [...]}` |
| `steps` | ReAct 步骤 | `{"steps": [...]}` |
| `plan` | Plan-and-Execute 计划 | `{"plan": [...]}` |
| `step_results` | Plan 执行结果 | `{"step_results": [...]}` |
| `tool_calls` | 工具调用记录 | `{"tool_calls": [...]}` |
| `assistant_message` | 完整 assistant 消息 | `{"id": "...", "role": "assistant", "content": "..."}` |
| `done` | 流式结束 | `{"status": "done"}` |
| `error` | 错误事件 | `{"error": "..."}` |

### 错误处理

- **Session 不存在**：返回 SSE `error` 事件
- **空 content**：返回 HTTP 422

### SSE 流式请求示例

```bash
curl -N -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages/stream \
  -H "Content-Type: application/json" \
  -d '{"content": "What is AI?", "mode": "rag"}'
```

### SSE 流式 /tool 命令示例

```bash
curl -N -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages/stream \
  -H "Content-Type: application/json" \
  -d '{"content": "/tool echo_tool {\"text\":\"hello\"}"}'
```

## Web UI Tool Panel 使用说明

1. 左侧边栏显示 Tool Panel
2. 下拉选择工具
3. 输入 JSON 参数（如 `{"text": "hello"}`）
4. 点击 "Invoke" 按钮
5. 查看工具返回结果（成功/错误、输出、延迟）
6. 也可在聊天框中使用 `/tool` 命令调用工具

## 技术栈

**后端：**
- Python 3.12
- FastAPI
- SQLAlchemy 2.x（异步）
- Alembic
- PostgreSQL + pgvector
- Redis
- pytest

**前端：**
- Vite 6
- React 18
- TypeScript
- ESLint

**基础设施：**
- Docker Compose
- GitHub Actions CI

## 项目目录

```
enterprise-ai-agent/
├── app/                        # 后端应用
│   ├── agents/                 # RAG Agent, ReAct Agent, Plan-and-Execute Agent
│   ├── api/                    # API 路由
│   ├── core/                   # 配置、日志、错误处理
│   ├── db/                     # 数据库模型、Repository
│   ├── mcp/                    # MCP Demo Integration
│   ├── llm/                    # LLM Provider
│   ├── rag/                    # RAG 组件
│   ├── schemas/                # Pydantic Schema
│   ├── services/               # 业务逻辑
│   └── tools/                  # 工具模块
│       ├── base.py             # BaseTool ABC
│       ├── schemas.py          # ToolResult, ToolInfo 等
│       ├── registry.py         # ToolRegistry
│       ├── builtin.py          # 内置工具实现
│       └── service.py          # ToolService
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── api/client.ts       # API 客户端
│   │   ├── components/         # React 组件
│   │   │   ├── ToolPanel.tsx   # 工具面板组件
│   │   │   ├── ReActSteps.tsx  # ReAct 步骤展示组件
│   │   │   ├── PlanExecuteTrace.tsx  # Plan-Execute 追踪组件
│   │   │   └── ChatWindow.tsx  # 聊天窗口组件（含流式开关）
│   │   ├── App.tsx             # 主应用
│   │   ├── types.ts            # TypeScript 类型
│   │   └── styles.css          # 样式
│   ├── Dockerfile              # 前端 Docker 镜像
│   ├── nginx.conf              # Nginx 配置
│   └── package.json
├── tests/                      # 后端测试
├── alembic/                    # 数据库迁移
├── docker-compose.yml          # Docker Compose 配置
├── Dockerfile                  # 后端 Docker 镜像
├── pyproject.toml              # Python 项目配置
└── .github/workflows/ci.yml    # GitHub Actions CI
```

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `APP_NAME` | 应用名称 | `enterprise-ai-agent` |
| `APP_ENV` | 运行环境 | `development` |
| `APP_VERSION` | 应用版本 | `1.0.0` |
| `DATABASE_URL` | PostgreSQL 连接 URL | `postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai_agent` |
| `REDIS_URL` | Redis 连接 URL | `redis://localhost:6379/0` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `CORS_ORIGINS` | CORS 允许的源 | `["http://localhost:3000","http://localhost:5173","http://localhost:8000"]` |
| `SECRET_KEY` | 安全密钥 | 需在生产环境更改 |
| `LLM_PROVIDER` | LLM Provider 名称 | `fake` |
| `OPENAI_API_KEY` | OpenAI API Key（openai provider 必需） | 空 |
| `OPENAI_BASE_URL` | OpenAI 兼容服务 Base URL | `https://api.openai.com/v1` |
| `OPENAI_LLM_MODEL` | OpenAI LLM 模型 | `gpt-4o-mini` |
| `EMBEDDING_PROVIDER` | Embedding Provider 名称 | `fake` |
| `OPENAI_EMBEDDING_MODEL` | OpenAI Embedding 模型 | `text-embedding-3-small` |
| `PROVIDER_TIMEOUT_SECONDS` | Provider 请求超时时间（秒） | `30` |
| `PROVIDER_MAX_RETRIES` | Provider 请求最大重试次数 | `2` |
| `RAG_CHUNK_SIZE` | 文本切分大小 | `800` |
| `RAG_CHUNK_OVERLAP` | 切分重叠大小 | `100` |
| `EMBEDDING_DIMENSION` | Embedding 维度 | `1536` |
| `RAG_TOP_K` | RAG 检索返回的最大结果数 | `4` |
| `RAG_SNIPPET_MAX_LENGTH` | Citation snippet 最大长度 | `300` |
| `VITE_API_BASE_URL` | 前端 API 地址 | `http://localhost:8000` |

### Provider 配置说明

- **`LLM_PROVIDER=fake`**（默认）：使用 FakeLLMProvider，不访问网络，输出稳定。适用于开发和测试。
- **`LLM_PROVIDER=openai`**：使用 OpenAILLMProvider，通过 httpx.Client 调用 OpenAI 兼容 API。需要设置 `OPENAI_API_KEY`，否则抛出 `ProviderConfigError`。
- **`EMBEDDING_PROVIDER=fake`**（默认）：使用 FakeEmbeddingProvider，基于 SHA-256 hash 的确定性向量，不访问网络。
- **`EMBEDDING_PROVIDER=openai`**：使用 OpenAIEmbeddingProvider，通过 httpx.AsyncClient 调用 OpenAI 兼容 Embedding API。需要设置 `OPENAI_API_KEY`，否则抛出 `ProviderConfigError`。

**OpenAI 兼容服务**：通过 `OPENAI_BASE_URL` 可配置兼容 OpenAI API 的服务地址（如 Azure OpenAI、本地部署等），默认为 `https://api.openai.com/v1`。

**Provider 超时和重试**：通过 `PROVIDER_TIMEOUT_SECONDS`（默认 30 秒）和 `PROVIDER_MAX_RETRIES`（默认 2 次）配置请求超时和重试策略。

**注意**：测试默认使用 fake provider。真实 provider 需要用户自行提供 API key。

### Provider Error 说明

Provider 错误体系基于 `ProviderError` 基类，提供细粒度错误类型：

| 错误类型 | 说明 | 触发场景 |
|----------|------|----------|
| `ProviderError` | Provider 基础错误 | 所有 Provider 错误的基类 |
| `ProviderConfigError` | 配置错误 | `OPENAI_API_KEY` 未设置时使用 openai provider |
| `ProviderTimeoutError` | 请求超时 | 请求超过 `PROVIDER_TIMEOUT_SECONDS` |
| `ProviderResponseError` | 响应错误 | API 返回非 200 状态码或响应解析失败 |

### Retriever 双路径策略

Retriever 根据数据库类型自动选择检索路径：

- **PostgreSQL + pgvector**：使用 pgvector 原生 `<=>` cosine distance 操作符进行向量检索，score = 1 - distance。
- **SQLite（测试环境）**：使用 Python 层 cosine similarity 计算。

数据库差异封装在 Retriever 内部，route/service/agent 层不感知数据库类型。

## GitHub Codespaces 使用说明

**本项目推荐使用 GitHub Codespaces 进行开发和验证。**

### 创建 Codespace

1. 在 GitHub 仓库页面，点击 "Code" 按钮
2. 选择 "Codespaces" 标签
3. 点击 "Create codespace on main"

### 端口转发

Codespaces 会自动转发以下端口：
- **8000** - 后端 API
- **5173** - 前端 Web UI

### Codespaces pgvector 验证步骤

1. 启动服务：
   ```bash
   cp .env.example .env
   docker compose up -d postgres redis
   uv run alembic upgrade head
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. 上传文档并创建 chat session
3. 使用 psql 验证 embedding 存在：
   ```bash
   docker compose exec postgres psql -U postgres -d enterprise_ai_agent -c "SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL;"
   ```

## 后端启动方式

```bash
cp .env.example .env
docker compose up -d postgres redis
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 前端启动方式

```bash
cd frontend
npm install
npm run dev
```

## Docker Compose 启动方式

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

## API 简介

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 基础健康检查 |
| GET | `/health/ready` | 就绪检查 |
| GET | `/health/live` | 存活检查 |

### Chat API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/sessions` | 创建聊天会话 |
| GET | `/api/chat/sessions` | 列出聊天会话 |
| GET | `/api/chat/sessions/{session_id}` | 获取单个会话 |
| GET | `/api/chat/sessions/{session_id}/messages` | 获取消息列表 |
| POST | `/api/chat/sessions/{session_id}/messages` | 发送消息（RAG 问答、/tool 调用、ReAct 或 Plan-Execute 模式） |
| POST | `/api/chat/sessions/{session_id}/messages/stream` | SSE 流式发送消息（支持 rag / react / plan_execute 模式） |

### Document API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/documents/upload` | 上传文档 |
| GET | `/api/documents` | 列出文档 |
| GET | `/api/documents/{document_id}` | 获取单个文档 |
| GET | `/api/documents/{document_id}/chunks` | 获取文档 chunks |
| DELETE | `/api/documents/{document_id}` | 删除文档 |

### Tool API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tools` | 列出可用工具 |
| POST | `/api/tools/{tool_name}/invoke` | 调用工具 |

## Web UI 使用步骤

1. 打开前端页面（http://localhost:5173 或 Codespaces 转发 URL）
2. 页面顶部显示 API 健康状态
3. 左侧边栏：
   - **Upload Document**：上传 .txt 或 .md 文件
   - **Documents**：查看已上传文档列表，支持删除
   - **Tool Panel**：选择并调用工具，查看结果
   - **Sessions**：创建或选择聊天会话
4. 右侧聊天区域：
   - 选择会话后显示消息历史
   - 选择模式：RAG / ReAct / Plan-Exec
   - **流式开关（Streaming Toggle）**：开启后使用 SSE 流式输出，实时显示 token
   - 输入问题并发送（RAG 问答、ReAct 工具选择或 Plan-Execute 多步计划）
   - 输入 `/tool <name> <json>` 调用工具（优先级最高）
   - 查看 assistant 回答、citations、ReAct Steps 和 Plan Trace

## 手动端到端验收流程

在 GitHub Codespaces 中：

```bash
cp .env.example .env
docker compose up -d --build
```

1. 打开 Codespaces frontend 转发端口 URL
2. 确认页面顶部显示 "API Online"
3. 确认文档上传仍可用
4. 确认普通 RAG chat 仍可用
5. 确认 Tool Panel 显示工具列表
6. 在 Tool Panel 调用 echo_tool
7. 在 Tool Panel 调用 calculator_tool
8. 在 Chat 输入框输入：`/tool echo_tool {"text":"hello"}`
9. 确认 assistant message 显示工具结果
10. 在 Chat 输入框输入：`/tool calculator_tool {"expression":"1+2*3"}`
11. 确认 assistant message 显示计算结果
12. 输入普通问题，确认仍走 RAG 并返回 citations
13. 在 Chat 模式选择 "ReAct"
14. 输入：`计算 1+2*3`，确认 answer 显示 7，页面显示 ReAct Steps
15. 输入：`echo hello`，确认调用 echo_tool
16. 输入：`系统状态`，确认调用 get_system_status_tool
17. 输入普通文档问题，确认 fallback 到 RAG
18. 输入 `/tool calculator_tool {"expression":"1+2"}`，确认 /tool 优先级高于 ReAct
19. 在 Chat 模式选择 "Plan-Exec"
20. 输入：`请先查看系统状态，再搜索文档并总结`
21. 确认页面显示 Plan 和 Step Results
22. 确认调用 get_system_status_tool 和 search_documents_tool
23. 输入：`计算 1+2*3`，确认 calculator_tool + final 执行
24. 输入无法规划的问题，确认 fallback 到 RAG
25. 输入 `/tool calculator_tool {"expression":"1+2"}`，确认 /tool 优先级高于 Plan-Exec
26. 在 Tool Panel 确认工具列表包含 mcp_echo、mcp_get_business_metric、mcp_create_ticket
27. 在 Tool Panel 调用 mcp_echo
28. 在 Tool Panel 调用 mcp_get_business_metric，metric=revenue
29. 在 Chat 输入：`/tool mcp_echo {"text":"hello"}`
30. 选择 ReAct mode，输入：`查询 revenue 业务指标`，确认调用 mcp_get_business_metric
31. 选择 Plan-Exec mode，输入：`请先查看业务指标，再创建工单`，确认 plan 包含 MCP tools
32. 开启流式开关（Streaming Toggle）
33. 输入普通问题，确认 SSE 流式逐字输出 token
34. 选择 ReAct 模式 + 流式，输入：`计算 1+2*3`，确认流式输出包含 steps 事件
35. 选择 Plan-Exec 模式 + 流式，输入：`请先查看系统状态，再搜索文档并总结`，确认流式输出包含 plan 和 step_results 事件
36. 流式模式下输入 `/tool echo_tool {"text":"hello"}`，确认流式输出工具结果
37. 关闭流式开关，确认回退到非流式模式

## v1.0 已知限制

- **Fake LLM**：默认使用 FakeLLMProvider，不访问真实 LLM API
- **Fake Embedding**：基于 SHA-256 hash 的确定性向量，不是语义检索
- **测试默认使用 fake provider**：CI 和开发环境使用 fake provider
- **真实 provider 需要用户自行提供 API key**：openai provider 需要 OPENAI_API_KEY
- **Fake streaming 是模拟 token chunk**：fake provider 的流式输出是模拟逐字输出，非真实 LLM 流式
- **不含认证/RBAC**：当前无用户认证和权限管理系统
- **ReAct 是确定性规划器**：不是生产级 LLM planner，基于规则匹配
- **Plan-and-Execute 是确定性规划器**：不是生产级 LLM planner，基于规则匹配
- **MCP 是 demo 集成**：in-process demo server，非标准 MCP transport
- **仅支持 .txt/.md**：不支持 PDF、DOCX 等文档格式

## v1.0+ 后续方向

**v1.0 Phase 1 已完成：**
- ~~接入真实 LLM（如 OpenAI API）~~ ✅ OpenAI-compatible Provider 已实现
- ~~实现 SSE 流式输出~~ ✅ SSE Streaming Chat API 已实现

**待实现：**
1. 实现 LLM 驱动的 ReAct planner（替换确定性规划器）
2. 实现 LLM 驱动的 Plan-and-Execute planner
3. 实现标准 MCP transport（stdio/HTTP）
4. 实现用户认证和授权（RBAC）
5. 支持 PDF、DOCX 文档格式
6. 实现多租户
7. 实现 Admin Dashboard

## 许可证

MIT License
