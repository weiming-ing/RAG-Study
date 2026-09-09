from agent.tool_registry import Tool, tool_registry
from agent.tools.base import _get_session_history, _search_knowledge
from agent.tools.web_search import _web_search
from agent.tools.code_interpreter import _code_execute
from agent.tools.file_parser import _file_read, _file_list
from agent.tools.image_tools import _image_generate, _image_analyze
from agent.tools.api_integration import _http_request


def register_all_tools():
    tool_registry.register(Tool(
        name="web_search",
        description="搜索互联网获取实时信息。当需要查询最新新闻、实时数据、百科知识等不在知识库中的信息时使用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，使用简洁的关键词组合",
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认 5",
                },
            },
            "required": ["query"],
        },
        handler=_web_search,
    ))

    tool_registry.register(Tool(
        name="code_execute",
        description="执行 Python 代码进行数据分析、计算、绘图等。支持 math、statistics、json、datetime、collections、itertools、random 等标准库。",
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码",
                },
                "language": {
                    "type": "string",
                    "description": "编程语言，目前仅支持 python",
                    "enum": ["python"],
                },
            },
            "required": ["code"],
        },
        handler=_code_execute,
    ))

    tool_registry.register(Tool(
        name="file_read",
        description="读取知识库中指定文档的完整内容（分块拼接）。传入文档ID或文档名称即可获取全文。",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文档ID（数字）或文档名称。可先用 file_list 查看可用文档列表获取ID。",
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码，默认 utf-8",
                },
            },
            "required": ["file_path"],
        },
        handler=_file_read,
    ))

    tool_registry.register(Tool(
        name="file_list",
        description="列出知识库中所有已上传的文档。返回文档ID、名称、大小、类型、所属知识库、状态等信息。",
        parameters={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "按部门筛选文档，留空则列出全部",
                },
            },
            "required": [],
        },
        handler=_file_list,
    ))

    tool_registry.register(Tool(
        name="image_generate",
        description="根据文字描述生成图片（需要配置图片生成 API）。",
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "图片描述文字",
                },
                "size": {
                    "type": "string",
                    "description": "图片尺寸，如 512x512、1024x1024",
                },
            },
            "required": ["prompt"],
        },
        handler=_image_generate,
    ))

    tool_registry.register(Tool(
        name="image_analyze",
        description="分析图片文件的基本信息（格式、尺寸等）。",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "图片文件路径",
                },
                "question": {
                    "type": "string",
                    "description": "关于图片的具体问题（可选）",
                },
            },
            "required": ["file_path"],
        },
        handler=_image_analyze,
    ))

    tool_registry.register(Tool(
        name="http_request",
        description="发送 HTTP 请求调用外部 API 接口。支持 GET、POST、PUT、DELETE、PATCH 方法。",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "请求的完整 URL",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP 方法",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                },
                "headers": {
                    "type": "string",
                    "description": "请求头，JSON 格式字符串，如 {\"Authorization\": \"Bearer xxx\"}",
                },
                "body": {
                    "type": "string",
                    "description": "请求体，JSON 格式字符串",
                },
                "timeout": {
                    "type": "number",
                    "description": "超时时间（秒），默认 30",
                },
            },
            "required": ["url"],
        },
        handler=_http_request,
    ))

    tool_registry.register(Tool(
        name="search_knowledge",
        description="搜索企业内部知识库获取相关文档内容。当用户询问公司制度、流程、规范、操作手册等企业内部知识时使用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题，使用简洁的关键词组合",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认 5",
                },
            },
            "required": ["query"],
        },
        handler=_search_knowledge,
    ))

    tool_registry.register(Tool(
        name="get_session_history",
        description="获取当前会话的对话历史，用于理解上下文中的指代关系。",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "当前会话ID",
                },
            },
            "required": ["session_id"],
        },
        handler=_get_session_history,
    ))

    print(f"[TOOLS] 已注册 {len(tool_registry._tools)} 个工具: {list(tool_registry._tools.keys())}")


register_all_tools()