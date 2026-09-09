import httpx
from config import JAVA_BACKEND_URL

JAVA_TIMEOUT = 15.0
FILE_MAX_CHARS = 10000


async def _file_list(directory: str = "") -> str:
    params = {"pageSize": 100}
    if directory:
        params["department"] = directory

    try:
        async with httpx.AsyncClient(timeout=JAVA_TIMEOUT) as client:
            resp = await client.get(
                f"{JAVA_BACKEND_URL}/api/internal/knowledge/list",
                params=params,
            )
            if resp.status_code != 200:
                return f"无法获取知识库文档列表（HTTP {resp.status_code}）"

            data = resp.json()
            if data.get("code") != 0:
                return f"获取文档列表失败: {data.get('message', '未知错误')}"

            page_data = data.get("data", {})
            records = page_data.get("records", [])

            if not records:
                return "知识库中暂无文档。"

            lines = [f"知识库文档列表（共 {len(records)} 个文档）:"]
            for doc in records:
                doc_id = doc.get("id", "")
                name = doc.get("name", doc.get("fileName", "未知"))
                file_type = doc.get("fileType", "")
                file_size = doc.get("fileSize", 0)
                status = doc.get("status", "unknown")
                kb_name = doc.get("kbName", doc.get("knowledgeBaseName", ""))

                if file_size < 1024:
                    size_str = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.1f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.1f} MB"

                meta_parts = []
                if kb_name:
                    meta_parts.append(f"知识库: {kb_name}")
                if file_type:
                    meta_parts.append(f"类型: {file_type}")
                meta_parts.append(f"大小: {size_str}")
                meta_parts.append(f"状态: {status}")
                meta = " | ".join(meta_parts)

                lines.append(f"  [{doc_id}] {name} ({meta})")

            return "\n".join(lines)

    except httpx.ConnectError:
        return "无法连接到知识库后端服务，请确认 Java 后端已启动。"
    except Exception as e:
        return f"获取文档列表失败: {e}"


async def _file_read(file_path: str, encoding: str = "utf-8") -> str:
    doc_id = None

    try:
        int(file_path)
        doc_id = file_path
    except ValueError:
        pass

    if doc_id is None:
        doc_id = await _resolve_document_id(file_path)

    if doc_id is None:
        return f"文档未找到: {file_path}\n提示: 请使用 file_list 查看可用文档列表，或使用 search_knowledge 搜索文档内容。"

    try:
        async with httpx.AsyncClient(timeout=JAVA_TIMEOUT) as client:
            resp = await client.get(
                f"{JAVA_BACKEND_URL}/api/internal/knowledge/{doc_id}",
            )
            if resp.status_code != 200:
                return f"无法获取文档 {doc_id} 的信息（HTTP {resp.status_code}）"

            data = resp.json()
            if data.get("code") != 0:
                return f"获取文档 {doc_id} 失败: {data.get('message', '未知错误')}"

            doc_info = data.get("data", {})
            doc_name = doc_info.get("name", doc_info.get("fileName", "未知"))

    except Exception:
        return f"无法获取文档 {doc_id} 的信息。"

    try:
        async with httpx.AsyncClient(timeout=JAVA_TIMEOUT) as client:
            resp = await client.get(
                f"{JAVA_BACKEND_URL}/api/internal/knowledge/chunks/{doc_id}",
            )
            if resp.status_code != 200:
                return f"无法获取文档 {doc_id} 的内容分块（HTTP {resp.status_code}）"

            data = resp.json()
            if data.get("code") != 0:
                return f"获取文档 {doc_id} 内容失败: {data.get('message', '未知错误')}"

            chunks = data.get("data", [])
            if not chunks:
                return f"文档 [{doc_id}] {doc_name} 无内容。"

            lines = []
            for chunk in chunks:
                chunk_index = chunk.get("chunkIndex", "")
                content = chunk.get("content", "")
                lines.append(f"--- 分块 {chunk_index} ---")
                lines.append(content)

            full_content = "\n".join(lines)
            return _format_content(full_content, doc_name, doc_id)

    except httpx.ConnectError:
        return "无法连接到知识库后端服务，请确认 Java 后端已启动。"
    except Exception as e:
        return f"读取文档失败: {e}"


async def _resolve_document_id(name: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=JAVA_TIMEOUT) as client:
            resp = await client.get(
                f"{JAVA_BACKEND_URL}/api/internal/knowledge/list",
                params={"pageSize": 500},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            if data.get("code") != 0:
                return None

            records = data.get("data", {}).get("records", [])
            name_lower = name.lower().strip()

            for doc in records:
                doc_name = (doc.get("name") or doc.get("fileName") or "").lower()
                doc_id = str(doc.get("id", ""))
                if doc_name == name_lower or name_lower in doc_name:
                    return doc_id

            return None

    except Exception:
        return None


def _format_content(content: str, filename: str, doc_id: str = "") -> str:
    header = f"文档: {filename}"
    if doc_id:
        header += f" (ID: {doc_id})"
    if len(content) > FILE_MAX_CHARS:
        content = content[:FILE_MAX_CHARS] + f"\n\n... (内容过长，已截断至 {FILE_MAX_CHARS} 字符)"
    return f"{header}\n{'=' * 40}\n{content}"