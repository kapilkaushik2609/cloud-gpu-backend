from pydantic import BaseModel
from typing import Optional

class ProvisionRequest(BaseModel):
    gpu:           Optional[int] = None   # None = auto-select
    gpu_memory_gb: int  = 4
    cpus:          str  = "2"
    memory_gb:     str  = "8g"
    storage_gb:    int  = 20
    image:         str  = "nvidia/cuda:12.4.0-base-ubuntu22.04"
