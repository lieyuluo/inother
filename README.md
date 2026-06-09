# Enterprise AI Agent

企业级 AI Agent 后端服务 - 一个生产就绪的 FastAPI + React 应用。当前版本 v0.2。

## 项目介绍

Enterprise AI Agent 是一个企业级 AI Agent 应用，提供 AI 对话、文档管理和 RAG（检索增强生成）功能。v0.2 版本增强了 Provider 架构，支持通过配置选择 LLM/Embedding Provider，并在 PostgreSQL 环境下使用 pgvector 原生检索。

## v0.2 功能清单

- 健康检查 API
- Chat 会话和消息管理
- 文档上传、列表、删除
- RAG 检索与问答
- **LLM Provider 可通过配置选择（fake/openai 占位）**
- **Embedding Provider 可通过配置选择（fake/openai 占位）**
- **PostgreSQL 环境下 Retriever 使用 pgvector 原生 cosine distance 查询**
- **SQLite 测试环境下 Retriever 使用 Python cosine fallback**
- Citations 追踪
- AuditLog 审计日志
- 基础 Web UI
- Docker Compose 一键部署
- **datetime.utcnow() 已修复为 timezone-aware 写法**

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
│   │   ├── base.py             # BaseLLMProvider ABC
│   │   ├── fake.py             # FakeLLMProvider
│   │   ├── external.py         # OpenAILLMProvider 占位
│   │   └── provider.py         # get_llm_provider 工厂函数
│   ├── rag/                    # RAG 组件
│   │   ├── embeddings.py       # Embedding Provider（含工厂函数）
│   │   ├── retriever.py         # Retriever（pgvector + Python fallback）
│   │   ├── chunking.py         # 文本切分
│   │   └── loaders.py          # 文档加载
│   ├── schemas/                # Pydantic Schema
│   │   └── services/               # 业务逻辑
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── api/client.ts       # API 客户端
│   │   ├── components/         # React 组件
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
- **`LLM_PROVIDER=openai`**：使用 OpenAILLMProvider 占位。当前版本仅抛出 NotImplementedError，不进行网络调用。未来版本将接入真实 OpenAI API。
- **`EMBEDDING_PROVIDER=fake`**（默认）：使用 FakeEmbeddingProvider，基于 SHA-256 hash 的确定性向量，不访问网络。适用于开发和测试。
- **`EMBEDDING_PROVIDER=openai`**：使用 OpenAIEmbeddingProvider 占位。当前版本仅抛出 NotImplementedError，不进行网络调用。未来版本将接入真实 OpenAI Embedding API。

**注意**：真实 Provider（OpenAI）目前只是接口占位，不会进行任何网络调用。测试环境必须使用 fake provider。

### Retriever 双路径策略

Retriever 根据数据库类型自动选择检索路径：

- **PostgreSQL + pgvector**：使用 pgvector 原生 `<=>` cosine distance 操作符进行向量检索，score = 1 - distance。性能优于 Python 计算。
- **SQLite（测试环境）**：使用 Python 层 cosine similarity 计算。兼容 SQLite，不依赖 pgvector。

数据库差异封装在 Retriever 内部，route/service/agent 层不感知数据库类型。

## GitHub Codespaces 使用说明

**本项目推荐使用 GitHub Codespaces 进行开发和验证。**

### 创建 Codespace

1. 在 GitHub 仓库页面，点击 "Code" 按钮
2. 选择 "Codespaces" 标签
3. 点击 "Create codespace on main"

### Codespace 配置

Codespace 会自动配置开发环境，包括 Python 3.12、Node.js 20、Docker 和 Docker Compose。

### 端口转发

Codespaces 会自动转发以下端口：
- **8000** - 后端 API
- **5173** - 前端 Web UI

在 Codespaces 的 "Ports" 标签中查看转发 URL。

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
4. 使用 psql 执行 pgvector cosine distance 查询（从已有 chunk 取 embedding 作为 query vector）：
   ```bash
   docker compose exec postgres psql -U postgres -d enterprise_ai_agent -c "SELECT id, 1 - (embedding <=> (SELECT embedding FROM document_chunks LIMIT 1)) AS score FROM document_chunks WHERE embedding IS NOT NULL ORDER BY embedding <=> (SELECT embedding FROM document_chunks LIMIT 1) LIMIT 5;"
   ```

## 后端启动方式

### 1. 复制环境变量

```bash
cp .env.example .env
```

### 2. 启动 PostgreSQL 和 Redis

```bash
docker compose up -d postgres redis
```

### 3. 执行数据库迁移

```bash
uv run alembic upgrade head
```

### 4. 启动后端

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. 验证

```bash
curl http://localhost:8000/health
```

## 前端启动方式

### 开发模式

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 http://localhost:5173，API 请求代理到 http://localhost:8000。

### 生产构建

```bash
cd frontend
npm run build
```

## Docker Compose 启动方式

一键启动所有服务（API + Frontend + PostgreSQL + Redis）：

```bash
cp .env.example .env
docker compose up -d --build
```

查看服务状态：

```bash
docker compose ps
```

应看到 4 个服务：api、frontend、postgres、redis。

### 访问服务

- **前端 Web UI**：http://localhost:5173
- **后端 API**：http://localhost:8000
- **API 文档**：http://localhost:8000/docs

**Codespaces 中**：使用 Ports 标签中显示的转发 URL。

## 数据库迁移

```bash
# 执行迁移
uv run alembic upgrade head

# 查看当前版本
uv run alembic current

# 创建新迁移
uv run alembic revision --autogenerate -m "description"
```

## 后端测试命令

```bash
# 运行所有测试
uv run pytest -q

# 运行特定测试
uv run pytest tests/test_health.py

# Lint 检查
uv run ruff check .

# 格式检查
uv run ruff format --check .

# 类型检查
uv run mypy app
```

## 前端 Lint/Build 命令

```bash
cd frontend

# 安装依赖
npm install

# Lint 检查
npm run lint

# 生产构建
npm run build

# 开发服务器
npm run dev
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
| POST | `/api/chat/sessions/{session_id}/messages` | 发送消息（RAG 问答） |

### Document API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/documents/upload` | 上传文档 |
| GET | `/api/documents` | 列出文档 |
| GET | `/api/documents/{document_id}` | 获取单个文档 |
| GET | `/api/documents/{document_id}/chunks` | 获取文档 chunks |
| DELETE | `/api/documents/{document_id}` | 删除文档 |

## Web UI 使用步骤

1. 打开前端页面（http://localhost:5173 或 Codespaces 转发 URL）
2. 页面顶部显示 API 健康状态
3. 左侧边栏：
   - **Upload Document**：上传 .txt 或 .md 文件
   - **Documents**：查看已上传文档列表，支持删除
   - **Sessions**：创建或选择聊天会话
4. 右侧聊天区域：
   - 选择会话后显示消息历史
   - 输入问题并发送
   - 查看 assistant 回答和 citations
5. Citations 显示在聊天区域下方，包含 document_title、chunk_index、score、snippet

## 手动端到端验收流程

### 前置条件

在 GitHub Codespaces 中：

```bash
cp .env.example .env
docker compose up -d --build
```

等待所有服务启动完成（约 30-60 秒）。

### 验收步骤

1. 打开 Codespaces frontend 转发端口 URL
2. 确认页面顶部显示 "API Online"
3. 在左侧 "Upload Document" 区域上传一个 .txt 或 .md 文件
4. 确认文档列表出现该文档，status 显示为 "ready"
5. 点击 "+ New" 按钮创建一个 chat session
6. 点击新创建的 session
7. 在聊天输入框中输入与上传文档相关的问题（如"这个项目支持哪些 API？"）
8. 点击 Send 发送
9. 确认页面显示 assistant answer
10. 确认页面显示 citations（包含 document_title、chunk_index、score、snippet）
11. 刷新页面（F5）
12. 确认 session 列表仍存在
13. 重新选择 session
14. 确认消息历史仍存在
15. 在文档列表中点击 "Delete" 删除文档
16. 确认文档列表不再显示该文档

### API 直接验证

```bash
curl http://localhost:8000/health
```

## v0.2 已知限制

- **Fake LLM**：默认使用 FakeLLMProvider，不访问真实 LLM API，输出为固定格式
- **Fake Embedding**：默认使用 FakeEmbeddingProvider，基于 SHA-256 hash 的确定性向量，不是语义检索
- **OpenAI Provider 占位**：OpenAILLMProvider 和 OpenAIEmbeddingProvider 仅抛出 NotImplementedError，不进行网络调用
- **无认证**：当前无用户认证系统，使用 demo user
- **无权限**：当前无权限管理
- **无 MCP**：未实现 Model Context Protocol
- **无 Tool Calling**：未实现工具调用
- **无 ReAct / Plan-and-Execute**：未实现复杂 Agent 架构
- **仅支持 .txt/.md**：不支持 PDF、DOCX 等文档格式
- **无流式输出**：Chat API 不支持 SSE 流式响应

## v0.3 建议方向

1. 接入真实 LLM（如 OpenAI API）
2. 接入真实 Embedding Provider
3. 实现用户认证和授权
4. 支持 PDF、DOCX 文档格式
5. 实现 SSE 流式输出
6. 实现 ReAct / Tool Calling
7. 实现 MCP
8. 实现多租户
9. 实现 Admin Dashboard

## 许可证

MIT License
