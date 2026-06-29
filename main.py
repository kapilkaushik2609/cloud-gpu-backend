"""
Neural Cloud — Backend API
Run: uvicorn main:app --host 0.0.0.0 --port 7085 --reload
"""
import logging, time
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from config import LOG_FILE, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_NAME
import services.storage as db
import services.auth_service as auth_svc
from routers import auth, provision, gpu, admin

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("neural_cloud")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Neural Cloud API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logger ────────────────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start    = time.time()
    response = await call_next(request)
    ms       = round((time.time() - start) * 1000)
    logger.info(f"{request.method} {request.url.path}  status={response.status_code}  {ms}ms")
    return response

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(provision.router, prefix="/provision", tags=["Provision"])
app.include_router(gpu.router,       prefix="/gpu",       tags=["GPU"])
app.include_router(admin.router,     prefix="/admin",     tags=["Admin"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "Neural Cloud API v2"}

# ── Seed default admin on first run ──────────────────────────────────────────
@app.on_event("startup")
def seed_admin():
    if not db.get_users():
        user = auth_svc.create_user(
            DEFAULT_ADMIN_NAME,
            DEFAULT_ADMIN_EMAIL,
            DEFAULT_ADMIN_PASSWORD,
            role="admin"
        )
        logger.info(f"Default admin created: {DEFAULT_ADMIN_EMAIL}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7085, reload=True)
