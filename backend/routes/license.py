"""
授权状态接口

- GET /api/license          查看当前授权状态（需登录）
- GET /api/license/fingerprint  读取本机机器指纹（需登录；便于交付时读给供应商签发）
- POST /api/license/reload  清除缓存并重新校验（需登录；换授权文件后无需重启）
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from routes.auth import get_current_user
from services.license_service import license_service, machine_fingerprint, license_machine_id

router = APIRouter(prefix="/api/license", tags=["license"])


@router.get("")
async def get_license(current_user: dict = Depends(get_current_user)):
    status = license_service.status(force=True)
    data = status.to_dict()
    # 机器标识原文只在管理端可见，便于排查指纹问题
    data["machineId"] = license_machine_id()
    return JSONResponse(content={"success": True, "data": data})


@router.get("/fingerprint")
async def get_fingerprint(current_user: dict = Depends(get_current_user)):
    """交付时把该值读给供应商，用于签发绑定本机的授权。"""
    return JSONResponse(content={
        "success": True,
        "data": {
            "fingerprint": machine_fingerprint(),
            "machineId": license_machine_id(),
        },
    })


@router.post("/reload")
async def reload_license(current_user: dict = Depends(get_current_user)):
    license_service.invalidate()
    status = license_service.status(force=True)
    return JSONResponse(content={
        "success": status.valid,
        "data": status.to_dict(),
        "error": "" if status.valid else status.message,
    })
