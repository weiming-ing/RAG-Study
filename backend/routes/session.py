from fastapi import APIRouter, HTTPException, Depends, Request
from models.schemas import SessionCreate, SessionRename
from services.session_service import session_service
from routes.auth import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(request: Request, current_user: dict = Depends(get_current_user)):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    sessions = await session_service.get_sessions(user_id=str(current_user["id"]), token=token)
    return {"success": True, "data": sessions}


@router.post("")
async def create_session(body: SessionCreate, current_user: dict = Depends(get_current_user)):
    session = await session_service.create_session(body.title, user_id=str(current_user["id"]))
    return {"success": True, "data": session}


@router.delete("/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    await _ensure_owner(session_id, current_user)
    await session_service.delete_session(session_id, user_id=str(current_user["id"]))
    return {"success": True, "message": "删除成功"}


async def _ensure_owner(session_id: str, current_user: dict):
    """校验会话归属：能查到归属且不匹配时返回 404（不暴露存在性）。

    归属未知（历史会话/Java 侧创建）时放行，保持向后兼容。
    """
    owner = await session_service.get_session_owner(session_id)
    if owner and owner != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/{session_id}/history")
async def get_history(session_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    await _ensure_owner(session_id, current_user)
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    history = await session_service.get_history(session_id, token=token)
    return {"success": True, "data": history}


@router.put("/{session_id}")
async def rename_session(session_id: str, body: SessionRename, current_user: dict = Depends(get_current_user)):
    await _ensure_owner(session_id, current_user)
    ok = await session_service.rename_session(session_id, body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"success": True, "message": "重命名成功"}