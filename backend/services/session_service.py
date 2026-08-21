import json
import uuid
from datetime import datetime
from typing import List, Optional
from database.db import get_redis, get_db
from config import SESSION_TTL

REDIS_AVAILABLE = False


async def check_redis():
    global REDIS_AVAILABLE
    try:
        r = await get_redis()
        await r.ping()
        REDIS_AVAILABLE = True
    except Exception:
        REDIS_AVAILABLE = False


class SessionService:

    async def _redis(self):
        return await get_redis()

    async def _use_redis(self) -> bool:
        return REDIS_AVAILABLE

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
            await r.hmset(session_key, {"id": session_id, "title": title, "user_id": user_id, "created_at": now, "updated_at": now})
            await r.expire(session_key, SESSION_TTL)
            if user_id:
                await r.sadd(f"user_sessions:{user_id}", session_id)
                await r.expire(f"user_sessions:{user_id}", SESSION_TTL)
        else:
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (session_id, title, now, now),
                )
                await db.commit()
            finally:
                await db.close()

        return meta

    async def get_sessions(self, user_id: str = "") -> List[dict]:
        if await self._use_redis():
            r = await self._redis()
            if user_id:
                session_ids = await r.smembers(f"user_sessions:{user_id}")

                # 兜底：集合为空时，扫描所有 session 并重建用户关联
                if not session_ids:
                    raw_keys = await r.keys("session:*")
                    for key in raw_keys:
                        key = key.decode() if isinstance(key, bytes) else key
                        if ":messages" in key:
                            continue
                        sid = key.replace("session:", "")
                        uid = await r.hget(key, "user_id")
                        if uid == user_id:
                            session_ids.append(sid)
                            await r.sadd(f"user_sessions:{user_id}", sid)
                    if session_ids:
                        await r.expire(f"user_sessions:{user_id}", SESSION_TTL)
            else:
                raw_keys = await r.keys("session:*")
                session_ids = []
                for s in raw_keys:
                    s = s.decode() if isinstance(s, bytes) else s
                    if ":messages" in s:
                        continue
                    session_ids.append(s.replace("session:", ""))

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
            return sessions

        db = await get_db()
        try:
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

    async def get_history(self, session_id: str) -> List[dict]:
        if await self._use_redis():
            r = await self._redis()
            messages_key = f"session:{session_id}:messages"
            raw_messages = await r.lrange(messages_key, 0, -1)
            history = []
            for i, msg_str in enumerate(raw_messages):
                msg = json.loads(msg_str)
                msg["id"] = i + 1
                history.append(msg)
            return history

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


session_service = SessionService()