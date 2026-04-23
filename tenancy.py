# Tenancy Logic - Stable v2.1 (UTF-8) - 2026-04-23 18:20
import os, uuid, json
from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import Column, String, DateTime, Boolean
from pathlib import Path

def setup_tenancy(app, SessionLocal, Base):
    class Tenant(Base):
        __tablename__ = "tenants"
        id = Column(String, primary_key=True)
        slug = Column(String, unique=True, index=True)
        name = Column(String)
        status = Column(String, default="active") # active, disabled
        created_at = Column(DateTime, default=datetime.utcnow)
        disabled_at = Column(DateTime, nullable=True)

    # Helper function to get domain root
    def _domain_root():
        return os.environ.get("DOMAIN_ROOT", "zjedz.it")

    router = APIRouter(prefix="/api/admin", tags=["Tenancy"])

    def require_dash_token(request: Request):
        token = os.environ.get("DASH_ADMIN_TOKEN", "elvis-secure-token")
        provided = request.headers.get("X-Dash-Token") or request.query_params.get("token")
        if provided != token:
            raise HTTPException(status_code=403, detail="Brak uprawnień administratora")

    @router.get("/tenants")
    async def list_tenants(request: Request):
        require_dash_token(request)
        db = SessionLocal()
        try:
            tenants = db.query(Tenant).all()
            return [{"slug": t.slug, "name": t.name, "status": t.status, "fqdn": f"{t.slug}.{_domain_root()}"} for t in tenants]
        finally:
            db.close()

    @router.post("/tenants")
    async def create_tenant_entry(request: Request):
        require_dash_token(request)
        data = await request.json()
        slug = data.get("slug").lower().strip()
        name = data.get("name", slug.capitalize())
        
        if not slug:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Brak sluga"})

        db = SessionLocal()
        try:
            existing = db.query(Tenant).filter(Tenant.slug == slug).first()
            if existing:
                existing.status = "active"
                existing.name = name
            else:
                t = Tenant(id=str(uuid.uuid4()), slug=slug, name=name, status="active")
                db.add(t)

            db.commit()
            return {"ok": True, "slug": slug, "name": name, "fqdn": f"{slug}.{_domain_root()}"}
        finally:
            db.close()

    @router.delete("/tenants/{slug}")
    async def disable_tenant(slug: str, request: Request):
        require_dash_token(request)
        slug = slug.lower().strip()
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
            if not tenant:
                return JSONResponse(status_code=404, content={"ok": False, "error": "Tenant nie istnieje"})
            tenant.status = "disabled"
            tenant.disabled_at = datetime.utcnow()
            db.commit()
            return {"ok": True, "slug": slug, "status": tenant.status}
        finally:
            db.close()

    app.include_router(router)
    return Tenant
