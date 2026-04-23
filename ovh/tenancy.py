from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import Column, String, DateTime


TENANT_RE = re.compile(r"^[a-z0-9-]{2,32}$")


def _domain_root() -> str:
    return (os.environ.get("DOMAIN_ROOT") or "zjedz.it").lower().strip()


def extract_tenant_slug(hostname: Optional[str]) -> Optional[str]:
    if not hostname:
        return None
    host = hostname.split(":")[0].lower().strip()
    root = _domain_root()

    if host in {root, f"www.{root}"}:
        return None
    if host == f"dash.{root}":
        return "dash"

    parts = host.split(".")
    root_parts = root.split(".")
    if len(parts) >= len(root_parts) + 1 and parts[-len(root_parts):] == root_parts:
        return parts[0]
    return None


def require_dash_token(request: Request) -> None:
    token = request.headers.get("X-Dash-Token")
    expected = os.environ.get("DASH_ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="DASH_ADMIN_TOKEN not configured")
    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def setup_tenancy(app, SessionLocal, Base):
    class Tenant(Base):
        __tablename__ = "tenants"
        id = Column(String, primary_key=True)
        slug = Column(String, unique=True, index=True, nullable=False)
        name = Column(String, nullable=False)
        status = Column(String, default="active")  # active / disabled / deleted
        created_at = Column(DateTime, default=datetime.utcnow)
        disabled_at = Column(DateTime, nullable=True)
        deleted_at = Column(DateTime, nullable=True)

    router = APIRouter(prefix="/api/dash", tags=["DASH Tenants"])

    # --- Caddy ask endpoint ---
    # Caddy calls: GET /api/dash/allow?domain=<hostname>  [1](https://deepwiki.com/lucaslorentz/caddy-docker-proxy/3.1-docker-labels)[2](https://ovh.github.io/manager/)
    @router.get("/allow")
    async def allow_domain(domain: str):
        host = (domain or "").split(":")[0].lower().strip()
        root = _domain_root()

        # Always allow landing + dash
        if host in {root, f"www.{root}", f"dash.{root}"}:
            return {"ok": True}

        # Deny if it's not a proper tenant host
        slug = extract_tenant_slug(host)
        if not slug or slug == "dash":
            return JSONResponse(status_code=403, content={"ok": False})

        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
            if not tenant or tenant.status != "active":
                return JSONResponse(status_code=403, content={"ok": False})
            return {"ok": True}
        finally:
            db.close()

    # --- CRUD tenants (DASH) ---
    @router.get("/tenants")
    async def list_tenants(request: Request):
        require_dash_token(request)
        db = SessionLocal()
        try:
            tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
            return {
                "ok": True,
                "tenants": [
                    {
                        "slug": t.slug,
                        "name": t.name,
                        "status": t.status,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                        "disabled_at": t.disabled_at.isoformat() if t.disabled_at else None,
                    }
                    for t in tenants
                ],
            }
        finally:
            db.close()

    @router.post("/tenants")
    async def create_tenant(request: Request):
        require_dash_token(request)
        data = await request.json()
        slug = (data.get("slug") or "").lower().strip()
        name = (data.get("name") or slug).strip()

        if not TENANT_RE.match(slug):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Zły slug (2-32, a-z0-9-)"})

        if slug in {"dash", "www", "admin"}:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Slug zarezerwowany"})

        db = SessionLocal()
        try:
            existing = db.query(Tenant).filter(Tenant.slug == slug).first()
            if existing and existing.status == "active":
                return JSONResponse(status_code=409, content={"ok": False, "error": "Tenant już istnieje"})

            if existing and existing.status != "active":
                existing.status = "active"
                existing.disabled_at = None
                existing.deleted_at = None
                if name:
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
