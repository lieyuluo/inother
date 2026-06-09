# Enterprise AI Agent

企业级 AI Agent 后端服务 - 一个生产就绪的 FastAPI + React 应用。当前版本 v0.2。

## 项目介绍

Enterprise AI Agent 是一个企业级 AI Agent 应用，提供 AI 对话、文档管理、RAG（检索增强生成）和工具调用功能。v0.2 Phase 2 新增了 Tool Registry 和基础 Tool Calling 能力。

## v0.2 功能清单

- 健康检查 API
- Chat 会话和消息管理
- 文档上传、列表、删除
- RAG 检索与问答
- LLM Provider 可通过配置选择（fake/openai 占位）
- Embedding Provider 可通过配置选择（fake/openai 占位）
- PostgreSQL 环境下 Retriever 使用 pgvector 原生 cosine distance 查询
- SQLite 测试环境下 Retriever 使用 Python cosine fallback
- Citations 追踪
- AuditLog 审计日志
- **Tool Registry 工具注册中心**
- **5 个内置工具：echo、calculator、search_documents、get_system_status、list_documents**
- **Chat 中通过 /tool 命令调用工具**
- **Tool API（GET /api/tools, POST /api/tools/{name}/invoke）**
- **Web UI Tool Panel**
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
- 当前不支持 LLM 自动选择工具，ReAct 在下一 Phase

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
│   ├── agents/                 # RAG Agent
│   ├── api/                    # API 路由
│   ├── core/                   # 配置、日志、错误处理
│   ├── db/                     # 数据库模型、Repository
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
│   │   │   └── ToolPanel.tsx   # 工具面板组件
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
| `APP_VERSION` | 应用版本 | `0.2.0` |
| `DATABASE_URL` | PostgreSQL 连接 URL | `postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai_agent` |
| `REDIS_URL` | Redis 连接 URL | `redis://localhost:6379/0` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `CORS_ORIGINS` | CORS 允许的源 | `["http://localhost:3000","http://localhost:5173","http://localhost:8000"]` |
| `SECRET_KEY` | 安全密钥 | 需在生产环境更改 |
| `LLM_PROVIDER` | LLM Provider 名称 | `fake` |
| `OPENAI_API_KEY` | OpenAI API Key（v0.2+ 接入真实 LLM 时需要） | 空 |
| `OPENAI_LLM_MODEL` | OpenAI LLM 模型 | `gpt-3.5-turbo` |
| `EMBEDDING_PROVIDER` | Embedding Provider 名称 | `fake` |
| `OPENAI_EMBEDDING_MODEL` | OpenAI Embedding 模型 | `text-embedding-ada-002` |
| `RAG_CHUNK_SIZE` | 文本切分大小 | `800` |
| `RAG_CHUNK_OVERLAP` | 切分重叠大小 | `100` |
| `EMBEDDING_DIMENSION` | Embedding 维度 | `1536` |
| `RAG_TOP_K` | RAG 检索返回的最大结果数 | `4` |
| `RAG_SNIPPET_MAX_LENGTH` | Citation snippet 最大长度 | `300` |
| `VITE_API_BASE_URL` | 前端 API 地址 | `http://localhost:8000` |

### Provider 配置说明

- **`LLM_PROVIDER=fake`**（默认）：使用 FakeLLMProvider，不访问网络，输出稳定。适用于开发和测试。
- **`LLM_PROVIDER=openai`**：使用 OpenAILLMProvider 占位。当前版本仅抛出 NotImplementedError，不进行网络调用。
- **`EMBEDDING_PROVIDER=fake`**（默认）：使用 FakeEmbeddingProvider，基于 SHA-256 hash 的确定性向量，不访问网络。
- **`EMBEDDING_PROVIDER=openai`**：使用 OpenAIEmbeddingProvider 占位。当前版本仅抛出 NotImplementedError，不进行网络调用。

**注意**：真实 Provider（OpenAI）目前只是接口占位，不会进行任何网络调用。测试环境必须使用 fake provider。

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
| POST | `/api/chat/sessions/{session_id}/messages` | 发送消息（RAG 问答或 /tool 调用） |

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
   - 输入问题并发送（RAG 问答）
   - 输入 `/tool <name> <json>` 调用工具
   - 查看 assistant 回答和 citations

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

## v0.2 已知限制

- **Fake LLM**：默认使用 FakeLLMProvider，不访问真实 LLM API
- **Fake Embedding**：基于 SHA-256 hash 的确定性向量，不是语义检索
- **OpenAI Provider 占位**：仅抛出 NotImplementedError
- **无认证**：当前无用户认证系统
- **无权限**：当前无权限管理
- **无 MCP**：未实现 Model Context Protocol
- **无 ReAct**：当前 /tool 是简单命令触发，不支持 LLM 自动选择工具或多步循环
- **仅支持 .txt/.md**：不支持 PDF、DOCX 等文档格式
- **无流式输出**：Chat API 不支持 SSE 流式响应

## v0.3 建议方向

1. 接入真实 LLM（如 OpenAI API）
2. 实现 ReAct 循环（LLM 自动选择工具）
3. 实现用户认证和授权
4. 支持 PDF、DOCX 文档格式
5. 实现 SSE 流式输出
6. 实现 MCP
7. 实现多租户
8. 实现 Admin Dashboard

## 许可证

MIT License
