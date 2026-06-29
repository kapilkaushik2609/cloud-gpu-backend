from fastapi import APIRouter, Depends
from models.provision import ProvisionRequest
import services.auth_service  as auth_svc
import services.docker_service as docker_svc
import services.storage        as db

router = APIRouter()

@router.post("")
def provision(req: ProvisionRequest, user: dict = Depends(auth_svc.get_current_user)):
    return docker_svc.provision_container(user, req)

@router.get("/mine")
def my_instance(user: dict = Depends(auth_svc.get_current_user)):
    info = db.get_tenant(user["id"])
    if not info:
        return None
    status = docker_svc.get_container_status(info["container_id"])
    return {**info, "status": status, "ssh": docker_svc._build_ssh(info)}

@router.delete("/mine")
def deprovision_mine(user: dict = Depends(auth_svc.get_current_user)):
    return docker_svc.deprovision_container(user["id"])
