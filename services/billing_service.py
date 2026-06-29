import time, uuid
import services.storage as db

def calculate_hourly_rate(tenant: dict, pricing: dict) -> float:
    """Cost per hour in INR for a given tenant config."""
    vram_cost    = tenant.get("gpu_memory_gb", 0)  * pricing["vram_per_gb_per_hour"]
    cpu_cost     = float(tenant.get("cpus", 0))     * pricing["cpu_per_core_per_hour"]
    ram_gb       = float(str(tenant.get("memory_gb", "0g")).replace("g", ""))
    ram_cost     = ram_gb                            * pricing["ram_per_gb_per_hour"]
    return round(vram_cost + cpu_cost + ram_cost, 2)

def calculate_current_bill(tenant: dict, pricing: dict) -> dict:
    """Live running cost for an active instance."""
    started_at   = tenant.get("created_at", time.time())
    hours        = round((time.time() - started_at) / 3600, 4)
    hourly_rate  = calculate_hourly_rate(tenant, pricing)
    total        = round(hourly_rate * hours, 2)

    ram_gb = float(str(tenant.get("memory_gb", "0g")).replace("g", ""))
    return {
        "started_at":    started_at,
        "hours_running": round(hours, 2),
        "hourly_rate":   hourly_rate,
        "current_total": total,
        "currency":      pricing.get("currency", "INR"),
        "breakdown": {
            "vram":    {"gb":    tenant.get("gpu_memory_gb", 0),
                        "rate":  pricing["vram_per_gb_per_hour"],
                        "total": round(tenant.get("gpu_memory_gb", 0) * pricing["vram_per_gb_per_hour"] * hours, 2)},
            "cpu":     {"cores": float(tenant.get("cpus", 0)),
                        "rate":  pricing["cpu_per_core_per_hour"],
                        "total": round(float(tenant.get("cpus", 0)) * pricing["cpu_per_core_per_hour"] * hours, 2)},
            "ram":     {"gb":    ram_gb,
                        "rate":  pricing["ram_per_gb_per_hour"],
                        "total": round(ram_gb * pricing["ram_per_gb_per_hour"] * hours, 2)},
        },
    }

def generate_invoice(user: dict, tenant: dict, pricing: dict) -> dict:
    """Generate and save a final invoice when instance is stopped."""
    started_at  = tenant.get("created_at", time.time())
    ended_at    = time.time()
    hours       = round((ended_at - started_at) / 3600, 4)
    hourly_rate = calculate_hourly_rate(tenant, pricing)
    total       = round(hourly_rate * hours, 2)

    ram_gb = float(str(tenant.get("memory_gb", "0g")).replace("g", ""))

    invoice = {
        "id":             f"INV-{uuid.uuid4().hex[:8].upper()}",
        "user_id":        user["id"],
        "user_name":      user["name"],
        "user_email":     user["email"],
        "container_name": tenant.get("container_name", ""),
        "gpu":            tenant.get("gpu"),
        "gpu_memory_gb":  tenant.get("gpu_memory_gb"),
        "cpus":           tenant.get("cpus"),
        "memory_gb":      tenant.get("memory_gb"),
        "image":          tenant.get("image", ""),
        "started_at":     started_at,
        "ended_at":       ended_at,
        "hours":          round(hours, 4),
        "hourly_rate":    hourly_rate,
        "breakdown": {
            "vram": {"gb":    tenant.get("gpu_memory_gb", 0),
                     "rate":  pricing["vram_per_gb_per_hour"],
                     "total": round(tenant.get("gpu_memory_gb", 0) * pricing["vram_per_gb_per_hour"] * hours, 2)},
            "cpu":  {"cores": float(tenant.get("cpus", 0)),
                     "rate":  pricing["cpu_per_core_per_hour"],
                     "total": round(float(tenant.get("cpus", 0)) * pricing["cpu_per_core_per_hour"] * hours, 2)},
            "ram":  {"gb":    ram_gb,
                     "rate":  pricing["ram_per_gb_per_hour"],
                     "total": round(ram_gb * pricing["ram_per_gb_per_hour"] * hours, 2)},
        },
        "subtotal":  total,
        "currency":  pricing.get("currency", "INR"),
        "status":    "generated",
        "created_at": ended_at,
    }
    db.add_invoice(invoice)
    return invoice
