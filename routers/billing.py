import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import services.auth_service   as auth_svc
import services.billing_service as billing_svc
import services.storage         as db

router = APIRouter()

class PricingUpdate(BaseModel):
    vram_per_gb_per_hour:     float
    cpu_per_core_per_hour:    float
    ram_per_gb_per_hour:      float
    storage_per_gb_per_month: float

# ── Public / Customer ─────────────────────────────────────────────────────────

@router.get("/pricing")
def get_pricing(user: dict = Depends(auth_svc.get_current_user)):
    """Current pricing rates — visible to all authenticated users."""
    return db.get_pricing()

@router.get("/current")
def current_bill(user: dict = Depends(auth_svc.get_current_user)):
    """Live running cost for the customer's active instance."""
    tenant = db.get_tenant(user["id"])
    if not tenant:
        return {"current_total": 0, "hours_running": 0, "hourly_rate": 0, "currency": "INR"}
    return billing_svc.calculate_current_bill(tenant, db.get_pricing())

@router.get("/invoices")
def my_invoices(user: dict = Depends(auth_svc.get_current_user)):
    """Invoice history for the logged-in customer."""
    return db.get_user_invoices(user["id"])

# ── Admin ─────────────────────────────────────────────────────────────────────

@router.put("/pricing")
def update_pricing(req: PricingUpdate, admin: dict = Depends(auth_svc.require_admin)):
    """Admin sets new pricing rates."""
    pricing = {
        "vram_per_gb_per_hour":     req.vram_per_gb_per_hour,
        "cpu_per_core_per_hour":    req.cpu_per_core_per_hour,
        "ram_per_gb_per_hour":      req.ram_per_gb_per_hour,
        "storage_per_gb_per_month": req.storage_per_gb_per_month,
        "currency":                 "INR",
        "updated_at":               time.time(),
        "updated_by":               admin["id"],
    }
    db.save_pricing(pricing)
    return pricing

@router.get("/admin/invoices")
def all_invoices(admin: dict = Depends(auth_svc.require_admin)):
    """Admin: all invoices across all customers."""
    return db.get_invoices()

@router.get("/admin/revenue")
def revenue_summary(admin: dict = Depends(auth_svc.require_admin)):
    """Admin: revenue summary — total, this month, active running cost."""
    invoices = db.get_invoices()
    tenants  = db.get_tenants()
    pricing  = db.get_pricing()

    now   = time.time()
    month_start = now - (now % (30 * 86400))   # rough 30-day window

    total_revenue   = round(sum(inv["subtotal"] for inv in invoices), 2)
    monthly_revenue = round(sum(inv["subtotal"] for inv in invoices
                                if inv.get("created_at", 0) > now - 30*86400), 2)

    # Running cost of all active instances right now
    active_running = round(sum(
        billing_svc.calculate_current_bill(t, pricing)["current_total"]
        for t in tenants.values()
    ), 2)

    return {
        "total_revenue":   total_revenue,
        "monthly_revenue": monthly_revenue,
        "active_running":  active_running,
        "total_invoices":  len(invoices),
        "active_instances": len(tenants),
        "currency":        "INR",
    }

@router.get("/admin/running")
def all_running_costs(admin: dict = Depends(auth_svc.require_admin)):
    """Admin: live cost for every active instance."""
    tenants = db.get_tenants()
    pricing = db.get_pricing()
    users   = {u["id"]: u for u in db.get_users()}
    result  = []
    for uid, tenant in tenants.items():
        bill = billing_svc.calculate_current_bill(tenant, pricing)
        user = users.get(uid, {})
        result.append({
            **bill,
            "user_id":        uid,
            "user_name":      user.get("name", uid),
            "container_name": tenant.get("container_name"),
            "gpu":            tenant.get("gpu"),
            "gpu_memory_gb":  tenant.get("gpu_memory_gb"),
        })
    return result
