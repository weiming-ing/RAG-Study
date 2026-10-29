import json
import uuid
import os
from datetime import datetime
from typing import List, Optional
import httpx
from database.db import get_redis, get_db
from config import SESSION_TTL

REDIS_AVAILABLE = False
REDIS_ERROR = ""
JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")


async def check_redis():
    """探测 Redis 可用性，结果落 REDIS_AVAILABLE/REDIS_ERROR 供日志与 /api/health 使用。

    注意必须如实暴露失败原因：此前此函数吞掉异常后 lifespan 仍打印
    "Redis 连接成功"，导致应用在 SQLite 降级模式下长期运行且无告警。
    """
    global REDIS_AVAILABLE, REDIS_ERROR
    try:
        r = await get_redis()
        await r.ping()
        REDIS_AVAILABLE = True
        REDIS_ERROR = ""
        try:
            info = await r.info("server")
            version = str(info.get("redis_version", ""))
            if version and int(version.split(".")[0]) < 4:
                print(f"[WARNING] Redis 版本 {version} 过低（建议 7.x）：多字段 HSET 等语法不可用，"
                      f"旧版本已通过逐字段写入兼容，但生产环境建议升级")
        except Exception:
            pass
    except Exception as e:
        REDIS_AVAILABLE = False
        REDIS_ERROR = str(e)


async def _hset_all(r, key: str, mapping: dict, pipe=None):
    """逐字段 HSET：多字段 HSET key f v f v... 语法是 Redis 4.0+ 才有的，
    本地开发常见的老版本 Redis（如 3.2）会报 wrong number of arguments；
    逐字段写对新旧版本均兼容。pipe 传入时写入管道。"""
    target = pipe if pipe is not None else r
    for field, value in mapping.items():
        await target.hset(key, field, "" if value is None else value)


class SessionService:
    """
    会话管理服务

    核心职责：管理对话会话的生命周期，支持 Redis + MySQL 双存储。

    存储策略：
      - 优先 Redis：高性能缓存，TTL=7天，适合生产环境
      - 降级 SQLite：Redis 不可用时自动切换本地存储
      - MySQL 兜底：Redis TTL 过期后，从 conversation_log 表回源加载历史记录

    数据模型：
      - sessions: 会话元数据（id, title, user_id, created_at, updated_at）
      - messages: 消息记录（session_id, role, content, sources, created_at）
      - conversation_log (MySQL): 每条 Q&A 的持久化记录

    主要操作：
      - create_session: 创建新会话（UUID 16位 hex）
      - get_sessions: 获取会话列表（Redis + MySQL 回源）
      - get_history: 获取会话历史消息（Redis + MySQL 回源）
      - add_message: 添加消息（user/assistant），更新会话时间
      - update_title: 自动更新标题（仅首次）
      - delete_session: 删除会话及关联消息
    """

    async def _call_java(self, path: str, token: str = "", timeout: float = 10.0) -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{JAVA_BACKEND}{path}", headers=headers)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            print(f"[session_service] Java 后端调用失败: {e}")
        return {}

    async def _mysql_get_history(self, session_id: str, token: str = "") -> List[dict]:
        result = await self._call_java(
            f"/api/conversations?sessionId={session_id}&pageSize=500&sortOrder=asc",
            token=token,
        )
        if not result or result.get("code") != 0:
            return []

        data = result.get("data", {})
        records = data.get("records", []) if isinstance(data, dict) else []
        if not records:
            return []

        history = []
        msg_id = 0
        for row in records:
            msg_id += 1
            question = row.get("question", "")
            answer = row.get("answer", "")
            create_time = row.get("createTime", "")
            referenced = row.get("referencedChunks", "")

            sources = None
            if referenced:
                try:
                    sources = json.dumps(json.loads(referenced), ensure_ascii=False) if isinstance(referenced, str) else json.dumps(referenced, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    sources = referenced if isinstance(referenced, str) else ""

            if question:
                history.append({
                    "id": msg_id,
                    "role": "user",
                    "content": question,
                    "sources": None,
                    "created_at": create_time,
                })
                msg_id += 1

            if answer:
                history.append({
                    "id": msg_id,
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "created_at": create_time,
                })

        return history

    async def _mysql_get_sessions(self, user_id: str = "", token: str = "") -> List[dict]:
        path = f"/api/conversations?pageSize=500&sortOrder=desc"
        if user_id:
            path += f"&userId={user_id}"
        result = await self._call_java(path, token=token)
        if not result or result.get("code") != 0:
            return []

        data = result.get("data", {})
        records = data.get("records", []) if isinstance(data, dict) else []
        if not records:
            return []

        session_map = {}
        for row in records:
            sid = row.get("sessionId", "")
            if not sid:
                continue
            create_time = row.get("createTime", "")
            question = row.get("question", "")

            if sid not in session_map:
                session_map[sid] = {
                    "id": sid,
                    "title": question[:50] if question else "新对话",
                    "created_at": create_time,
                    "updated_at": create_time,
                    "message_count": 0,
                }
            session_map[sid]["message_count"] += 2
            if create_time and create_time > session_map[sid]["updated_at"]:
                session_map[sid]["updated_at"] = create_time
            if create_time and create_time < session_map[sid]["created_at"]:
                session_map[sid]["created_at"] = create_time

        sessions = list(session_map.values())
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return sessions

    async def _redis(self):
        return await get_redis()

    async def _use_redis(self) -> bool:
        return REDIS_AVAILABLE

    async def get_session_owner(self, session_id: str) -> str:
        """查询会话归属的 user_id（先 Redis 后 SQLite）。

        查不到时返回空串——由调用方决定放行策略（未知归属不拦截，
        避免误伤 Java 侧或历史路径创建的会话）。
        """
        try:
            if await self._use_redis():
                r = await self._redis()
                uid = await r.hget(f"session:{session_id}", "user_id")
                if uid:
                    return str(uid)
        except Exception:
            pass
        try:
            db = await get_db()
            try:
                async with db.execute("SELECT user_id FROM sessions WHERE id = ?", (session_id,)) as cur:
                    row = await cur.fetchone()
                    if row and row[0]:
                        return str(row[0])
            finally:
                await db.close()
        except Exception:
            pass
        return ""

    async def create_session(self, title: str = "新对话", user_id: str = "") -> dict:
        session_id = uuid.uuid4().hex[:16]
        now = datetime.now().isoformat()
        meta = {
            "id": session_id,
            "title": title,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }

        if await self._use_redis():
            r = await self._redis()
            session_key = f"session:{session_id}"
            await _hset_all(r, session_key, {"id": session_id, "title": title, "user_id": user_id, "created_at": now, "updated_at": now})
            await r.expire(session_key, SESSION_TTL)
            if user_id:
                await r.sadd(f"user_sessions:{user_id}", session_id)
                await r.expire(f"user_sessions:{user_id}", SESSION_TTL)
        else:
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO sessions (id, title, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, title, user_id, now, now),
                )
                await db.commit()
            finally:
                await db.close()

        return meta

    async def get_sessions(self, user_id: str = "", token: str = "") -> List[dict]:
        if await self._use_redis():
            r = await self._redis()
            if user_id:
                session_ids = await r.smembers(f"user_sessions:{user_id}")

                # 兜底：集合为空时，用 SCAN 遍历所有 session 并重建用户关联
                if not session_ids:
                    cursor = 0
                    while True:
                        cursor, keys = await r.scan(cursor, match="session:*", count=100)
                        for key in keys:
                            if ":messages" in key:
                                continue
                            sid = key.replace("session:", "")
                            uid = await r.hget(key, "user_id")
                            if uid == user_id:
                                session_ids.append(sid)
                                await r.sadd(f"user_sessions:{user_id}", sid)
                        if cursor == 0:
                            break
                    if session_ids:
                        await r.expire(f"user_sessions:{user_id}", SESSION_TTL)
            else:
                cursor = 0
                session_ids = []
                while True:
                    cursor, keys = await r.scan(cursor, match="session:*", count=100)
                    for s in keys:
                        if ":messages" in s:
                            continue
                        session_ids.append(s.replace("session:", ""))
                    if cursor == 0:
                        break

            sessions = []
            for sid in session_ids:
                sid = sid.decode() if isinstance(sid, bytes) else sid
                session_key = f"session:{sid}"
                if not await r.exists(session_key):
                    continue
                meta = await r.hgetall(session_key)
                msg_count = await r.llen(f"session:{sid}:messages")
                sessions.append({
                    "id": meta.get("id", sid),
                    "title": meta.get("title", "新对话"),
                    "created_at": meta.get("created_at", ""),
                    "updated_at": meta.get("updated_at", ""),
                    "message_count": msg_count,
                })
            sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

            if sessions:
                return sessions

            sessions = await self._mysql_get_sessions(user_id, token)
            if sessions:
                # 回写 Redis 会话元数据，加速后续访问
                pipe = r.pipeline()
                for sess in sessions:
                    sk = f"session:{sess['id']}"
                    await _hset_all(r, sk, {
                        "id": sess["id"],
                        "title": sess["title"],
                        "user_id": user_id,
                        "created_at": sess.get("created_at", ""),
                        "updated_at": sess.get("updated_at", ""),
                    }, pipe=pipe)
                    pipe.expire(sk, SESSION_TTL)
                if user_id:
                    pipe.sadd(f"user_sessions:{user_id}", *[s["id"] for s in sessions])
                    pipe.expire(f"user_sessions:{user_id}", SESSION_TTL)
                try:
                    await pipe.execute()
                except Exception:
                    pass
                return sessions

            return []

        db = await get_db()
        try:
            if user_id:
                cursor = await db.execute(
                    "SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id) as message_count "
                    "FROM sessions s LEFT JOIN messages m ON s.id = m.session_id "
                    "WHERE s.user_id = ? "
                    "GROUP BY s.id ORDER BY s.updated_at DESC",
                    (user_id,),
                )
            else:
                cursor = await db.execute(
                    "SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id) as message_count "
                    "FROM sessions s LEFT JOIN messages m ON s.id = m.session_id "
                    "GROUP BY s.id ORDER BY s.updated_at DESC"
                )
            rows = await cursor.fetchall()
            return [{
                "id": row[0],
                "title": row[1] or "新对话",
                "created_at": row[2] or "",
                "updated_at": row[3] or "",
                "message_count": row[4] or 0,
            } for row in rows]
        finally:
            await db.close()

    async def delete_session(self, session_id: str, user_id: str = "") -> bool:
        if await self._use_redis():
            r = await self._redis()
            session_key = f"session:{session_id}"
            await r.delete(session_key)
            await r.delete(f"session:{session_id}:messages")
            if user_id:
                await r.srem(f"user_sessions:{user_id}", session_id)
        else:
            db = await get_db()
            try:
                await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                await db.commit()
            finally:
                await db.close()
        return True

    async def get_history(self, session_id: str, token: str = "") -> List[dict]:
        if await self._use_redis():
            r = await self._redis()
            messages_key = f"session:{session_id}:messages"
            raw_messages = await r.lrange(messages_key, 0, -1)
            if raw_messages:
                history = []
                for i, msg_str in enumerate(raw_messages):
                    msg = json.loads(msg_str)
                    msg["id"] = i + 1
                    history.append(msg)
                return history

            history = await self._mysql_get_history(session_id, token)
            if history:
                # 回写 Redis，加速后续访问
                pipe = r.pipeline()
                for msg in history:
                    pipe.rpush(f"session:{session_id}:messages",
                               json.dumps({"role": msg["role"], "content": msg["content"],
                                           "sources": msg.get("sources"), "created_at": msg.get("created_at", "")},
                                          ensure_ascii=False))
                pipe.expire(f"session:{session_id}:messages", SESSION_TTL)
                try:
                    await pipe.execute()
                except Exception:
                    pass
                return history

            return []

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, role, content, sources, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
            rows = await cursor.fetchall()
            return [{
                "id": row[0],
                "role": row[1],
                "content": row[2],
                "sources": row[3],
                "created_at": row[4] or "",
            } for row in rows]
        finally:
            await db.close()

    async def add_message(
        self, session_id: str, role: str, content: str, sources: Optional[List[dict]] = None
    ) -> int:
        sources_json = json.dumps(sources, ensure_ascii=False) if sources else None
        now = datetime.now().isoformat()

        if await self._use_redis():
            r = await self._redis()
            messages_key = f"session:{session_id}:messages"
            session_key = f"session:{session_id}"

            msg = {
                "role": role,
                "content": content,
                "sources": sources_json,
                "created_at": now,
            }
            await r.rpush(messages_key, json.dumps(msg, ensure_ascii=False))
            await r.expire(messages_key, SESSION_TTL)

            await r.hset(session_key, "updated_at", now)
            await r.expire(session_key, SESSION_TTL)

            user_id = await r.hget(session_key, "user_id")
            if user_id:
                await r.sadd(f"user_sessions:{user_id}", session_id)
                await r.expire(f"user_sessions:{user_id}", SESSION_TTL)

            msg_count = await r.llen(messages_key)
            return msg_count

        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO messages (session_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, sources_json, now),
            )
            await db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            await db.commit()

            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0
        finally:
            await db.close()

    async def update_title(self, session_id: str, title: str):
        if not title or title == "新对话":
            return
        if await self._use_redis():
            r = await self._redis()
            session_key = f"session:{session_id}"
            if await r.exists(session_key):
                current_title = await r.hget(session_key, "title")
                if current_title == "新对话":
                    await r.hset(session_key, "title", title[:50])
                    await r.expire(session_key, SESSION_TTL)
        else:
            db = await get_db()
            try:
                cursor = await db.execute("SELECT title FROM sessions WHERE id = ?", (session_id,))
                row = await cursor.fetchone()
                if row and row[0] == "新对话":
                    await db.execute("UPDATE sessions SET title = ? WHERE id = ?", (title[:50], session_id))
                    await db.commit()
            finally:
                await db.close()

    async def rename_session(self, session_id: str, title: str) -> bool:
        if await self._use_redis():
            r = await self._redis()
            session_key = f"session:{session_id}"
            if not await r.exists(session_key):
                return False
            await r.hset(session_key, "title", title[:50])
            await r.expire(session_key, SESSION_TTL)
            return True

        db = await get_db()
        try:
            cursor = await db.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
            if not await cursor.fetchone():
                return False
            await db.execute("UPDATE sessions SET title = ? WHERE id = ?", (title[:50], session_id))
            await db.commit()
            return True
        finally:
            await db.close()


    async def cleanup_old_sessions(self, days: int = 30):
        """清理 SQLite 中超过指定天数的旧会话及其消息（降级路径的数据维护）"""
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id FROM sessions WHERE updated_at < datetime('now', ?)",
                (f'-{days} days',),
            )
            old_ids = [row[0] for row in await cursor.fetchall()]
            if old_ids:
                for sid in old_ids:
                    await db.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
                await db.execute(
                    "DELETE FROM sessions WHERE updated_at < datetime('now', ?)",
                    (f'-{days} days',),
                )
                await db.commit()
                print(f"[session_service] Cleaned up {len(old_ids)} old sessions (>{days} days)")
            return len(old_ids)
        finally:
            await db.close()


session_service = SessionService()