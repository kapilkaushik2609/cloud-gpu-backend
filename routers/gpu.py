from fastapi import APIRouter, Depends, HTTPException
import services.auth_service as auth_svc
import services.gpu_service  as gpu_svc
import services.storage      as db

router = APIRouter()

@router.get("/status")
def gpu_status(user: dict = Depends(auth_svc.get_current_user)):
    return gpu_svc.gpu_status_map()

@router.get("/usage/{user_id}")
def usage(user_id: str, caller: dict = Depends(auth_svc.get_current_user)):
    # Customers can only see their own usage
    if caller["role"] != "admin" and caller["id"] != user_id:
        raise HTTPException(403, "Access denied")

    info = db.get_tenant(user_id)
    if not info:
        raise HTTPException(404, "No active instance for this user")

    metrics = gpu_svc.fetch_metrics(info["gpu"])
    return {
        "user_id":           user_id,
        "gpu":               info["gpu"],
        "allocated_vram_gb": info.get("gpu_memory_gb", 4),
        "metrics":           metrics,
    }

@router.get("/usage")
def my_usage(user: dict = Depends(auth_svc.get_current_user)):
    info = db.get_tenant(user["id"])
    if not info:
        raise HTTPException(404, "No active instance")
    metrics = gpu_svc.fetch_metrics(info["gpu"])
    return {
        "user_id":           user["id"],
        "gpu":               info["gpu"],
        "allocated_vram_gb": info.get("gpu_memory_gb", 4),
        "metrics":           metrics,
    }
