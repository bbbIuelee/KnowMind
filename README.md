# KnowMind

KnowMind 是一个面向知识库问答场景的 RAG 应用，目标是提供文档上传、知识检索、智能问答、会话管理、流式输出和检索过程可视化等能力。

## 功能目标

- 用户注册、登录和基于角色的权限控制
- 文档上传、解析、分块和向量化入库
- 基于 Milvus 的向量检索和混合检索
- 基于 LangChain / LangGraph 的 RAG 问答流程
- 聊天会话持久化和历史记录管理
- SSE 流式响应和前端实时渲染
- 检索来源、评分和过程追踪展示

## 技术栈

- 后端：FastAPI、Pydantic、SQLAlchemy、Uvicorn
- 前端：Vue 3 CDN、原生 JavaScript、CSS
- 检索：Milvus、Dense Embedding、BM25 Sparse Embedding、Rerank
- 编排：LangChain、LangGraph
- 存储：PostgreSQL、Redis

## 项目结构

```text
KnowMind/
├── backend/          # 后端服务代码
├── frontend/         # 前端页面和交互脚本
├── data/             # 本地运行数据
├── tests/            # 测试代码
├── .env.example      # 环境变量示例
├── .gitignore        # Git 忽略规则
├── main.py           # 项目入口
├── pyproject.toml    # Python 项目配置
└── README.md         # 项目说明
```

## 本地开发

复制环境变量示例文件：

```bash
cp .env.example .env
```

安装依赖：

```bash
uv sync
```

启动服务：

```bash
uvicorn backend.app:app --reload
```

访问地址：

- 前端页面：`http://127.0.0.1:8000/`
- API 文档：`http://127.0.0.1:8000/docs`

## 配置说明

主要环境变量见 `.env.example`，包括：

- 模型配置：`ARK_API_KEY`、`MODEL`、`FAST_MODEL`、`BASE_URL`
- 数据库配置：`DATABASE_URL`
- 缓存配置：`REDIS_URL`
- 鉴权配置：`JWT_SECRET_KEY`、`ADMIN_INVITE_CODE`
- Milvus 配置：`MILVUS_HOST`、`MILVUS_PORT`、`MILVUS_COLLECTION`
- 检索配置：`DENSE_EMBEDDING_DIM`、`BM25_STATE_PATH`
