import random, secrets, string, time, uuid, logging
import docker
from fastapi import HTTPException
from config import SSH_PORT_RANGE, SERVER_IP, MPS_PIPE_DIR, GPU_VRAM_GB, DEFAULT_VRAM_GB
import services.storage as db
import services.gpu_service as gpu_svc

logger  = logging.getLogger("neural_cloud")
CLIENT  = docker.from_env()

def generate_password(n=12) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n))

def pick_free_port() -> int:
    used = {t["ssh_port"] for t in db.get_tenants().values() if "ssh_port" in t}
    free = [p for p in SSH_PORT_RANGE if p not in used]
    if not free:
        raise HTTPException(503, "No free SSH ports")
    return random.choice(free)

def setup_ssh(container, password: str):
    cmds = [
        "apt-get update -qq",
        "apt-get install -y -qq openssh-server",
        "mkdir -p /var/run/sshd",
        f"echo 'root:{password}' | chpasswd",
        "sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config",
        "sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config",
        "/usr/sbin/sshd",
    ]
    for cmd in cmds:
        code, out = container.exec_run(f'bash -c "{cmd}"')
        if code != 0:
            raise HTTPException(500, f"SSH setup failed: {cmd} → {out.decode()[:200]}")

def _build_ssh(record: dict) -> dict:
    return {
        "host":     SERVER_IP,
        "port":     record["ssh_port"],
        "username": "root",
        "password": record.get("ssh_password", ""),
        "command":  f"ssh root@{SERVER_IP} -p {record['ssh_port']}",
    }

def provision_container(user: dict, req) -> dict:
    user_id = user["id"]

    # Validate VRAM
    if req.gpu_memory_gb < 1 or req.gpu_memory_gb > max(GPU_VRAM_GB.values()):
        raise HTTPException(400, f"gpu_memory_gb must be 1–{max(GPU_VRAM_GB.values())}")

    if db.get_tenant(user_id):
        raise HTTPException(409, "You already have an active instance. Stop it first.")

    # Pick GPU
    if req.gpu is not None:
        if req.gpu not in GPU_VRAM_GB:
            raise HTTPException(400, f"Invalid GPU index. Valid: {list(GPU_VRAM_GB)}")
        free = gpu_svc.get_vram_free(req.gpu)
        if free < req.gpu_memory_gb:
            raise HTTPException(503, f"GPU {req.gpu} only has {free}GB free. Requested {req.gpu_memory_gb}GB.")
        gpu_index = req.gpu
    else:
        gpu_index = gpu_svc.pick_best_gpu(req.gpu_memory_gb)

    total_vram   = GPU_VRAM_GB[gpu_index]
    mem_fraction = round(req.gpu_memory_gb / total_vram, 4)
    thread_pct   = max(5, int(mem_fraction * 100))
    mps_dir      = f"{MPS_PIPE_DIR}/{gpu_index}"

    gpu_svc.setup_mps(gpu_index)

    ssh_port       = pick_free_port()
    password       = generate_password()
    container_name = f"nc-{user['name'].lower().replace(' ','-')[:12]}-{uuid.uuid4().hex[:6]}"

    logger.info(f"Provisioning  user={user_id}  gpu={gpu_index}  vram={req.gpu_memory_gb}GB  port={ssh_port}")

    container = CLIENT.containers.run(
        req.image,
        name=container_name,
        command="sleep infinity",
        detach=True,
        remove=False,
        device_requests=[docker.types.DeviceRequest(device_ids=[str(gpu_index)], capabilities=[["gpu"]])],
        nano_cpus=int(float(req.cpus) * 1e9),
        mem_limit=req.memory_gb,
        ports={"22/tcp": ssh_port},
        volumes={mps_dir: {"bind": "/tmp/nvidia-mps", "mode": "rw"}},
        environment={
            "CUDA_MPS_PIPE_DIRECTORY":           "/tmp/nvidia-mps",
            "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(thread_pct),
            "GPU_MEMORY_FRACTION":               str(mem_fraction),
            "GPU_MEMORY_LIMIT_GB":               str(req.gpu_memory_gb),
            "NEURAL_CLOUD_USER":                 user_id,
            "NEURAL_CLOUD_GPU":                  str(gpu_index),
        },
        labels={"neural_cloud": "true", "user_id": user_id, "gpu_index": str(gpu_index)},
    )

    # Setup SSH
    setup_ssh(container, password)

    record = {
        "container_id":   container.id,
        "container_name": container_name,
        "gpu":            gpu_index,
        "gpu_memory_gb":  req.gpu_memory_gb,
        "gpu_fraction":   mem_fraction,
        "cpus":           req.cpus,
        "memory_gb":      req.memory_gb,
        "storage_gb":     req.storage_gb,
        "image":          req.image,
        "ssh_port":       ssh_port,
        "ssh_password":   password,
        "created_at":     time.time(),
        "user_id":        user_id,
        "user_name":      user["name"],
    }
    db.set_tenant(user_id, record)
    logger.info(f"Provisioned  user={user_id}  container={container_name}")

    return {
        **record,
        "status": "running",
        "ssh": _build_ssh({**record, "ssh_password": password}),
    }

def deprovision_container(user_id: str) -> dict:
    info = db.get_tenant(user_id)
    if not info:
        raise HTTPException(404, "No active instance found")

    gpu_index = info.get("gpu", 0)
    try:
        c = CLIENT.containers.get(info["container_id"])
        c.stop(timeout=5)
        c.remove()
    except docker.errors.NotFound:
        pass

    db.remove_tenant(user_id)

    # Stop MPS if no more tenants on this GPU
    remaining = [t for t in db.get_tenants().values() if t.get("gpu") == gpu_index]
    if not remaining:
        gpu_svc.stop_mps(gpu_index)

    logger.info(f"Deprovisioned  user={user_id}  container={info['container_name']}")
    return {"status": "removed", "freed_vram_gb": info.get("gpu_memory_gb", DEFAULT_VRAM_GB)}

def get_container_status(container_id: str) -> str:
    try:
        return CLIENT.containers.get(container_id).status
    except docker.errors.NotFound:
        return "missing"
