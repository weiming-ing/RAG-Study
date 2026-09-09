import asyncio
import httpx
import sys
import os

BASE_URL = os.getenv("PYTHON_BACKEND_URL", "http://localhost:8001")
TEST_USERNAME = os.getenv("TEST_USERNAME", "testuser")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "test123456")
TEST_DISPLAY = "测试用户"

passed = 0
failed = 0
token = None
session_id = None


async def run():
    global passed, failed, token, session_id

    async def check(name, fn):
        global passed, failed
        try:
            await fn()
            passed += 1
            print(f"  [PASS] {name}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")

    print("=" * 60)
    print(" RAG Study 全功能测试")
    print("=" * 60)

    # ---- 1. 健康检查 ----
    print("\n[1] 基础功能")
    await check("健康检查", lambda: _health_check())

    # 确保服务就绪
    await asyncio.sleep(0.5)

    # ---- 2. 用户认证 ----
    print("\n[2] 用户认证")
    await check("注册", lambda: _register())
    await check("登录", lambda: _login())
    if token:
        await check("获取用户信息", lambda: _get_me())

    # ---- 3. 会话管理 ----
    print("\n[3] 会话管理")
    if token:
        await check("创建会话", lambda: _create_session())
    if token:
        await check("获取会话列表", lambda: _list_sessions())
    if token and session_id:
        await check("重命名会话", lambda: _rename_session())

    # ---- 4. 聊天功能 ----
    print("\n[4] 聊天功能")
    await check("游客聊天", lambda: _guest_chat())
    if token and session_id:
        await check("登录用户聊天", lambda: _user_chat())
    if token and session_id:
        await check("获取会话历史", lambda: _get_history())

    # ---- 5. 知识库功能 ----
    print("\n[5] 知识库功能")
    if token:
        await check("获取文档列表", lambda: _list_documents())
        await check("获取手动条目", lambda: _list_entries())
        await check("搜索知识库", lambda: _search_kb())

    # ---- 6. 清理 ----
    print("\n[6] 清理")
    if token and session_id:
        await check("删除会话", lambda: _delete_session())

    # ---- 结果 ----
    total = passed + failed
    print("\n" + "=" * 60)
    print(f" 测试结果: {passed}/{total} 通过, {failed}/{total} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


async def _health_check():
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{BASE_URL}/api/health")
                assert r.status_code == 200, f"status={r.status_code}"
                data = r.json()
                assert data.get("status") == "ok", f"body={r.text}"
                return
        except Exception as e:
            if attempt == 2:
                raise Exception(f"健康检查失败(尝试{attempt+1}/3): {e}")
            await asyncio.sleep(1)


async def _register():
    global token, session_id
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{BASE_URL}/api/auth/register", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "display_name": TEST_DISPLAY,
        })
        if r.status_code == 400 and "已存在" in r.text:
            print("  [INFO] 用户已存在，跳过注册")
            return
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        assert r.json().get("success"), f"body={r.text}"


async def _login():
    global token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        })
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        data = r.json()
        assert data.get("success"), f"body={r.text}"
        token = data["data"]["access_token"]
        assert token, "未获取到 token"


async def _get_me():
    global token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        data = r.json()
        assert data.get("success"), f"body={r.text}"
        assert data.get("data", {}).get("username") == TEST_USERNAME


async def _create_session():
    global token, session_id
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{BASE_URL}/api/sessions", json={
            "title": "测试会话",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        data = r.json()
        assert data.get("success"), f"body={r.text}"
        session_id = data["data"]["id"]
        assert session_id, "未获取到 session_id"


async def _list_sessions():
    global token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE_URL}/api/sessions", headers={
            "Authorization": f"Bearer {token}",
        })
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        data = r.json()
        assert data.get("success"), f"body={r.text}"
        assert len(data.get("data", [])) > 0, "会话列表为空"


async def _rename_session():
    global token, session_id
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.put(f"{BASE_URL}/api/sessions/{session_id}", json={
            "title": "重命名测试",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        assert r.json().get("success"), f"body={r.text}"


async def _guest_chat():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{BASE_URL}/api/chat/guest", json={
            "message": "你好",
        })
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
        has_token = any("token" in line for line in r.text.strip().split("\n"))
        assert has_token, "无 token 输出"


async def _user_chat():
    global token, session_id
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{BASE_URL}/api/chat", json={
            "session_id": session_id,
            "message": "你好，请介绍一下自己",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
        has_token = any("token" in line for line in r.text.strip().split("\n"))
        assert has_token, "无 token 输出"


async def _get_history():
    global token, session_id
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE_URL}/api/sessions/{session_id}/history", headers={
            "Authorization": f"Bearer {token}",
        })
        body = r.text
        assert r.status_code == 200, f"status={r.status_code} body={body}"
        data = r.json()
        assert data.get("success"), f"success=false body={body}"
        assert len(data.get("data", [])) > 0, f"data={data.get('data')}"


async def _list_documents():
    global token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE_URL}/api/knowledge/documents", headers={
            "Authorization": f"Bearer {token}",
        })
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        assert r.json().get("success"), f"body={r.text}"


async def _list_entries():
    global token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE_URL}/api/knowledge/manual", headers={
            "Authorization": f"Bearer {token}",
        })
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        assert r.json().get("success"), f"body={r.text}"


async def _search_kb():
    global token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE_URL}/api/knowledge/search", params={
            "q": "测试",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        assert r.json().get("success"), f"body={r.text}"


async def _delete_session():
    global token, session_id
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.delete(f"{BASE_URL}/api/sessions/{session_id}", headers={
            "Authorization": f"Bearer {token}",
        })
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        assert r.json().get("success"), f"body={r.text}"


if __name__ == "__main__":
    asyncio.run(run())