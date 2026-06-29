from fastapi import APIRouter, Depends, HTTPException
from models.provision import ProvisionRequest
from models.user import UpdateRoleRequest, UserOut
import services.auth_service  as auth_svc
import services.docker_service as docker_svc
import services.storage        as db

router = APIRouter()

def _to_out(u):
    return UserOut(id=u["id"], name=u["name"], email=u["email"],
                   role=u["role"], is_active=u["is_active"], created_at=u["created_at"])

# ── Users ──────────────────────────────────────────────────────────────────────
@router.get("/users")
def list_users(admin: dict = Depends(auth_svc.require_admin)):
    users   = db.get_users()
    tenants = db.get_tenants()
    return [
        {**_to_out(u).model_dump(),
         "has_instance": u["id"] in tenants}
        for u in users
    ]

@router.put("/users/{user_id}/role")
def update_role(user_id: str, req: UpdateRoleRequest, admin: dict = Depends(auth_svc.require_admin)):
    if req.role not in ("admin", "customer"):
        raise HTTPException(400, "role must be 'admin' or 'customer'")
    user = db.find_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user["role"] = req.role
    db.upsert_user(user)
    return _to_out(user)

@router.patch("/users/{user_id}/toggle")
def toggle_user(user_id: str, admin: dict = Depends(auth_svc.require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(400, "Cannot deactivate yourself")
    user = db.find_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user["is_active"] = not user["is_active"]
    db.upsert_user(user)
    return _to_out(user)

@router.delete("/users/{user_id}")
def delete_user(user_id: str, admin: dict = Depends(auth_svc.require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(400, "Cannot delete yourself")
    # Deprovision first if they have an instance
    if db.get_tenant(user_id):
        docker_svc.deprovision_container(user_id)
    db.delete_user(user_id)
    return {"status": "deleted", "user_id": user_id}

# ── Tenants ────────────────────────────────────────────────────────────────────
@router.get("/tenants")
def list_tenants(admin: dict = Depends(auth_svc.require_admin)):
    tenants = db.get_tenants()
    users   = {u["id"]: u for u in db.get_users()}
    result  = []
    for uid, info in tenants.items():
        status = docker_svc.get_container_status(info["container_id"])
        user   = users.get(uid, {})
        result.append({**info, "status": status,
                       "user_name": user.get("name", uid),
                       "user_email": user.get("email", "")})
    return result

@router.post("/provision/{user_id}")
def provision_for_user(user_id: str, req: ProvisionRequest,
                       admin: dict = Depends(auth_svc.require_admin)):
    user = db.find_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return docker_svc.provision_container(user, req)

@router.delete("/tenants/{user_id}")
def deprovision_any(user_id: str, admin: dict = Depends(auth_svc.require_admin)):
    return docker_svc.deprovision_container(user_id)
