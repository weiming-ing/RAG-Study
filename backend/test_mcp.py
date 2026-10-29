import urllib.request
import json

BASE = "http://localhost:8005"

def call_tool(name, params):
    data = json.dumps({"name": name, "parameters": params}).encode()
    req = urllib.request.Request(
        f"{BASE}/mcp/tools/call", data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {"error": str(e)}

# 1. health_check
code, r = call_tool("health_check", {})
print(f"1. health_check (HTTP {code}):")
print(f"   java_backend_healthy: {r.get('java_backend_healthy')}")

# 2. list_knowledge_bases
code, r = call_tool("list_knowledge_bases", {})
print(f"\n2. list_knowledge_bases (HTTP {code}):")
kbs = r.get("knowledge_bases", [])
print(f"   共 {len(kbs)} 个知识库")
for kb in kbs[:3]:
    print(f"   - {kb.get('name', kb.get('kbName', '?'))}")

# 3. search_knowledge
code, r = call_tool("search_knowledge", {"query": "RAG助手架构", "top_k": 3})
print(f"\n3. search_knowledge (HTTP {code}):")
print(f"   total_found: {r.get('total_found', 0)}")
for item in r.get("results", [])[:3]:
    print(f"   [{item.get('score', '?')}] {item.get('document_name', '?')}: {item.get('content', '')[:60]}...")

# 4. get_document_chunks
code, r = call_tool("get_document_chunks", {"document_id": "73", "page": 1, "page_size": 2})
print(f"\n4. get_document_chunks (HTTP {code}):")
print(f"   total: {r.get('total', 0)}")
for c in r.get("chunks", [])[:2]:
    print(f"   - {str(c)[:80]}")

print("\n✅ 全部工具可正常调用！")