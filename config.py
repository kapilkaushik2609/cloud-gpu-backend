import os

SECRET_KEY       = os.environ.get("SECRET_KEY", "neural-cloud-secret-change-in-prod")
ALGORITHM        = "HS256"
TOKEN_EXPIRE_SEC = 86400          # 24 hours

PROMETHEUS_URL   = os.environ.get("PROMETHEUS_URL", "http://localhost:9091")
SERVER_IP        = os.environ.get("SERVER_IP",       "103.204.95.220")
SSH_PORT_RANGE   = range(32000, 32100)
MPS_PIPE_DIR     = "/tmp/nvidia-mps"

GPU_VRAM_GB      = {0: 15, 1: 20}   # A4000=15GB, A4500=20GB
DEFAULT_VRAM_GB  = 4

BASE_DIR  = os.path.dirname(__file__)
DATA_DIR  = os.path.join(BASE_DIR, "data")
LOG_FILE  = os.path.join(BASE_DIR, "neural_cloud.log")

DEFAULT_ADMIN_EMAIL    = "admin@neural.cloud"
DEFAULT_ADMIN_PASSWORD = "Admin@123"
DEFAULT_ADMIN_NAME     = "Admin"
