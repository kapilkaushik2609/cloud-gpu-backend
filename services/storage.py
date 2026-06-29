import json, os, threading
from config import DATA_DIR

_lock = threading.Lock()
USERS_FILE    = os.path.join(DATA_DIR, "users.json")
TENANTS_FILE  = os.path.join(DATA_DIR, "tenants.json")
PRICING_FILE  = os.path.join(DATA_DIR, "pricing.json")
INVOICES_FILE = os.path.join(DATA_DIR, "invoices.json")

os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_PRICING = {
    "vram_per_gb_per_hour":     8.0,
    "cpu_per_core_per_hour":    2.0,
    "ram_per_gb_per_hour":      1.0,
    "storage_per_gb_per_month": 0.5,
    "currency":                 "INR",
    "updated_at":               None,
    "updated_by":               None,
}

def _read(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)

def _write(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ── Users ─────────────────────────────────────────────────────────────────────
def get_users() -> list:
    with _lock:
        return _read(USERS_FILE, [])

def save_users(users: list):
    with _lock:
        _write(USERS_FILE, users)

def find_user_by_email(email: str) -> dict | None:
    return next((u for u in get_users() if u["email"].lower() == email.lower()), None)

def find_user_by_id(uid: str) -> dict | None:
    return next((u for u in get_users() if u["id"] == uid), None)

def upsert_user(user: dict):
    users = get_users()
    idx = next((i for i, u in enumerate(users) if u["id"] == user["id"]), None)
    if idx is None:
        users.append(user)
    else:
        users[idx] = user
    save_users(users)

def delete_user(uid: str):
    users = [u for u in get_users() if u["id"] != uid]
    save_users(users)

# ── Tenants ───────────────────────────────────────────────────────────────────
def get_tenants() -> dict:
    with _lock:
        return _read(TENANTS_FILE, {})

def save_tenants(tenants: dict):
    with _lock:
        _write(TENANTS_FILE, tenants)

def get_tenant(user_id: str) -> dict | None:
    return get_tenants().get(user_id)

def set_tenant(user_id: str, info: dict):
    t = get_tenants()
    t[user_id] = info
    save_tenants(t)

def remove_tenant(user_id: str):
    t = get_tenants()
    t.pop(user_id, None)
    save_tenants(t)

# ── Pricing ───────────────────────────────────────────────────────────────────
def get_pricing() -> dict:
    with _lock:
        return _read(PRICING_FILE, DEFAULT_PRICING.copy())

def save_pricing(pricing: dict):
    with _lock:
        _write(PRICING_FILE, pricing)

# ── Invoices ──────────────────────────────────────────────────────────────────
def get_invoices() -> list:
    with _lock:
        return _read(INVOICES_FILE, [])

def save_invoices(invoices: list):
    with _lock:
        _write(INVOICES_FILE, invoices)

def add_invoice(invoice: dict):
    invoices = get_invoices()
    invoices.append(invoice)
    save_invoices(invoices)

def get_user_invoices(user_id: str) -> list:
    return [inv for inv in get_invoices() if inv["user_id"] == user_id]
