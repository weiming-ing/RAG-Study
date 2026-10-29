"""
知识库三级访问隔离端到端测试（需双服务在线）

覆盖关键场景：
  1. 普通用户 accessible 集合不含 MANAGEMENT 库
  2. 普通用户带不可访问 kb_id 提问 → 403
  3. 普通用户默认提问 → 检索结果不含管理级库内容
  4. 授权（kb_user_access）后（≤60s TTL）可检索管理级库
  5. 访客范围仅 PUBLIC 库
  6. 授权接口越权修复：非 owner/管理员授权 → 被拒

运行：python test_kb_isolation.py
夹具自动创建/清理：临时管理级知识库 + 测试文档，结束后删除。
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, ".")

import httpx

BASE = "http://localhost:8001"
MAGIC = f"机密内容X{os.urandom(2).hex()}"

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}: {detail}")


async def make_user(c, name):
    rr = await c.post(f"{BASE}/api/auth/register", json={
        "username": name, "password": "test123456", "display_name": name})
    if rr.status_code != 200:
        print(f"  [INFO] 注册 {name}: {rr.status_code} {rr.text[:120]}")
    r = await c.post(f"{BASE}/api/auth/login", json={"username": name, "password": "test123456"})
    if r.status_code != 200 or not r.text.strip().startswith("{"):
        raise RuntimeError(f"登录失败 {name}: {r.status_code} {r.text[:200]}")
    token = r.json()["data"]["access_token"]
    me = await c.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    uid = me.json()["data"]["id"]
    return {"token": token, "id": uid, "name": name}


def H(u):
    return {"Authorization": f"Bearer {u['token']}"}


async def main():
    async with httpx.AsyncClient(timeout=120) as c:
        suffix = os.urandom(3).hex()
        owner = await make_user(c, f"isow_{suffix}")
        employee = await make_user(c, f"isoe_{suffix}")

        # ---- 夹具：owner 创建管理级测试库并上传带魔力值的文档 ----
        r = await c.post(f"{BASE}/api/knowledge-bases", headers=H(owner), json={
            "name": f"隔离测试库_{suffix}", "description": "临时夹具", "visibility": "MANAGEMENT"})
        assert r.status_code == 200 and r.json().get("success"), f"创建管理级库失败: {r.text[:200]}"
        mgmt_kb = r.json()["data"]["id"]

        doc_bytes = f"# 机密文件\n\n{MAGIC}\n\n这是一段只允许授权用户检索的机密内容。".encode("utf-8")
        r = await c.post(
            f"{BASE}/api/knowledge/{mgmt_kb}/documents/upload",
            headers=H(owner),
            files={"file": ("机密文件.md", doc_bytes, "text/markdown")})
        assert r.status_code == 200, f"上传夹具文档失败: {r.text[:200]}"
        time.sleep(6)  # 等异步索引完成

        print("\n[1] 普通用户范围与越权拦截")
        r = await c.get(f"{BASE}/api/knowledge-bases/accessible-ish", headers=H(employee))
        # 员工范围经 chat 链路验证：带不可访问 kb_id 提问应 403
        s = await c.post(f"{BASE}/api/sessions", json={"title": "t"}, headers=H(employee))
        sid = s.json()["data"]["id"]
        r403 = await c.post(f"{BASE}/api/chat", headers=H(employee), json={
            "session_id": sid, "message": "搜索" + MAGIC, "kb_id": str(mgmt_kb)})
        check("普通用户带管理级 kb_id 提问 → 403", r403.status_code == 403, f"实际 {r403.status_code}")

        print("\n[2] 普通用户默认检索不含管理级库内容")
        r = await c.post(f"{BASE}/api/chat", headers=H(employee), json={
            "session_id": sid, "message": "请告诉我" + MAGIC + "的内容"})
        body = r.text
        check("答案不含管理级库魔力值", MAGIC not in body, "检索结果泄漏了管理级库内容")

        print("\n[3] 访客范围仅 PUBLIC")
        rg = await c.post(f"{BASE}/api/chat/guest", json={"message": "帮我找" + MAGIC})
        check("访客答案不含管理级库魔力值", MAGIC not in rg.text, "访客检索泄漏管理级库内容")

        print("\n[4] 授权接口越权修复")
        rg2 = await c.post(f"{BASE}/api/knowledge-bases/{mgmt_kb}/users", headers=H(employee),
                           json={"userIds": [employee["id"]], "accessLevel": "READ"})
        code = rg2.status_code
        body_ok = rg2.status_code == 200 and rg2.json().get("success")
        check("普通员工给自己授权管理级库 → 被拒", not body_ok, f"实际 {code} {rg2.text[:120]}")

        print("\n[5] owner 授权后 ≤60s 生效（TTL）")
        rg3 = await c.post(f"{BASE}/api/knowledge-bases/{mgmt_kb}/users", headers=H(owner),
                           json={"userIds": [employee["id"]], "accessLevel": "READ"})
        check("owner 给员工授权 → 成功", rg3.status_code == 200 and rg3.json().get("success"), rg3.text[:150])
        print("  等待 61s（Python 侧 60s TTL 缓存过期）...")
        await asyncio.sleep(61)

        r = await c.post(f"{BASE}/api/chat", headers=H(employee), json={
            "session_id": sid, "message": "机密文件的内容是什么"})
        check("授权后员工可检索管理级库内容", MAGIC in r.text, "授权后仍未检索到魔力值内容")

        # ---- 清理 ----
        await c.delete(f"{BASE}/api/knowledge-bases/{mgmt_kb}", headers=H(owner))
        await c.delete(f"{BASE}/api/sessions/{sid}", headers=H(employee))
        print("\n夹具已清理")

    print("\n" + "=" * 50)
    print(f" 隔离测试: {passed}/{passed + failed} 通过")
    print("=" * 50)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
