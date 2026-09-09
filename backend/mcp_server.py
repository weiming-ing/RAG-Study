#!/usr/bin/env python
"""
RAG 助手 MCP Server
===================
将 RAG 检索能力通过 MCP (Model Context Protocol) 协议暴露出去，
让 Claude Desktop、Cursor 等支持 MCP 的 AI 客户端可以直接调用。

完全独立，不修改原有业务代码。
"""

import json
import asyncio
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from config import (
    JAVA_BACKEND_URL,
    TOP_K,
    SIMILARITY_THRESHOLD,
    USE_HYBRID_SEARCH,
)

# MCP 协议版本
MCP_VERSION = "1.0.0"
SERVICE_NAME = "rag-assistant"
SERVICE_VERSION = "1.0.0"


class RAGMCPTools:
    """RAG MCP 工具集合，定义可被外部调用的工具"""

    def __init__(self):
        self.java_backend_url = JAVA_BACKEND_URL
        self.timeout = 15.0

    async def search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        在企业知识库中进行语义搜索，返回与查询最相关的文档片段。

        Args:
            query: 搜索查询文本
            top_k: 返回最大结果数，默认 5
            threshold: 相似度阈值，低于此阈值的结果会被过滤，默认使用配置值

        Returns:
            搜索结果列表，包含内容、文档名、相关度分数
        """
        if threshold is None:
            threshold = SIMILARITY_THRESHOLD

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.java_backend_url}/api/internal/search",
                    json={
                        "query": query,
                        "topK": top_k,
                        "enableHybrid": USE_HYBRID_SEARCH,
                        "filters": {},
                    },
                )
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Java 后端调用失败: HTTP {resp.status_code}",
                        "results": [],
                    }

                data = resp.json()
                if not data.get("success"):
                    return {
                        "success": False,
                        "error": data.get("error", "未知错误"),
                        "results": [],
                    }

                search_data = data.get("data", {})
                raw_results = search_data.get("results", [])

                # 过滤并格式化结果
                results = []
                for r in raw_results:
                    score = r.get("score", 0)
                    if score < threshold:
                        continue
                    metadata = r.get("metadata", {})
                    results.append({
                        "content": r.get("content", ""),
                        "document_name": metadata.get("docName", metadata.get("filename", "未知文档")),
                        "document_id": metadata.get("documentId", ""),
                        "chunk_index": metadata.get("chunkIndex", 0),
                        "score": round(score, 4),
                    })

                return {
                    "success": True,
                    "query": query,
                    "total_found": len(results),
                    "results": results,
                }

        except Exception as e:
            error_msg = str(e)
            if "All connection attempts failed" in error_msg or "无法连接" in error_msg or "Connection refused" in error_msg:
                error_msg = (
                    f"无法连接到 Java 后端 ({self.java_backend_url})，请确保 Java 后端已启动。"
                    "搜索功能需要 Java 后端提供检索服务。"
                    f"原始错误: {e}"
                )
            return {
                "success": False,
                "error": error_msg,
                "results": [],
            }

    async def list_knowledge_bases(self) -> Dict[str, Any]:
        """
        获取所有可用的知识库列表。

        Returns:
            知识库列表，包含 ID、名称、描述等信息
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.java_backend_url}/api/knowledge-bases/list")
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "error": f"获取知识库列表失败: HTTP {resp.status_code}",
                        "knowledge_bases": [],
                    }

                data = resp.json()
                if not data.get("success"):
                    return {
                        "success": False,
                        "error": data.get("error", "未知错误"),
                        "knowledge_bases": [],
                    }

                return {
                    "success": True,
                    "knowledge_bases": data.get("data", []),
                }

        except Exception as e:
            error_msg = str(e)
            if "All connection attempts failed" in error_msg or "无法连接" in error_msg or "Connection refused" in error_msg:
                error_msg = (
                    f"无法连接到 Java 后端 ({self.java_backend_url})，请确保 Java 后端已启动。"
                    f"原始错误: {e}"
                )
            return {
                "success": False,
                "error": error_msg,
                "knowledge_bases": [],
            }

    async def get_document_chunks(
        self,
        document_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        获取指定文档的所有切片。

        Args:
            document_id: 文档 ID
            page: 页码，从 1 开始
            page_size: 每页数量

        Returns:
            文档切片列表
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.java_backend_url}/api/chunks/list",
                    params={
                        "documentId": document_id,
                        "pageNum": page,
                        "pageSize": page_size,
                    },
                )
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "error": f"获取文档切片失败: HTTP {resp.status_code}",
                        "chunks": [],
                    }

                data = resp.json()
                if not data.get("success"):
                    return {
                        "success": False,
                        "error": data.get("error", "未知错误"),
                        "chunks": [],
                    }

                return {
                    "success": True,
                    "document_id": document_id,
                    "total": data.get("total", 0),
                    "page": page,
                    "chunks": data.get("data", []),
                }

        except Exception as e:
            error_msg = str(e)
            if "All connection attempts failed" in error_msg or "无法连接" in error_msg or "Connection refused" in error_msg:
                error_msg = (
                    f"无法连接到 Java 后端 ({self.java_backend_url})，请确保 Java 后端已启动。"
                    f"原始错误: {e}"
                )
            return {
                "success": False,
                "error": error_msg,
                "chunks": [],
            }

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查，检查服务和 Java 后端是否正常运行。

        Returns:
            健康状态信息
        """
        java_healthy = False
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.java_backend_url}/api/internal/health")
                java_healthy = resp.status_code == 200
        except Exception:
            pass

        return {
            "success": True,
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "mcp_version": MCP_VERSION,
            "java_backend_healthy": java_healthy,
        }


# 定义工具元数据（符合 MCP 规范）
TOOL_DEFINITIONS = [
    {
        "name": "search_knowledge",
        "description": "在企业知识库中进行语义搜索，返回与查询最相关的文档片段。当用户询问企业内部知识、文档内容、业务规则时使用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询文本，描述你要找什么内容",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回最大结果数，默认 5",
                    "default": 5,
                },
                "threshold": {
                    "type": "number",
                    "description": "相似度阈值（0-1），低于此阈值的结果会被过滤，默认使用系统配置值",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_knowledge_bases",
        "description": "获取所有可用的知识库列表，查看当前系统中有哪些知识库可以查询。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_document_chunks",
        "description": "获取指定文档的所有切片内容，完整阅读某篇文档。",
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "文档 ID",
                },
                "page": {
                    "type": "integer",
                    "description": "页码，从 1 开始，默认 1",
                    "default": 1,
                },
                "page_size": {
                    "type": "integer",
                    "description": "每页返回多少切片，默认 20",
                    "default": 20,
                },
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "health_check",
        "description": "检查 RAG MCP 服务和 Java 后端是否健康运行。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[MCP] RAG MCP Server 启动 - 版本 {SERVICE_VERSION} (MCP {MCP_VERSION})")
    print(f"[MCP] Java 后端地址: {JAVA_BACKEND_URL}")
    yield
    print("[MCP] RAG MCP Server 停止")


app = FastAPI(
    title="RAG 助手 MCP Server",
    description="将 RAG 知识库检索能力通过 MCP 协议暴露给 AI 客户端",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_tools = RAGMCPTools()


@app.get("/", response_class=HTMLResponse)
async def root():
    """首页 - 展示 MCP Server 概览信息"""
    health = await rag_tools.health_check()
    java_ok = health.get("java_backend_healthy", False)
    status_text = "运行正常" if java_ok else "降级运行"
    status_class = "status-ok" if java_ok else "status-warn"
    java_text = "已连接" if java_ok else "未连接"
    java_class = "status-ok" if java_ok else "status-err"

    tools_html = ""
    for i, t in enumerate(TOOL_DEFINITIONS, 1):
        desc = t["description"]
        params = t.get("parameters", {}).get("properties", {})
        required = t.get("parameters", {}).get("required", [])
        params_html = ""
        for pname, pinfo in params.items():
            req = "required" if pname in required else "optional"
            default_val = pinfo.get("default", "")
            default_str = f" (默认: {default_val})" if default_val != "" else ""
            params_html += f"""
                    <div class="param-row">
                        <span class="param-name">{pname}</span>
                        <span class="param-type">{pinfo.get('type', 'string')}</span>
                        <span class="param-req {req}">{req}</span>
                        <span class="param-desc">{pinfo.get('description', '')}{default_str}</span>
                    </div>"""

        tools_html += f"""
            <div class="tool-card" onclick="toggleTool('tool-{i}')">
                <div class="tool-header">
                    <div class="tool-icon">{i}</div>
                    <div class="tool-info">
                        <h3>{t["name"]}</h3>
                        <p>{desc}</p>
                    </div>
                    <div class="tool-expand">▾</div>
                </div>
                <div class="tool-details" id="tool-{i}">
                    <div class="params-section">
                        <h4>参数</h4>
                        {params_html if params_html else '<div class="param-row"><span class="param-desc">无参数</span></div>'}
                    </div>
                    <div class="tool-example">
                        <h4>调用示例</h4>
                        <pre>{json.dumps({"name": t["name"], "parameters": {p: (pinfo.get("example", "")) for p, pinfo in params.items() if p in required}}, indent=2, ensure_ascii=False)}</pre>
                    </div>
                </div>
            </div>"""

    doc_html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RAG 助手 · MCP Server</title>
        <style>
            :root {{
                --color-bg: #ffffff;
                --color-surface: #f9fafb;
                --color-hover: #f3f4f6;
                --color-active: #e5e7eb;
                --color-text: #111827;
                --color-text-secondary: #6b7280;
                --color-text-tertiary: #9ca3af;
                --color-border: #e5e7eb;
                --color-border-light: #f3f4f6;
                --accent: #2563eb;
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif;
                background: var(--color-bg);
                color: var(--color-text);
                line-height: 1.6;
                -webkit-font-smoothing: antialiased;
            }}
            .container {{ max-width: 720px; margin: 0 auto; padding: 48px 24px; }}

            /* Header */
            header {{ padding: 32px 0 40px; border-bottom: 1px solid var(--color-border); }}
            .logo {{ display: flex; align-items: center; gap: 12px; }}
            .logo-icon {{
                width: 40px; height: 40px;
                background: var(--color-text);
                border-radius: 6px;
                display: flex; align-items: center; justify-content: center;
                font-size: 18px; font-weight: 600;
                color: var(--color-bg);
                flex-shrink: 0;
            }}
            .logo-text h1 {{ font-size: 20px; font-weight: 600; color: var(--color-text); }}
            .logo-text span {{ font-size: 13px; color: var(--color-text-tertiary); }}
            header p {{ font-size: 15px; color: var(--color-text-secondary); margin-top: 8px; }}

            /* Status Bar */
            .status-bar {{ display: flex; gap: 8px; margin-top: 20px; flex-wrap: wrap; }}
            .status-item {{
                display: flex; align-items: center; gap: 8px;
                padding: 8px 12px;
                background: var(--color-surface);
                border: 1px solid var(--color-border);
                border-radius: 6px;
                font-size: 13px;
            }}
            .status-dot {{ width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }}
            .status-ok {{ background: var(--color-text); }}
            .status-warn {{ background: var(--color-text-tertiary); }}
            .status-err {{ background: var(--color-text-tertiary); }}
            .status-label {{ color: var(--color-text-tertiary); }}
            .status-value {{ color: var(--color-text); font-weight: 500; }}

            /* Section */
            section {{ margin-top: 40px; }}
            .section-title {{
                font-size: 13px; font-weight: 600;
                color: var(--color-text-tertiary);
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 12px;
            }}

            /* Endpoints */
            .endpoint-list {{ display: flex; flex-direction: column; gap: 4px; }}
            .endpoint-row {{
                display: flex; align-items: center; gap: 12px;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 13px;
                transition: background 0.15s;
            }}
            .endpoint-row:hover {{ background: var(--color-hover); }}
            .endpoint-method {{
                display: inline-block;
                font-size: 11px; font-weight: 600;
                padding: 1px 6px;
                border-radius: 4px;
                min-width: 36px;
                text-align: center;
            }}
            .method-get {{ background: var(--color-surface); color: var(--color-text-secondary); border: 1px solid var(--color-border); }}
            .method-post {{ background: var(--color-surface); color: var(--color-text-secondary); border: 1px solid var(--color-border); }}
            .endpoint-path {{
                font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
                font-size: 13px;
                color: var(--color-text);
                font-weight: 500;
                min-width: 120px;
            }}
            .endpoint-desc {{ color: var(--color-text-secondary); flex: 1; }}

            /* Tool Cards */
            .tool-card {{
                border: 1px solid var(--color-border);
                border-radius: 6px;
                margin-bottom: 6px;
                overflow: hidden;
                cursor: pointer;
                transition: border-color 0.15s;
            }}
            .tool-card:hover {{ border-color: var(--color-text-tertiary); }}
            .tool-header {{
                display: flex; align-items: flex-start; gap: 12px;
                padding: 14px 16px;
            }}
            .tool-icon {{
                font-family: 'SF Mono', 'Fira Code', monospace;
                font-size: 11px; font-weight: 600;
                color: var(--color-text-tertiary);
                line-height: 20px;
                flex-shrink: 0;
                min-width: 20px;
            }}
            .tool-info {{ flex: 1; min-width: 0; }}
            .tool-info h3 {{
                font-size: 15px; font-weight: 600;
                color: var(--color-text);
                font-family: 'SF Mono', 'Fira Code', monospace;
            }}
            .tool-info p {{
                font-size: 13px;
                color: var(--color-text-secondary);
                margin-top: 2px;
                line-height: 1.5;
            }}
            .tool-expand {{
                font-size: 12px;
                color: var(--color-text-tertiary);
                transition: transform 0.15s;
                flex-shrink: 0;
                line-height: 22px;
            }}
            .tool-details {{
                display: none;
                padding: 0 16px 16px;
                border-top: 1px solid var(--color-border-light);
            }}
            .tool-details.active {{ display: block; }}
            .tool-details h4 {{
                font-size: 11px; font-weight: 600;
                color: var(--color-text-tertiary);
                margin: 12px 0 6px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .param-row {{
                display: flex; align-items: baseline; gap: 8px;
                padding: 4px 0;
                font-size: 13px;
                border-bottom: 1px solid var(--color-border-light);
            }}
            .param-row:last-child {{ border-bottom: none; }}
            .param-name {{
                font-family: 'SF Mono', 'Fira Code', monospace;
                color: var(--color-text);
                font-weight: 500;
                min-width: 100px;
                font-size: 12px;
            }}
            .param-type {{
                color: var(--color-text-tertiary);
                font-size: 11px;
                min-width: 48px;
            }}
            .param-req {{
                font-size: 10px;
                padding: 0 6px;
                border-radius: 3px;
                min-width: 40px;
                text-align: center;
                border: 1px solid var(--color-border);
            }}
            .param-req.required {{ color: var(--color-text-secondary); border-color: var(--color-border); }}
            .param-req.optional {{ color: var(--color-text-tertiary); }}
            .param-desc {{ color: var(--color-text-secondary); flex: 1; font-size: 12px; }}
            .tool-example pre {{
                background: var(--color-surface);
                border: 1px solid var(--color-border);
                border-radius: 6px;
                padding: 12px 14px;
                font-size: 12px;
                font-family: 'SF Mono', 'Fira Code', monospace;
                color: var(--color-text-secondary);
                overflow-x: auto;
                margin-top: 6px;
                line-height: 1.5;
            }}

            /* Footer */
            footer {{
                margin-top: 48px;
                padding: 20px 0 0;
                border-top: 1px solid var(--color-border);
                color: var(--color-text-tertiary);
                font-size: 13px;
                text-align: center;
            }}

            /* Responsive */
            @media (max-width: 640px) {{
                .container {{ padding: 32px 16px; }}
                header {{ padding: 24px 0 32px; }}
                .logo-text h1 {{ font-size: 18px; }}
                .tool-header {{ padding: 12px 14px; }}
                .tool-details {{ padding: 0 14px 14px; }}
                .param-row {{ flex-wrap: wrap; gap: 2px; }}
                .param-name {{ min-width: 80px; }}
                .endpoint-path {{ min-width: 100px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="logo">
                    <div class="logo-icon">R</div>
                    <div class="logo-text">
                        <h1>RAG Assistant MCP</h1>
                        <span>v{SERVICE_VERSION} · {SERVICE_NAME}</span>
                    </div>
                </div>
                <p>将企业内部知识库检索能力通过 MCP 协议暴露给 AI 客户端</p>

                <div class="status-bar">
                    <div class="status-item">
                        <div class="status-dot {status_class}"></div>
                        <span class="status-label">服务</span>
                        <span class="status-value">{status_text}</span>
                    </div>
                    <div class="status-item">
                        <div class="status-dot {java_class}"></div>
                        <span class="status-label">Java</span>
                        <span class="status-value">{java_text}</span>
                    </div>
                    <div class="status-item">
                        <span class="status-value">{len(TOOL_DEFINITIONS)}</span>
                        <span class="status-label">工具</span>
                    </div>
                </div>
            </header>

            <section>
                <div class="section-title">Endpoints</div>
                <div class="endpoint-list">
                    <div class="endpoint-row">
                        <span class="endpoint-method method-get">GET</span>
                        <span class="endpoint-path">/</span>
                        <span class="endpoint-desc">首页概览</span>
                    </div>
                    <div class="endpoint-row">
                        <span class="endpoint-method method-get">GET</span>
                        <span class="endpoint-path">/health</span>
                        <span class="endpoint-desc">健康检查</span>
                    </div>
                    <div class="endpoint-row">
                        <span class="endpoint-method method-get">GET</span>
                        <span class="endpoint-path">/mcp/info</span>
                        <span class="endpoint-desc">服务信息与工具定义</span>
                    </div>
                    <div class="endpoint-row">
                        <span class="endpoint-method method-get">GET</span>
                        <span class="endpoint-path">/mcp/tools/list</span>
                        <span class="endpoint-desc">列出所有工具</span>
                    </div>
                    <div class="endpoint-row">
                        <span class="endpoint-method method-post">POST</span>
                        <span class="endpoint-path">/mcp/tools/call</span>
                        <span class="endpoint-desc">调用工具</span>
                    </div>
                </div>
            </section>

            <section>
                <div class="section-title">Tools</div>
                {tools_html}
            </section>

            <footer>RAG Assistant · FastAPI · MCP Protocol</footer>
        </div>

        <script>
            function toggleTool(id) {{
                var el = document.getElementById(id);
                el.classList.toggle('active');
                var expand = el.parentElement.querySelector('.tool-expand');
                expand.style.transform = el.classList.contains('active') ? 'rotate(180deg)' : 'rotate(0deg)';
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=doc_html)


@app.get("/mcp/info")
async def get_server_info():
    """获取 MCP 服务器信息"""
    return {
        "success": True,
        "name": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "mcp_version": MCP_VERSION,
        "description": "RAG 知识库检索 MCP 服务器，提供企业内部知识查询能力",
        "tools": TOOL_DEFINITIONS,
    }


@app.post("/mcp/tools/call")
async def call_tool(data: Dict[str, Any]):
    """
    MCP 工具调用入口

    Request format:
    {
        "name": "tool_name",
        "parameters": {}
    }
    """
    tool_name = data.get("name")
    parameters = data.get("parameters", {})

    if not tool_name:
        return {"success": False, "error": "缺少工具名称 'name' 参数"}

    tool_map = {
        "search_knowledge": rag_tools.search_knowledge,
        "list_knowledge_bases": rag_tools.list_knowledge_bases,
        "get_document_chunks": rag_tools.get_document_chunks,
        "health_check": rag_tools.health_check,
    }

    if tool_name not in tool_map:
        available = ", ".join(tool_map.keys())
        return {"success": False, "error": f"工具 '{tool_name}' 不存在。可用工具: {available}"}

    try:
        result = await tool_map[tool_name](**parameters)
        return result
    except TypeError as e:
        return {"success": False, "error": f"参数错误: {e}"}
    except Exception as e:
        return {"success": False, "error": f"执行失败: {e}"}


@app.get("/mcp/tools/list")
async def list_tools():
    """列出所有可用工具"""
    return {
        "success": True,
        "tools": TOOL_DEFINITIONS,
    }


@app.get("/health")
async def health():
    """健康检查"""
    return await rag_tools.health_check()


if __name__ == "__main__":
    import uvicorn
    # MCP Server 默认运行在 8003 端口，避免与原有服务冲突
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=8003, reload=True)