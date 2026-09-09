from fastapi import APIRouter, HTTPException, Depends
from models.schemas import SessionCreate, SessionRename
from services.session_service import session_service
from routes.auth import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(current_user: dict = Depends(get_current_user)):
    sessions = await session_service.get_sessions(user_id=str(current_user["id"]))
    return {"success": True, "data": sessions}


@router.post("")
async def create_session(body: SessionCreate, current_user: dict = Depends(get_current_user)):
    session = await session_service.create_session(body.title, user_id=str(current_user["id"]))
    return {"success": True, "data": session}


@router.delete("/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    await session_service.delete_session(session_id, user_id=str(current_user["id"]))
    return {"success": True, "message": "删除成功"}


@router.get("/{session_id}/history")
async def get_history(session_id: str, current_user: dict = Depends(get_current_user)):
    history = await session_service.get_history(session_id)
    return {"success": True, "data": history}


@router.put("/{session_id}")
async def rename_session(session_id: str, body: SessionRename, current_user: dict = Depends(get_current_user)):
    ok = await session_service.rename_session(session_id, body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"success": True, "message": "重命名成功"}