# 系统架构设计文档

## 1. 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    前端 (HTML/CSS/JS)                │
│             聊天界面 + 知识库管理 + 会话管理           │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP/SSE
┌─────────────────────▼───────────────────────────────┐
│                  FastAPI 后端                         │
│  ┌───────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ 知识库模块 │ │ RAG检索  │ │  LLM 生成模块    │   │
│  │ - 文档解析 │ │ - 向量化 │ │ - Prompt 构建    │   │
│  │ - 文本分块 │ │ - 相似度 │ │ - 上下文注入     │   │
│  │ - 向量存储 │ │   检索   │ │ - 流式输出       │   │
│  └─────┬─────┘ └────┬─────┘ └────────┬─────────┘   │
│        │            │               │               │
│  ┌─────▼────────────▼───────────────▼──────────┐    │
│  │              会话管理模块                      │    │
│  │         SQLite 存储会话和聊天历史               │    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                    数据层                             │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │   ChromaDB   │  │    SQLite    │                 │
│  │  (向量存储)   │  │  (会话/历史)  │                 │
│  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘
```

## 2. 技术选型

| 层次 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI + Uvicorn | 高性能异步框架，支持 SSE |
| 文档解析 | LangChain Document Loaders | 支持 PDF/TXT/MD/DOCX |
| 文本分块 | LangChain Text Splitters | 递归字符分割 |
| Embedding | sentence-transformers (BGE) | 本地部署，中文效果好 |
| 向量数据库 | ChromaDB | 轻量级，嵌入式运行 |
| LLM | Ollama (qwen2.5) | 本地部署，中文能力强 |
| 会话存储 | SQLite + aiosqlite | 轻量级关系数据库 |
| 前端 | 原生 HTML/CSS/JS | 无框架依赖，简单部署 |

## 3. API 接口设计

### 3.1 知识库管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/knowledge/upload | 上传文档 |
| GET  | /api/knowledge/documents | 获取文档列表 |
| DELETE | /api/knowledge/documents/{id} | 删除文档 |
| POST | /api/knowledge/rebuild | 重建知识库 |

### 3.2 智能问答
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/chat | 发送消息（SSE 流式） |
| POST | /api/chat/stream | 流式聊天（SSE） |

### 3.3 会话管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | /api/sessions | 获取会话列表 |
| POST | /api/sessions | 创建新会话 |
| DELETE | /api/sessions/{id} | 删除会话 |
| GET  | /api/sessions/{id}/history | 获取会话历史 |

## 4. 数据库设计

### 4.1 SQLite 表结构

```sql
-- 会话表
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT DEFAULT '新对话',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 消息表
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources TEXT,  -- JSON 格式的引用来源
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

### 4.2 ChromaDB Collection
- Collection 名称: `knowledge_base`
- 存储内容: 文档分块的 embedding 向量 + 元数据（文档名、页码、chunk_id）