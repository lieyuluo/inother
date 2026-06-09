# Enterprise AI Agent

企业级 AI Agent 后端服务 - 一个生产就绪的 FastAPI 应用。

## 项目介绍

Enterprise AI Agent 是一个企业级 AI Agent 后端服务，旨在提供可靠的 AI 对话、文档管理和 RAG（检索增强生成）功能。当前为 v0.1 版本，Phase 3 已实现文档上传、解析、切分和 Embedding 入库。

## 技术栈

- **Python 3.12**
- **FastAPI** - 现代、高性能的 Web 框架
- **SQLAlchemy 2.x** - 异步 ORM
- **Alembic** - 数据库迁移工具
- **PostgreSQL** (pgvector/pgvector:pg16) - 带 pgvector 扩展的关系数据库
- **Redis** - 缓存和会话存储
- **pytest** - 测试框架
- **pytest-asyncio** - 异步测试支持
- **httpx** - HTTP 客户端
- **ruff** - 快速的 Python linter 和 formatter
- **mypy** - 静态类型检查
- **uv** - 快速的 Python 包管理器
- **Docker Compose** - 容器编排

## GitHub Codespaces 启动方式

**重要说明：本项目当前阶段推荐使用 GitHub Codespaces 验证，而不是本地 Docker。**

### 创建 Codespace

1. 在 GitHub 仓库页面，点击 "Code" 按钮
2. 选择 "Codespaces" 标签
3. 点击 "Create codespace on main"

### Codespace 配置

Codespace 会自动配置开发环境，包括：
- Python 3.12
- Docker 和 Docker Compose
- 所有必要的开发工具

## 环境变量说明

项目使用以下环境变量（可在 `.env` 文件中配置）：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `APP_NAME` | 应用名称 | `enterprise-ai-agent` |
| `APP_ENV` | 运行环境 | `development` |
| `APP_VERSION` | 应用版本 | `0.1.0` |
| `DATABASE_URL` | PostgreSQL 连接 URL | `postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai_agent` |
| `REDIS_URL` | Redis 连接 URL | `redis://localhost:6379/0` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `CORS_ORIGINS` | CORS 允许的源 | `["http://localhost:3000","http://localhost:8000"]` |
| `SECRET_KEY` | 安全密钥 | 需在生产环境更改 |
| `RAG_CHUNK_SIZE` | 文本切分大小 | `800` |
| `RAG_CHUNK_OVERLAP` | 切分重叠大小 | `100` |
| `EMBEDDING_DIMENSION` | Embedding 维度 | `1536` |

## 快速开始

### 1. 复制环境变量配置

```bash
cp .env.example .env
```

### 2. 启动 PostgreSQL 和 Redis

在 GitHub Codespaces 中：

```bash
docker compose up -d postgres redis
```

等待服务健康检查完成：

```bash
docker compose ps
```

### 3. 执行数据库迁移

```bash
uv run alembic upgrade head
```

### 4. 启动 FastAPI 服务

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. 验证服务

在另一个终端或使用 curl：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/live
```

**注意**：如果 Codespaces 自动端口转发导致 `localhost` 不可访问，请使用 Codespaces 提供的 forwarded port URL（通常在 Codespace 的 "Ports" 标签中查看）。

## Chat API 使用说明

**重要说明**：当前 assistant response 是 mock 实现，不是真实 LLM。Mock 回复格式为 `Echo: {用户输入}`。

### 创建聊天会话

```bash
curl -X POST http://localhost:8000/api/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"My Chat Session"}'
```

响应示例：
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "My Chat Session",
  "is_active": true,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": null
}
```

如果不提供 title，默认使用 "New Chat"：

```bash
curl -X POST http://localhost:8000/api/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 列出聊天会话

```bash
curl http://localhost:8000/api/chat/sessions
```

响应示例：
```json
{
  "sessions": [
    {
      "id": "...",
      "title": "My Chat Session",
      "is_active": true,
      "created_at": "...",
      "updated_at": null
    }
  ],
  "total": 1
}
```

### 获取单个会话

```bash
curl http://localhost:8000/api/chat/sessions/{session_id}
```

### 发送消息

```bash
curl -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content":"Hello, this is a test message"}'
```

响应示例：
```json
{
  "user_message": {
    "id": "...",
    "session_id": "...",
    "role": "user",
    "content": "Hello, this is a test message",
    "token_count": null,
    "created_at": "..."
  },
  "assistant_message": {
    "id": "...",
    "session_id": "...",
    "role": "assistant",
    "content": "Echo: Hello, this is a test message",
    "token_count": null,
    "created_at": "..."
  }
}
```

### 获取消息列表

```bash
curl http://localhost:8000/api/chat/sessions/{session_id}/messages
```

响应示例：
```json
{
  "messages": [
    {
      "id": "...",
      "session_id": "...",
      "role": "user",
      "content": "Hello",
      "token_count": null,
      "created_at": "..."
    },
    {
      "id": "...",
      "session_id": "...",
      "role": "assistant",
      "content": "Echo: Hello",
      "token_count": null,
      "created_at": "..."
    }
  ],
  "total": 2
}
```

消息按 `created_at` 升序返回。

## Document API 使用说明

**重要说明**：
- 当前支持 `.txt` 和 `.md` 文件上传
- 当前 Embedding 使用 FakeEmbeddingProvider（deterministic，不访问网络）
- 当前阶段只做文档入库，不做 RAG 问答
- 删除策略为软删除（status 设为 'deleted'）

### 上传文档

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@README.md"
```

响应示例：
```json
{
  "document": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "README.md",
    "filename": "README.md",
    "file_type": "md",
    "file_size": 1234,
    "status": "ready",
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": null
  },
  "chunks_count": 5
}
```

上传 .txt 文件：
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@test.txt"
```

### 列出文档

```bash
curl http://localhost:8000/api/documents
```

响应示例：
```json
{
  "documents": [
    {
      "id": "...",
      "title": "README.md",
      "filename": "README.md",
      "file_type": "md",
      "file_size": 1234,
      "status": "ready",
      "created_at": "...",
      "updated_at": null
    }
  ],
  "total": 1
}
```

### 获取单个文档

```bash
curl http://localhost:8000/api/documents/{document_id}
```

### 获取文档 Chunks

```bash
curl http://localhost:8000/api/documents/{document_id}/chunks
```

响应示例：
```json
{
  "chunks": [
    {
      "id": "...",
      "document_id": "...",
      "chunk_index": 0,
      "content": "第一段文本内容...",
      "token_count": 200,
      "created_at": "...",
      "updated_at": null
    },
    {
      "id": "...",
      "document_id": "...",
      "chunk_index": 1,
      "content": "第二段文本内容...",
      "token_count": 180,
      "created_at": "...",
      "updated_at": null
    }
  ],
  "total": 5
}
```

**注意**：API 不返回 embedding 向量，避免响应过大。

### 删除文档

```bash
curl -X DELETE http://localhost:8000/api/documents/{document_id}
```

删除后返回 204 No Content。删除为软删除，文档 status 设为 'deleted'，默认不再出现在列表中。

## 运行测试

```bash
# 运行所有测试
uv run pytest -q

# 运行详细测试
uv run pytest -v

# 运行特定测试文件
uv run pytest tests/test_health.py
uv run pytest tests/test_chat.py
```

## 代码质量检查

### Lint 检查

```bash
uv run ruff check .
```

### 格式检查

```bash
uv run ruff format --check .
```

### 类型检查

```bash
uv run mypy app
```

### 自动格式化

```bash
uv run ruff format .
```

## 项目结构

```
enterprise-ai-agent/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_health.py # 健康检查路由
│   │   ├── routes_chat.py   # Chat API 路由
│   │   └── routes_documents.py # Document API 路由
│   ├── core/
│   │   ├── config.py        # 配置管理
│   │   ├── logging.py       # 日志配置
│   │   ├── errors.py        # 错误处理
│   │   └── lifespan.py      # 应用生命周期
│   ├── db/
│   │   ├── base.py          # SQLAlchemy Base
│   │   ├── session.py       # 数据库会话
│   │   ├── models.py        # 数据模型
│   │   └── repositories.py  # 数据库 Repository 层
│   ├── schemas/
│   │   ├── health.py        # 健康检查 Schema
│   │   ├── chat.py          # Chat API Schema
│   │   └── document.py      # Document API Schema
│   ├── rag/
│   │   ├── __init__.py      # RAG 模块入口
│   │   ├── loaders.py       # 文档加载器
│   │   ├── chunking.py      # 文本切分
│   │   ├── embeddings.py    # Embedding Provider
│   │   └── ingestion.py     # 文档入库流程
│   └── services/
│       ├── __init__.py
│       ├── chat_service.py  # Chat 业务逻辑
│       └── document_service.py # Document 业务逻辑
├── tests/
│   ├── conftest.py          # 测试配置
│   ├── test_health.py       # 健康检查测试
│   ├── test_chat.py         # Chat API 测试
│   └── test_documents.py    # Document API 测试
├── alembic/
│   ├── env.py               # Alembic 环境
│   ├── script.py.mako       # 迁移模板
│   └── versions/
│       └── 001_initial.py   # 初始迁移
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI
├── pyproject.toml           # 项目配置
├── docker-compose.yml       # Docker Compose 配置
├── Dockerfile               # Docker 镜像配置
├── alembic.ini              # Alembic 配置
├── .env.example             # 环境变量示例
├── README.md                # 项目文档
└── REPORT.md                # 阶段报告
```

## API 端点

### 健康检查

- `GET /health` - 基础健康检查
- `GET /health/ready` - 就绪检查（包含数据库和 Redis 状态）
- `GET /health/live` - 存活检查

### Chat API

- `POST /api/chat/sessions` - 创建聊天会话
- `GET /api/chat/sessions` - 列出聊天会话
- `GET /api/chat/sessions/{session_id}` - 获取单个会话
- `GET /api/chat/sessions/{session_id}/messages` - 获取会话消息列表
- `POST /api/chat/sessions/{session_id}/messages` - 发送消息

### Document API

- `POST /api/documents/upload` - 上传文档
- `GET /api/documents` - 列出文档
- `GET /api/documents/{document_id}` - 获取单个文档
- `GET /api/documents/{document_id}/chunks` - 获取文档 chunks
- `DELETE /api/documents/{document_id}` - 删除文档（软删除）

### 响应示例

**GET /health**
```json
{
  "status": "ok",
  "service": "enterprise-ai-agent",
  "version": "0.1.0"
}
```

**GET /health/ready**
```json
{
  "status": "ok",
  "database": "not_checked",
  "redis": "not_checked"
}
```

**GET /health/live**
```json
{
  "status": "ok"
}
```

## 数据库模型

Phase 1 包含以下数据库模型：

1. **User** - 用户模型（认证和所有权）
2. **ChatSession** - 聊天会话模型
3. **ChatMessage** - 聊天消息模型
4. **Document** - 文档模型
5. **DocumentChunk** - 文档分块模型（支持 pgvector）
6. **AuditLog** - 审计日志模型

所有模型使用 UUID 作为主键，核心表包含 `created_at`，可更新表包含 `updated_at`。

## 本地 Docker 说明

**本项目当前阶段不要求本地安装 Docker Desktop。**

所有 Docker 相关验证在 GitHub Codespaces 中进行。如果您需要在本地运行 Docker 命令，请确保已安装 Docker 和 Docker Compose。

## 许可证

MIT License