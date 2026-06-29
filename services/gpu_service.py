import os, subprocess, logging
from config import GPU_VRAM_GB, DEFAULT_VRAM_GB, MPS_PIPE_DIR, PROMETHEUS_URL
import requests as http
import services.storage as db

logger = logging.getLogger("neural_cloud")

def get_vram_used(gpu_index: int) -> int:
    return sum(
        t.get("gpu_memory_gb", DEFAULT_VRAM_GB)
        for t in db.get_tenants().values()
        if t.get("gpu") == gpu_index
    )

def get_vram_free(gpu_index: int) -> int:
    return max(0, GPU_VRAM_GB.get(gpu_index, 0) - get_vram_used(gpu_index))

def pick_best_gpu(requested_gb: int) -> int:
    candidates = sorted(
        [(g, get_vram_free(g)) for g in GPU_VRAM_GB],
        key=lambda x: x[1], reverse=True
    )
    for gpu_index, free in candidates:
        if free >= requested_gb:
            return gpu_index
    available = {g: f"{f}GB free" for g, f in candidates}
    from fastapi import HTTPException
    raise HTTPException(503, f"Not enough free VRAM. Requested {requested_gb}GB. Available: {available}")

def gpu_status_map() -> dict:
    tenants = db.get_tenants()
    users   = {u["id"]: u["name"] for u in db.get_users()}
    result  = {}
    for gpu_index, total in GPU_VRAM_GB.items():
        used = get_vram_used(gpu_index)
        free = get_vram_free(gpu_index)
        on_gpu = [
            {"user_id": uid, "name": users.get(uid, uid),
             "gpu_memory_gb": info.get("gpu_memory_gb", DEFAULT_VRAM_GB),
             "container": info.get("container_name")}
            for uid, info in tenants.items() if info.get("gpu") == gpu_index
        ]
        result[f"gpu_{gpu_index}"] = {
            "gpu_index":       gpu_index,
            "total_vram_gb":   total,
            "used_vram_gb":    used,
            "free_vram_gb":    free,
            "utilization_pct": round(used / total * 100, 1),
            "tenants":         on_gpu,
            "slots_remaining": free // DEFAULT_VRAM_GB,
        }
    return result

def fetch_metrics(gpu_index: int) -> dict:
    queries = {
        "temp_c":      f'DCGM_FI_DEV_GPU_TEMP{{gpu="{gpu_index}"}}',
        "power_w":     f'DCGM_FI_DEV_POWER_USAGE{{gpu="{gpu_index}"}}',
        "util_pct":    f'DCGM_FI_DEV_GPU_UTIL{{gpu="{gpu_index}"}}',
        "mem_used_mb": f'DCGM_FI_DEV_FB_USED{{gpu="{gpu_index}"}}',
        "mem_free_mb": f'DCGM_FI_DEV_FB_FREE{{gpu="{gpu_index}"}}',
    }
    results = {}
    for key, q in queries.items():
        try:
            r = http.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": q}, timeout=5)
            vals = r.json().get("data", {}).get("result", [])
            results[key] = float(vals[0]["value"][1]) if vals else None
        except Exception as e:
            results[key] = None
    return results

def setup_mps(gpu_index: int):
    mps_dir = f"{MPS_PIPE_DIR}/{gpu_index}"
    log_dir = f"/tmp/nvidia-log/{gpu_index}"
    os.makedirs(mps_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    check = subprocess.run(["pgrep", "-f", f"nvidia-cuda-mps-control.*{gpu_index}"], capture_output=True)
    if check.returncode == 0:
        return
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu_index),
           "CUDA_MPS_PIPE_DIRECTORY": mps_dir, "CUDA_MPS_LOG_DIRECTORY": log_dir}
    r = subprocess.run(["nvidia-cuda-mps-control", "-d"], env=env, capture_output=True, text=True)
    if r.returncode != 0:
        logger.warning(f"MPS start failed for GPU {gpu_index}: {r.stderr.strip()} — continuing")
    else:
        logger.info(f"MPS started for GPU {gpu_index}")

def stop_mps(gpu_index: int):
    mps_dir = f"{MPS_PIPE_DIR}/{gpu_index}"
    env = {**os.environ, "CUDA_MPS_PIPE_DIRECTORY": mps_dir}
    subprocess.run("echo quit | nvidia-cuda-mps-control", shell=True, env=env, capture_output=True)
