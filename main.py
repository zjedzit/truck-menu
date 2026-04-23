# Elvis Orchestrator - Stable v2.1 (UTF-8) - 2026-04-23 18:20
import os, requests, json, uuid
from openai import OpenAI
from fastapi import FastAPI, Request, File, UploadFile, Form, Cookie, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

import logging
import random
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter
from pymongo import MongoClient
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship


app = FastAPI()
APP_DIR = Path(__file__).resolve().parent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Ensure database connection on startup"""
    try:
        conn = get_db()
        try:
            from sqlalchemy import text
            # Existing migrations
            conn.session.execute(text("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS mode VARCHAR DEFAULT 'restaurant'"))
            conn.session.execute(text("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
            
            # New migrations for Order model expansion
            conn.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS burger_name VARCHAR"))
            conn.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS price FLOAT"))
            conn.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS note VARCHAR"))
            conn.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS to_kitchen BOOLEAN DEFAULT TRUE"))
            
            conn.session.commit()
            logger.info("Database migration: all columns checked and updated.")
        except Exception as mig_err:
            logger.warning(f"Migration warning (might be already up to date): {mig_err}")
            
        load_ai_config()
        logger.info("[ELVIS 2.0] SYSTEM INITIALIZED - STABLE")
    except Exception as e:
        logger.error(f"Startup error: {e}")

# Global exception handlers to ensure JSON response instead of HTML
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception: {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": f"Internal Server Error: {str(exc)}\n{tb}"},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"ok": False, "error": "Błąd walidacji danych: " + str(exc.errors())},
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": str(exc.detail)},
    )

# --- HARDWARE & PRINTER API ---
@app.post("/api/hardware/print")
async def send_print_job(request: Request):
    """Sends a print job (receipt or order) to a specific device via WS"""
    try:
        data = await request.json()
        device_key = data.get("device_key", "default_printer")
        content = data.get("content", {})
        job_type = data.get("type", "receipt") # receipt, kds_bon, fiscal
        
        # Prepare message for WebSocket
        message = json.dumps({
            "type": "print_job",
            "job_type": job_type,
            "data": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # In a real scenario, we'd target a specific connection from the manager
        # For now, we broadcast it, and the T520 agent with matching key will pick it up
        await manager.broadcast(message)
        
        return {"success": True, "message": f"Zadanie druku ({job_type}) wysłane do {device_key}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- AI ANALYTICS API ---
@app.get("/api/ai/analytics/report")
async def get_ai_analytics_report():
    """Generates a professional AI report on 'Who, Where, When, What'"""
    try:
        # 1. Gather data from DB
        database = get_db()
        if database is None: return {"error": "DB connection failed"}
        
        orders = list(database["orders"].find({}))
        # 2. Prepare prompt for Gemini
        analysis_context = ""
        for o in orders[-50:]: # analyze last 50 orders
            analysis_context += f"Time: {o.get('timestamp')}, Table: {o.get('table_number')}, Item: {o.get('burger_name')}, Price: {o.get('price')}\n"
        
        prompt = f"""
        Jesteś ekspertem analityki biznesowej w gastronomii. 
        Przeanalizuj poniższe dane sprzedażowe z systemu Elvis POS i stwórz profesjonalny raport:
        1. KTO: Jakie są trendy zakupowe (np. grupy znajomych vs osoby indywidualne)?
        2. KIEDY: W jakich godzinach jest największy ruch i co wtedy schodzi?
        3. GDZIE: Które stoliki/strefy są najbardziej dochodowe?
        4. CO: Jakie produkty są 'gwiazdami' a jakie 'psami' (macierz BGC)?
        
        Dane:
        {analysis_context}
        
        Raport powinien być w języku Polskim, profesjonalny i konkretny.
        """
        
        # 3. Call AI (using the existing OpenAI client structure if configured)
        # For now, return a placeholder or call the AI if API key is present
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            report = response.choices[0].message.content
        else:
            report = "Symulowany Raport AI: Największy ruch odnotowano w godz. 12-14. Stolik nr 5 generuje 30% obrotu. Bestseller: Elvis Classic."

        return {"success": True, "report": report}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- BILLING & CASH MANAGEMENT API ---
@app.get("/api/cash/status")
async def get_cash_status():
    """Returns the current open cash session"""
    db = get_db()
    if db is None: return {"error": "DB connection failed"}
    
    current_session = db["cash_sessions"].find_one({"status": "open"})
    if not current_session:
        # Check the last closed session to compare with next opening (as requested)
        last_session = db["cash_sessions"].find_one({"status": "closed"}, sort=[("closed_at", -1)])
        return {"ok": True, "session": None, "last_closing_cash": last_session.get("actual_cash", 0) if last_session else 0}
        
    # Calculate expectation based on transactions
    transactions = list(db["cash_transactions"].find({"session_id": current_session["_id"]}))
    total_sales = sum(t["amount"] for t in transactions if t["type"] == "sale")
    total_in = sum(t["amount"] for t in transactions if t["type"] == "in")
    total_out = sum(t["amount"] for t in transactions if t["type"] == "out")
    
    current_session["expected_now"] = current_session["starting_cash"] + total_sales + total_in - total_out
    return {"ok": True, "session": current_session}

@app.post("/api/cash/open")
async def open_cash_session(starting_cash: float, staff_id: str):
    """Opens a new daily cash session"""
    db = get_db()
    if db is None: return {"error": "DB connection failed"}
    
    # Check if a session is already open
    if db["cash_sessions"].find_one({"status": "open"}):
        return {"ok": False, "error": "Sesja jest już otwarta."}
    
    # Check for discrepancy from previous day (as requested: "nawet jeżeli różnica pojawi się rano")
    last_session = db["cash_sessions"].find_one({"status": "closed"}, sort=[("closed_at", -1)])
    morning_diff = 0
    if last_session:
        morning_diff = starting_cash - last_session["actual_cash"]
    
    session_id = str(uuid.uuid4())
    new_session = {
        "_id": session_id,
        "opened_at": datetime.now(),
        "starting_cash": starting_cash,
        "morning_difference": morning_diff,
        "status": "open",
        "staff_id": staff_id
    }
    
    db["cash_sessions"].insert_one(new_session)
    return {"ok": True, "session_id": session_id, "morning_warning": morning_diff != 0, "morning_diff": morning_diff}

@app.post("/api/cash/transaction")
async def add_cash_transaction(amount: float, type: str, reason: str, staff_id: str):
    """Record manual Cash In / Cash Out"""
    db = get_db()
    current_session = db["cash_sessions"].find_one({"status": "open"})
    if not current_session:
        return {"ok": False, "error": "Brak otwartej sesji kasy."}
        
    tx_id = str(uuid.uuid4())
    tx = {
        "_id": tx_id,
        "session_id": current_session["_id"],
        "amount": amount,
        "type": type, # 'in', 'out'
        "reason": reason,
        "staff_id": staff_id,
        "timestamp": datetime.now()
    }
    db["cash_transactions"].insert_one(tx)
    return {"ok": True}

@app.post("/api/cash/close")
async def close_cash_session(actual_cash: float, staff_id: str):
    """Closes current session and reports difference"""
    db = get_db()
    current_session = db["cash_sessions"].find_one({"status": "open"})
    if not current_session:
        return {"ok": False, "error": "Brak otwartej sesji."}
    
    # Sum it all up
    transactions = list(db["cash_transactions"].find({"session_id": current_session["_id"]}))
    total_flow = sum(t["amount"] * (1 if t["type"] in ['sale', 'in'] else -1) for t in transactions)
    expected = current_session["starting_cash"] + total_flow
    
    diff = actual_cash - expected
    
    db["cash_sessions"].update_one(
        {"_id": current_session["_id"]},
        {"$set": {
            "status": "closed",
            "closed_at": datetime.now(),
            "actual_cash": actual_cash,
            "expected_cash": expected,
            "difference": diff,
            "closing_staff_id": staff_id
        }}
    )
    return {"ok": True, "difference": diff, "is_balanced": diff == 0}

@app.get("/api/cash/settlements")
async def get_staff_settlements():
    """Returns settlements for each waiter/driver (as requested)"""
    db = get_db()
    current_session = db["cash_sessions"].find_one({"status": "open"})
    if not current_session: return {"error": "Brak otwartej sesji"}
    
    txs = list(db["cash_transactions"].find({"session_id": current_session["_id"]}))
    
    staff_summary = defaultdict(lambda: {"total_sales": 0, "payouts": 0, "net": 0})
    for t in txs:
        sid = t.get("staff_id", "nieznany")
        if t["type"] == "sale":
            staff_summary[sid]["total_sales"] += t["amount"]
        elif t["type"] == "out":
            staff_summary[sid]["payouts"] += t["amount"]
        
        staff_summary[sid]["net"] = staff_summary[sid]["total_sales"] - staff_summary[sid]["payouts"]
        
    return {"ok": True, "settlements": staff_summary}

@app.get("/api/gus/nip/{nip}")
async def get_nip_data(nip: str):
    """GUS NIP Integration (Placeholder)"""
    # In production, this would call BIR1.1 or similar service
    logger.info(f"Looking up NIP: {nip}")
    
    # Mock data for demonstration
    if nip == "1234567890":
        return {
            "success": True,
            "company_name": "ELVIS BURGER SP. Z O.O.",
            "address": "ul. Burgerowa 1, 00-001 Warszawa",
            "nip": nip
        }
    
    return {"success": False, "error": "Nie znaleziono firmy o tym numerze NIP."}




# Helper for getting system mode with DB persistence + File Override (2.0)
def get_system_mode():
    # 0. Supreme Override via File (Radical Simplicity for 2.0)
    try:
        if os.path.exists("system_mode.txt"):
            with open("system_mode.txt", "r") as f:
                mode = f.read().strip().lower()
                if mode in ["foodtruck", "restaurant"]:
                    logger.info(f"[ELVIS 2.0] !!! FILE OVERRIDE DETECTED !!! => {mode}")
                    return mode
    except Exception as e:
        logger.error(f"[ELVIS 2.0] Error reading system_mode.txt: {e}")

    brand_id = os.environ.get("BRAND", "ELVIS").lower()
    logger.info(f"[ELVIS 2.0] Checking persistence for {brand_id}...")
    try:
        conn = get_db()
        if conn:
            # 1. Try brand ID (lowercase)
            rest = conn["restaurants"].find_one({"_id": brand_id})
            if rest and "mode" in rest:
                logger.info(f"--- DB FOUND: '{brand_id}' mode: {rest['mode']} ---")
                return rest["mode"]
                
            # 2. Try UPPERCASE brand ID
            rest = conn["restaurants"].find_one({"_id": brand_id.upper()})
            if rest and "mode" in rest:
                logger.info(f"--- DB FOUND (UPPER): '{brand_id.upper()}' mode: {rest['mode']} ---")
                return rest["mode"]

            # 3. Try global fallback 'elvis'
            rest = conn["restaurants"].find_one({"_id": "elvis"})
            if rest and "mode" in rest:
                logger.info(f"--- DB FOUND (GLOBAL): 'elvis' mode: {rest['mode']} ---")
                return rest["mode"]

            # 4. Fallback to general config
            config = conn["config"].find_one({"_id": "system_settings"})
            if config and "mode" in config:
                logger.info(f"--- DB FOUND (CONFIG): mode: {config['mode']} ---")
                return config["mode"]
    except Exception as e:
        logger.error(f"--- DATABASE ERROR during get_system_mode: {e} ---")
    
    # 5. Environment variable as last resort
    env_mode = os.environ.get("SYSTEM_MODE", "restaurant")
    logger.info(f"[ELVIS 2.0] FINAL MODE => {env_mode} (Source: ENV/DEFAULT)")
    return env_mode

def is_nfc_required():
    try:
        db = get_db()
        if db is not None:
            settings = db["config"].find_one({"_id": "system_settings"}) or {}
            return settings.get("nfc_required", True)
    except:
        pass
    return True

def set_system_mode(mode: str):
    brand_id = os.environ.get("BRAND", "ELVIS").lower()
    logger.info(f"SETTING MODE -> {brand_id} to {mode}")
    # Update local process env as fallback/immediate
    os.environ["SYSTEM_MODE"] = mode
    try:
        conn = get_db()
        if conn:
            conn["restaurants"].update_one(
                {"_id": brand_id}, 
                {"$set": {"mode": mode, "updated_at": datetime.utcnow()}}, 
                upsert=True
            )
            # Second update for the default 'elvis' if brand is different
            if brand_id != "elvis":
                conn["restaurants"].update_one(
                    {"_id": "elvis"}, 
                    {"$set": {"mode": mode, "updated_at": datetime.utcnow()}}, 
                    upsert=True
                )
            logger.info(f"System mode '{mode}' saved successfully to DB.")
            return True
    except Exception as e:
        logger.error(f"Error saving system mode to DB: {e}")
    return False

    return False

# --- QR TRACKING COMPONENTS ---
qr_router = APIRouter(prefix="/qrtrack", tags=["QR Tracking"])

class SessionItem(BaseModel):
    item_id: str
    name: str
    price: float
    quantity: int = 1

class SessionRequest(BaseModel):
    customer_name: Optional[str] = None
    mode: str = "restaurant"  # "restaurant" or "foodtruck"

class SessionResponse(BaseModel):
    session_id: str
    session_number: int
    status: str
    items: List[SessionItem] = []
    timestamp: datetime

# Session management - now persistent in MongoDB
MAX_SESSIONS = 30

def get_next_session_number():
    """Get next available session number (1-30). If full, recycles oldest."""
    conn = get_db()
    if conn is None: return 1
    
    active_tables_list = list(conn["active_tables"].find({}))
    used_numbers = [int(t["_id"]) for t in active_tables_list if str(t["_id"]).isdigit()]
    
    # 1. Try to find a gap
    for n in range(1, MAX_SESSIONS + 1):
        if n not in used_numbers:
            return n

    # 2. Recycle: reset all active tables and start from 1 as requested
    print("WARNING: All sessions taken. Resetting active_tables.")
    conn["active_tables"].delete_many({})
    return 1
    
def create_session(customer_name: str = None, mode: str = "restaurant"):
    """Create new session with unique ID and session number and save to DB"""
    session_id = str(uuid.uuid4())
    session_number = get_next_session_number()
    
    session = {
        "_id": session_id,
        "session_id": session_id,
        "session_number": session_number,
        "status": "active",
        "items": [],
        "timestamp": datetime.now(),
        "last_activity": datetime.now(),
        "customer_name": customer_name,
        "mode": mode
    }
    
    conn = get_db()
    if conn is not None:
        conn["sessions"].insert_one(session)
        conn["active_tables"].update_one(
            {"_id": str(session_number)}, 
            {"$set": {"table_number": str(session_number), "session_id": session_id, "timestamp": datetime.now()}}, 
            upsert=True
        )
    return session

@qr_router.post("/new", response_model=SessionResponse)
async def create_qr_session(request: SessionRequest):
    """Create new QR session"""
    session = create_session(request.customer_name, request.mode)
    # Convert _id to string for response
    session["session_id"] = str(session["_id"])
    return session

@qr_router.get("/new")
async def get_qr_new_info():
    """Friendly info for GET requests to /new"""
    return JSONResponse({
        "ok": True, 
        "message": "Ten endpoint przyjmuje tylko POST. Odwiedź /zamowienie aby zobaczyć panel."
    })

@qr_router.get("/session/{session_id}")
async def get_session(request: Request, session_id: str):
    """Get session details or render menu for guest"""
    conn = get_db()
    session = conn["sessions"].find_one({"_id": session_id}) if conn is not None else None
    
    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Sesja nie istnieje lub wygasła.")
    
    # If the request wants HTML (browser), render the index.html (menu)
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        # Load menu data
        menu = load_menu_data()
        return templates.TemplateResponse(request=request, name="index.html", context={
            "request": request,
            "brand": get_brand(request),
            "menu": menu,
            "session_table": str(session["session_number"]),
            "my_session_id": session_id,
            "table_locked": False,
            "system_mode": get_system_mode()
        })
    
    return session

@qr_router.post("/session/{session_id}/add_item")
async def add_item_to_session(session_id: str, item: SessionItem):
    """Add item to session"""
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update last activity
    session["last_activity"] = datetime.now()
    
    # Add item to session
    session["items"].append(item.dict())
    return {"status": "success", "message": "Item added"}

@qr_router.get("/queue")
async def get_queue_status():
    """Get current queue status"""
    active_sessions = [
        {
            "session_id": sid,
            "session_number": sess["session_number"],
            "customer_name": sess["customer_name"],
            "mode": sess["mode"],
            "timestamp": sess["timestamp"],
            "status": sess["status"]
        }
        for sid, sess in ACTIVE_SESSIONS.items() 
        if sess["status"] == "active"
    ]
    
    return {
        "total_active": len(active_sessions),
        "queue": sorted(active_sessions, key=lambda x: x["session_number"]),
        "max_sessions": MAX_SESSIONS,
        "available_slots": MAX_SESSIONS - len(active_sessions)
    }

@qr_router.post("/session/{session_id}/complete")
async def complete_session(session_id: str):
    """Complete session"""
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    
    session["status"] = "completed"
    session["completed_at"] = datetime.now()
    
    # Return session number to queue
    SESSION_QUEUE.append(session["session_number"])
    
    return {"status": "completed", "session_number": session["session_number"]}

# --- CONFIGURATION API ENDPOINTS ---
@app.get("/api/config/local")
async def get_local_config(auth_role: Optional[str] = None):
    """Get local connection configuration from DB"""
    if auth_role not in ["master", "admin"]:
        return JSONResponse({"error": "Brak uprawnień"}, status_code=403)
    
    db = get_db()
    conf = db["config"].find_one({"_id": "connectivity"}) or {}
    
    return {
        "server_address": conf.get("server_address", os.environ.get("SERVER_ADDRESS", "https://bar.zjedz.it")),
        "local_address": conf.get("local_address", os.environ.get("LOCAL_ADDRESS", "http://elvis.local:8080")),
        "device_key": conf.get("device_key", os.environ.get("DEVICE_KEY", "Elvis_KWI_0326")),
        "master_token": conf.get("master_token", os.environ.get("MASTER_TOKEN", "aabe2d70-09ee-4aa9-a166-9bcfdd3949b5"))
    }

@app.post("/api/config/local")
async def save_local_config(request: Request, auth_role: Optional[str] = None):
    """Save local connection configuration to DB"""
    if auth_role not in ["master", "admin"]:
        return JSONResponse({"error": "Brak uprawnień"}, status_code=403)
    
    try:
        data = await request.json()
        db = get_db()
        
        # Build update document
        update_doc = {
            "server_address": data.get("server_address"),
            "device_key": data.get("device_key"),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Optional fields if provided
        if "local_address" in data: update_doc["local_address"] = data["local_address"]
        if "master_token" in data: update_doc["master_token"] = data["master_token"]
        
        db["config"].update_one(
            {"_id": "connectivity"},
            {"$set": update_doc},
            upsert=True
        )
        
        # Sync to environment for immediate use in current process
        for k, v in update_doc.items():
            if isinstance(v, str):
                os.environ[k.upper()] = v
        
        return {"success": True, "message": "Konfiguracja zapisana pomyślnie"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- MASTER API ENDPOINTS ---
@app.post("/api/master/toggle_mode")
async def toggle_master_mode(request: Request, auth_role: Optional[str] = None):
   """Set or Toggle system mode (restaurant/foodtruck)"""
   if auth_role != "master":
      return JSONResponse({"error": "Brak uprawnień"}, status_code=403)
   
   try:
      data = await request.json()
      requested_mode = data.get("mode")
      if requested_mode in ["restaurant", "foodtruck"]:
         new_mode = requested_mode
      else:
         new_mode = "foodtruck" if get_system_mode() == "restaurant" else "restaurant"
   except:
      new_mode = "foodtruck" if get_system_mode() == "restaurant" else "restaurant"
      
   set_system_mode(new_mode)
   return {"success": True, "message": f"Tryb systemu ustawiony na: {new_mode}", "mode": new_mode}

# Include the QR router in the main app
app.include_router(qr_router)

# --- AUTH & MARKETING CONSENT API ---
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

class MarketingConsentRequest(BaseModel):
    email: str
    phone: Optional[str] = None
    full_name: Optional[str] = None
    marketing_consent: bool
    registration_id: Optional[str] = None

@auth_router.post("/register_consent")
async def register_marketing_consent(request: MarketingConsentRequest):
    """Registers marketing consent for a client"""
    db = SessionLocal()
    try:
        client_id = str(uuid.uuid4())
        new_client = Client(
            id=client_id,
            email=request.email,
            phone=request.phone,
            full_name=request.full_name,
            marketing_consent=request.marketing_consent,
            registration_id=request.registration_id or client_id[:8]
        )
        db.add(new_client)
        db.commit()
        return {"success": True, "client_id": client_id, "registration_id": new_client.registration_id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@auth_router.post("/google_login")
async def google_login_placeholder(token: str):
    """Placeholder for Google Login integration"""
    # In a real app, verify the token with Google
    logger.info(f"Google login attempt with token: {token[:10]}...")
    return {"success": True, "message": "Google Login integration active (placeholder)"}

@auth_router.post("/send_sms_code")
async def send_sms_code_placeholder(phone: str):
    """Placeholder for SMS confirmation via API Gateway"""
    # Integration with SMSAPI.pl or similar would go here
    logger.info(f"SMS code requested for: {phone}")
    return {"success": True, "message": f"Kod testowy wysłany na {phone} (bramka SMS placeholder)"}

@auth_router.post("/nfc_toggle")
async def nfc_toggle(nfc_id: str = Form(...)):
    """Handles NFC tag tap (Login/Logout toggle)"""
    db = SessionLocal()
    try:
        # Mask the ID in logs for privacy
        masked_id = nfc_id[:2] + "****" + nfc_id[-2:] if len(nfc_id) > 4 else "****"
        logger.info(f"NFC Tap attempted: {masked_id}")

        staff = db.query(Staff).filter(Staff.nfc_id == nfc_id).first()
        if not staff:
            return JSONResponse({"success": False, "error": "Nieautoryzowany dostęp (Tag ukryty)"}, status_code=403)
        
        # Toggle activity status
        staff.is_active = not staff.is_active
        staff.updated_at = datetime.utcnow()
        event_type = "login" if staff.is_active else "logout"
        
        # Log activity
        activity = StaffActivity(staff_id=staff.id, event_type=event_type)
        db.add(activity)
        db.commit()
        
        # Broadcast via WebSocket (without sending the NFC ID)
        await manager.broadcast(json.dumps({
            "type": "nfc_auth",
            "staff_name": staff.name,
            "role": staff.role,
            "status": event_type,
            "is_active": staff.is_active
        }))
        
        return {
            "success": True, 
            "staff_name": staff.name, 
            "is_active": staff.is_active,
            "event": event_type
        }
    except Exception as e:
        db.rollback()
        logger.error(f"NFC Auth Error: {e}")
        return JSONResponse({"success": False, "error": "Błąd autoryzacji"}, status_code=500)
    finally:
        db.close()

app.include_router(auth_router)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for d in disconnected:
            self.disconnect(d)

manager = ConnectionManager()
DEVICE_STATUS_CACHE = {} # Global cache for device status (online/offline, ip, etc.)

@app.websocket("/ws")
@app.websocket("/ws/")
async def websocket_endpoint(websocket: WebSocket):
    device_key = websocket.query_params.get("device_key", "anonymous")
    await manager.connect(websocket)
    print(f"WS Client connected: {device_key}")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                m_type = msg.get("type")
                
                # Update device_key if provided in message
                if "device_key" in msg:
                    device_key = msg["device_key"]

                if m_type in ["register", "device_status"]:
                    # Zapisujemy status urządzenia w pamięci RAM
                    DEVICE_STATUS_CACHE[device_key] = {
                        "status": "online",
                        "ip": msg.get("ip", "unknown"),
                        "last_seen": datetime.now(timezone.utc).isoformat()
                    }
                    # Rozgłaszamy do paneli admina/wydawki że status się zmienił
                    await manager.broadcast(json.dumps({"type": "update"}))
                elif msg.get("type") == "receipt_ack":
                    # Obsługa ACK z T520 (potwierdzenie wydruku) — aktualizacja bazy i rozgłoszenie
                    receipt_id = msg.get("id")
                    status = msg.get("status")
                    if receipt_id:
                        try:
                            database = get_db()
                            if database is not None:
                                update_data = {"status": status}
                                if status != "error":
                                    update_data["printed"] = True
                                database["pos_history"].update_one({"_id": receipt_id}, {"$set": update_data})
                        except Exception as e:
                            print(f"DEBUG: Could not update pos_history for {receipt_id}: {e}")
                        
                    await manager.broadcast(json.dumps({
                        "type": "receipt_ack",
                        "id": receipt_id,
                        "table_number": msg.get("table_number"),
                        "status": status
                    }))
            except Exception as e: 
                print(f"WS Error processing message: {e}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Mark as offline in cache
        if device_key in DEVICE_STATUS_CACHE:
            DEVICE_STATUS_CACHE[device_key]["status"] = "offline"
        else:
            DEVICE_STATUS_CACHE[device_key] = {"status": "offline"}
            
        await manager.broadcast(json.dumps({"type": "update"}))
        print(f"WS Client disconnected: {device_key}")

@app.get("/api/active_staff")
async def get_active_staff():
    """Returns list of currently active (logged in via NFC) staff"""
    db = SessionLocal()
    try:
        active = db.query(Staff).filter(Staff.is_active == True).all()
        return {
            "staff": [{"id": s.id, "name": s.name, "role": s.role} for s in active]
        }
    finally:
        db.close()

@app.get("/api/device_status/{device_key}")
async def get_device_status(device_key: str):
    # Pobieramy z RAM zamiast Firestore
    return DEVICE_STATUS_CACHE.get(device_key, {"status": "offline"})


app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
import os
brand_name = os.environ.get("BRAND", "").lower()
brand_template_dir = APP_DIR / f"templates_{brand_name}"

if brand_name and brand_template_dir.exists():
    templates = Jinja2Templates(directory=str(brand_template_dir))
else:
    templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

@app.get("/sw.js")
async def service_worker():
    """Serwuje Service Worker z root scope — wymagane do cache'owania obrazków."""
    sw_path = APP_DIR / "static" / "sw.js"
    from fastapi.responses import FileResponse
    return FileResponse(
        str(sw_path),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"}
    )


@app.get("/regulamin", response_class=HTMLResponse)
async def get_legal(request: Request):
    legal_path = APP_DIR / "REGULAMIN.md"
    content = "Błąd: Nie znaleziono pliku regulaminu."
    if legal_path.exists():
        with open(legal_path, "r", encoding="utf-8") as f:
            content = f.read().replace("\n", "<br>")
    return templates.TemplateResponse(request=request, name="legal.html", context={"request": request, "content": content})


@app.get("/admin/queue", response_class=HTMLResponse)
async def get_admin_queue(request: Request):
    """Admin view of the queue (30 slots)"""
    return templates.TemplateResponse(request=request, name="zamowienie.html", context={
        "request": request,
        "system_mode": get_system_mode(),
        "brand": get_brand(request)
    })

# --- POSTGRESQL / SQLALCHEMY SETUP ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://marcin:Haslo123!@localhost:5432/saas_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

from tenancy import setup_tenancy
Tenant = setup_tenancy(app, SessionLocal, Base)


# Models
class Client(Base):
    __tablename__ = "clients"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String, unique=True, index=True)
    full_name = Column(String)
    marketing_consent = Column(Boolean, default=False)
    registration_id = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Staff(Base):
    __tablename__ = "staff"
    id = Column(String, primary_key=True) # Name as ID as per previous logic
    name = Column(String)
    pin = Column(String)
    nfc_id = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=False)
    role = Column(String) # 'waiter', 'chef', 'admin'
    updated_at = Column(DateTime, default=datetime.utcnow)

class StaffActivity(Base):
    __tablename__ = "staff_activity"
    id = Column(Integer, primary_key=True, autoincrement=True)
    staff_id = Column(String, ForeignKey("staff.id"))
    event_type = Column(String)  # 'login', 'logout'
    timestamp = Column(DateTime, default=datetime.utcnow)

class CashSession(Base):
    __tablename__ = "cash_sessions"
    id = Column(String, primary_key=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime)
    starting_cash = Column(Float)
    expected_cash = Column(Float, default=0.0)
    actual_cash = Column(Float)
    difference = Column(Float)
    status = Column(String, default="open") # 'open', 'closed'
    staff_id = Column(String)
    notes = Column(String)

class CashTransaction(Base):
    __tablename__ = "cash_transactions"
    id = Column(String, primary_key=True)
    session_id = Column(String)
    amount = Column(Float)
    type = Column(String) # 'in', 'out', 'sale'
    reason = Column(String)
    staff_id = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True)
    table_number = Column(String)
    session_id = Column(String)
    burger_name = Column(String)
    price = Column(Float)
    note = Column(String)
    to_kitchen = Column(Boolean, default=True)
    items = Column(JSON)
    total = Column(Float)
    paid = Column(Boolean, default=False)
    payment_method = Column(String) # 'cash', 'card', 'transfer', 'online'
    discount_value = Column(Float, default=0.0)
    discount_type = Column(String) # 'percent', 'flat'
    is_invoice = Column(Boolean, default=False)
    invoice_nip = Column(String)
    invoice_company_name = Column(String)
    invoice_address = Column(String)
    status = Column(String, default="nowe")
    timestamp = Column(DateTime, default=datetime.utcnow)

class MenuItem(Base):
    __tablename__ = "menu"
    id = Column(String, primary_key=True) # Mongo _id
    name = Column(String)
    price = Column(Float)
    category = Column(String)
    description = Column(String)
    image_url = Column(String)
    available = Column(Boolean, default=True)
    options = Column(JSON) # Dla dodatków itp.
    allergens = Column(String, default="") # Alergeny (np. "gluten, mleko")
    kcal = Column(String, default="") # Kalorie
    weight = Column(String, default="") # Gramatura w gramach
    to_kitchen = Column(Boolean, default=True) # Wysyłaj na KDS
    no_rating = Column(Boolean, default=False) # Ukryj gwiazdki oceniania
    sort_order = Column(Integer, default=10) # Kolejność sortowania

class POSHistory(Base):
    __tablename__ = "pos_history"
    id = Column(String, primary_key=True)
    table_number = Column(String)
    items = Column(JSON)
    total = Column(Float)
    status = Column(String)
    printed = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Restaurant(Base):
    __tablename__ = "restaurants"
    id = Column(String, primary_key=True)
    name = Column(String)
    mode = Column(String, default="restaurant")
    updated_at = Column(DateTime, default=datetime.utcnow)

class AppConfig(Base):
    __tablename__ = "config"
    id = Column(String, primary_key=True)
    data = Column(JSON)

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(String, primary_key=True)
    customer_name = Column(String)
    phone = Column(String)
    table_number = Column(String)
    reservation_time = Column(DateTime)
    guests_count = Column(Integer)
    status = Column(String, default="confirmed") # confirmed, cancelled, completed
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    staff_id = Column(String)
    action = Column(String) # 'item_deleted', 'price_changed', 'order_cancelled', 'login_error'
    details = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="confirmed") # confirmed, cancelled, completed
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

class MongoCompatibility:
    """Warstwa kompatybilności pozwalająca używać składni MongoDB z bazą Postgres"""
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()
    
    def __getitem__(self, collection_name):
        return CollectionWrapper(self.session, collection_name)

class MockCursor:
    """Helper class to emulate MongoDB cursor behavior (sort, limit, iteration)"""
    def __init__(self, data):
        self._data = data

    def sort(self, field, direction=-1):
        # direction -1 is DESC, 1 is ASC
        rev = True if direction == -1 else False
        try:
            # Simple in-place sort
            self._data.sort(key=lambda x: (x.get(field) is not None, x.get(field)), reverse=rev)
        except Exception as e:
            logger.error(f"MockCursor sort error on field '{field}': {e}")
        return self

    def limit(self, n):
        self._data = self._data[:n]
        return self

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, index):
        return self._data[index]

    def __len__(self):
        return len(self._data)

    def to_list(self):
        return self._data

class CollectionWrapper:
    def __init__(self, session, name):
        self.session = session
        self.name = name

    def _is_native(self):
        return self.name in ["menu", "staff", "pos_history", "orders", "clients", "config", "restaurants", "cash_sessions", "cash_transactions"]

    def _get_config_id(self, doc_id):
        if self.name == "config": return str(doc_id)
        return f"{self.name}_{doc_id}"

    def find(self, query=None):
        # Emulacja find() - zwraca listę słowników
        results = []
        try:
            query = query or {}
            if not self._is_native():
                prefix = f"{self.name}_"
                items = self.session.query(AppConfig).filter(AppConfig.id.like(f"{prefix}%")).all()
                for i in items:
                    d = i.data.copy() if i.data else {}
                    d["_id"] = i.id[len(prefix):]
                    # Filter emulation
                    if all(d.get(k) == v for k, v in query.items() if k != "_id"):
                        results.append(d)
                return results

            items = []
            if self.name == "menu":
                items = self.session.query(MenuItem).all()
            elif self.name == "staff":
                items = self.session.query(Staff).all()
            elif self.name == "pos_history":
                items = self.session.query(POSHistory).all()
            elif self.name == "orders":
                items = self.session.query(Order).all()
            elif self.name == "restaurants":
                items = self.session.query(Restaurant).all()
            elif self.name == "clients":
                items = self.session.query(Client).all()
            elif self.name == "cash_sessions":
                items = self.session.query(CashSession).all()
            elif self.name == "cash_transactions":
                items = self.session.query(CashTransaction).all()
            elif self.name == "config":
                items = self.session.query(AppConfig).all()
                for i in items:
                    d = i.data.copy() if i.data else {}
                    d["_id"] = i.id
                    if all(d.get(k) == v for k, v in query.items() if k != "_id"):
                        results.append(d)
                return results

            for i in items:
                d = {k: v for k, v in i.__dict__.items() if not k.startswith('_')}
                d["_id"] = d.pop("id", None)
                if getattr(i, "options", None) and isinstance(i.options, dict):
                    d.update(i.options)
                
                # Filter emulation
                if all(d.get(k) == v for k, v in query.items() if k != "_id"):
                    results.append(d)
        except Exception as e:
            logger.error(f"Error in find({self.name}): {e}")
        return MockCursor(results)

    def delete_many(self, query):
        """Emulacja delete_many dla Postgres"""
        try:
            if not self._is_native():
                # Dla AppConfig szukamy po ID z prefiksem
                doc_id = query.get("_id")
                if doc_id and isinstance(doc_id, dict) and "$in" in doc_id:
                    ids = [self._get_config_id(i) for i in doc_id["$in"]]
                    self.session.query(AppConfig).filter(AppConfig.id.in_(ids)).delete(synchronize_session=False)
                elif doc_id:
                    self.session.query(AppConfig).filter(AppConfig.id == self._get_config_id(doc_id)).delete(synchronize_session=False)
                else:
                    prefix = f"{self.name}_"
                    self.session.query(AppConfig).filter(AppConfig.id.like(f"{prefix}%")).delete(synchronize_session=False)
                self.session.commit()
                return

            # Dla natywnych tabel
            model = None
            if self.name == "menu": model = MenuItem
            elif self.name == "staff": model = Staff
            elif self.name == "orders": model = Order
            elif self.name == "active_tables": model = None # Map we don't have a model for this?
            
            if model:
                q = self.session.query(model)
                # Obsługa filtrów (np. _id, table_number, paid)
                for k, v in query.items():
                    if k == "_id":
                        if isinstance(v, dict) and "$in" in v:
                            q = q.filter(model.id.in_(v["$in"]))
                        else:
                            q = q.filter(model.id == v)
                    elif hasattr(model, k):
                        q = q.filter(getattr(model, k) == v)
                
                q.delete(synchronize_session=False)
                self.session.commit()
        except Exception as e:
            logger.error(f"Error in delete_many({self.name}): {e}")
            self.session.rollback()

    def delete_one(self, query):
        """Emulacja delete_one"""
        # W tej prostej implementacji delete_one działa jak delete_many
        self.delete_many(query)

    def update_many(self, query, update_data):
        """Emulacja update_many"""
        # Dla uproszczenia wykonujemy pętlę po trafieniach
        docs = self.find(query)
        for doc in docs:
            self.update_one({"_id": doc["_id"]}, update_data)

    def find_one(self, query, sort=None):
        # Bardzo uproszczona emulacja dla najczęstszych zapytań
        try:
            item_id = query.get("_id") or query.get("id")
            if not self._is_native():
                real_id = self._get_config_id(item_id)
                item = self.session.query(AppConfig).filter(AppConfig.id == real_id).first()
                if item:
                    d = item.data.copy() if item.data else {}
                    d["_id"] = str(item_id)
                    return d
                return None

            item = None
            if self.name == "staff":
                name = query.get("name") or item_id
                item = self.session.query(Staff).filter(Staff.id == name).first()
            elif self.name == "orders":
                item = self.session.query(Order).filter(Order.id == item_id).first()
            elif self.name == "clients":
                email = query.get("email")
                item = self.session.query(Client).filter(Client.email == email).first()
            elif self.name == "menu":
                item = self.session.query(MenuItem).filter(MenuItem.id == item_id).first()
            elif self.name == "pos_history":
                item = self.session.query(POSHistory).filter(POSHistory.id == item_id).first()
            elif self.name == "restaurants":
                item = self.session.query(Restaurant).filter(Restaurant.id == item_id).first()
            elif self.name == "config":
                item = self.session.query(AppConfig).filter(AppConfig.id == item_id).first()
                if item:
                    d = item.data.copy() if item.data else {}
                    d["_id"] = item.id
                    return d

            if item:
                d = {k: v for k, v in item.__dict__.items() if not k.startswith('_')}
                d["_id"] = d.pop("id", None)
                if getattr(item, "options", None) and isinstance(item.options, dict):
                    d.update(item.options)
                return d
        except Exception as e:
            logger.error(f"Error in find_one: {e}")
        return None

    def update_one(self, query, update_data, upsert=False):
        from sqlalchemy.orm.attributes import flag_modified
        # Emulacja update_one i upsertów w ORM
        try:
            doc_id = query.get("_id") or query.get("id")
            if not doc_id: return
            changes = update_data.get("$set", {})

            if not self._is_native() or self.name == "config":
                real_id = self._get_config_id(doc_id)
                item = self.session.query(AppConfig).filter(AppConfig.id == real_id).first()
                
                if item:
                    new_data = item.data.copy() if item.data else {}
                    new_data.update(changes)
                    item.data = new_data
                    flag_modified(item, "data")
                    self.session.commit()
                elif upsert:
                    new_item = AppConfig(id=real_id, data=changes)
                    self.session.add(new_item)
                    self.session.commit()
                return

            item = None
            if self.name == "menu":
                item = self.session.query(MenuItem).filter(MenuItem.id == doc_id).first()
            elif self.name == "staff":
                item = self.session.query(Staff).filter(Staff.id == doc_id).first()
            elif self.name == "orders":
                item = self.session.query(Order).filter(Order.id == doc_id).first()
            elif self.name == "restaurants":
                item = self.session.query(Restaurant).filter(Restaurant.id == doc_id).first()

            if item:
                opts = getattr(item, "options", {}) or {}
                changed_opts = False
                for k, v in changes.items():
                    if hasattr(item, k):
                        setattr(item, k, v)
                    else:
                        opts[k] = v
                        changed_opts = True
                if changed_opts and hasattr(item, "options"):
                    item.options = opts
                    flag_modified(item, "options")
                self.session.commit()
            elif upsert:
                new_item = None
                opts = {}
                if self.name == "menu":
                    new_item = MenuItem(id=str(doc_id))
                    for k, v in changes.items():
                        if hasattr(new_item, k):
                            setattr(new_item, k, v)
                        else:
                            opts[k] = v
                    new_item.options = opts
                elif self.name == "staff":
                    new_item = Staff(id=str(doc_id))
                    for k, v in changes.items():
                        if hasattr(new_item, k):
                            setattr(new_item, k, v)
                elif self.name == "restaurants":
                    new_item = Restaurant(id=str(doc_id))
                    for k, v in changes.items():
                        if hasattr(new_item, k):
                            setattr(new_item, k, v)
                
                if new_item:
                    self.session.add(new_item)
                    self.session.commit()
        except Exception as e:
            logger.error(f"Error in update_one: {e}")
            self.session.rollback()

    def replace_one(self, query, replacement, upsert=False):
        # Emulacja replace_one (używana głównie przy init_db reset)
        doc_id = query.get("_id") or query.get("id")
        if not doc_id: return
        self.update_one(query, {"$set": replacement}, upsert=upsert)

    def insert_one(self, document):
        try:
            doc_id = document.get("_id") or document.get("id")
            if not doc_id:
                doc_id = str(uuid.uuid4())
                document["_id"] = doc_id

            if not self._is_native():
                # Emulacja dla kolekcji nie posiadających własnych tabel (np. sessions, active_tables)
                real_id = self._get_config_id(doc_id)
                data = {k: v for k, v in document.items() if k != "_id" and k != "id"}
                item = self.session.query(AppConfig).filter(AppConfig.id == real_id).first()
                if item:
                    item.data = data
                else:
                    item = AppConfig(id=real_id, data=data)
                    self.session.add(item)
                self.session.commit()
                return

            # Mapowanie na modele SQL
            model = None
            if self.name == "menu": model = MenuItem
            elif self.name == "staff": model = Staff
            elif self.name == "orders": model = Order
            elif self.name == "restaurants": model = Restaurant
            elif self.name == "clients": model = Client
            elif self.name == "pos_history": model = POSHistory
            
            if model:
                clean_doc = {k: v for k, v in document.items() if k != "_id"}
                clean_doc["id"] = str(doc_id)
                
                # Pobierz listy kolumn modelu
                model_cols = [c.name for c in model.__table__.columns]
                final_params = {k: v for k, v in clean_doc.items() if k in model_cols}
                
                # Zapisz nadmiarowe pola do JSON (jeśli model to wspiera)
                leftovers = {k: v for k, v in clean_doc.items() if k not in model_cols and k != "id"}
                if leftovers:
                    if "options" in model_cols:
                        final_params["options"] = leftovers
                    elif "items" in model_cols and not final_params.get("items"):
                        final_params["items"] = leftovers

                obj = model(**final_params)
                self.session.add(obj)
                self.session.commit()
                # print(f"DEBUG: insert_one({self.name}) SUCCESS: {doc_id}")
        except Exception as e:
            logger.error(f"Error in insert_one({self.name}): {e}")
            self.session.rollback()

def get_db():
    """Get database session (Postgres) wrapped in Mongo compatibility layer"""
    try:
        session = SessionLocal()
        # Test the connection immediately
        session.execute(text("SELECT 1"))
        return MongoCompatibility(session)
    except Exception as e:
        logger.error(f"DATABASE CONNECTION FAILURE for {os.environ.get('BRAND', 'UNKNOWN')}: {e}")
        return None
    # Uwaga: Sesja powinna być zamykana przez managera lub w middleware, 
    # ale dla uproszczenia emulacji zostawiamy ją otwartą w wrapie.


# --- STARTUP SEEDING ---
@app.on_event("startup")
async def seed_data():
    """Seed initial staff with master NFC tags"""
    try:
        db = SessionLocal()
        masters = [
            ("Master 1", "0067305985"),
            ("Master 2", "0575292482")
        ]
        for name, nfc in masters:
            existing = db.query(Staff).filter(Staff.nfc_id == nfc).first()
            if not existing:
                new_staff = Staff(
                    id=str(uuid.uuid4())[:8],
                    name=name,
                    nfc_id=nfc,
                    pin="123456", 
                    role="admin", # admin has access to everything
                    is_active=False
                )
                db.add(new_staff)
                logger.info(f"Seeded master NFC: {name}")
        db.commit()
    except Exception as e:
        logger.error(f"Seeding error: {e}")
    finally:
        db.close()

# --- AI CONFIG & GEMINI ---
AI_CONFIG_PATH = APP_DIR / "ai_config.json"
API_KEY = os.environ.get("OVH_AI_ENDPOINTS_ACCESS_TOKEN", "")
AI_MODEL_NAME = "gpt-oss-120b"

def load_ai_config():
    global API_KEY, AI_MODEL_NAME, ai_client
    if AI_CONFIG_PATH.exists():
        try:
            with open(AI_CONFIG_PATH, "r") as f:
                ai_cfg = json.load(f)
                API_KEY = ai_cfg.get("OVH_AI_ENDPOINTS_ACCESS_TOKEN", API_KEY)
                AI_MODEL_NAME = ai_cfg.get("AI_MODEL_NAME", AI_MODEL_NAME)
                print(f"DEBUG: Loaded AI Config: Model={AI_MODEL_NAME}, Key={'CONFIGURED' if API_KEY else 'MISSING'}")
        except Exception as e:
            print(f"ERROR: Could not load ai_config.json: {e}")

    if API_KEY:
        try:
            ai_client = OpenAI(
                base_url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
                api_key=API_KEY
            )
        except Exception as e:
            print(f"ERROR: Could not initialize OpenAI client: {e}")
            ai_client = None
    else:
        ai_client = None

load_ai_config()

# --- AI CACHING ---
AI_CACHE = {} # { "prompt": {"text": "...", "expires": timestamp} }

def get_cached_ai(prompt: str):
    now = datetime.now().timestamp()
    if prompt in AI_CACHE:
        entry = AI_CACHE[prompt]
        if entry["expires"] > now:
            return entry["text"]
    return None

def set_cached_ai(prompt: str, text: str, ttl=86400): # Default 24h
    AI_CACHE[prompt] = {
        "text": text,
        "expires": datetime.now().timestamp() + ttl
    }

STATUS_MAP = {
    "nowe": "W kolejce", 
    "preparing": "W kuchni", 
    "ready": "Gotowe!", 
    "closed": "Wydane"
}

@app.get("/api/get_waiter_joke")
async def get_waiter_joke():
    if not ai_client: return {"joke": "Klient: Kelner, w zupie jest mucha! Kelner: Spokojnie, pająk z drugiego dania już po nią idzie."}
    prompt = "Jesteś doświadczonym, nieco sarkastycznym kelnerem. Napisz 1 krótki, genialny żart o pracy kelnera, gościach lub kuchni. Max 100 znaków. Ma być śmieszne dla personelu!"
    
    cached = get_cached_ai(prompt)
    if cached: return {"joke": cached}

    try:
        response = ai_client.chat.completions.create(
            model=AI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15,
            max_tokens=256,
            extra_body={"reasoning_effort": "low"}
        )
        text = response.choices[0].message.content.strip()
        set_cached_ai(prompt, text)
        return {"joke": text}
    except Exception as e:
        print(f"Błąd AI Joke: {e}")
        return {"joke": "Kelner do klienta: Nasze ślimaki są świeże? Proszę pana, jeden właśnie wygrał wyścig z kucharzem!"}

@app.get("/api/get_joke")
async def get_joke(item: str = "jedzenie"):
    if not ai_client: return {"joke": "Smacznego! Ten burger to legenda."}
    prompt = f"Jesteś Duchem Burgera. Klient wybrał: {item}. Rzuć 1 krótkim żartem. Max 60 znaków."

    cached = get_cached_ai(prompt)
    if cached: return {"joke": cached}

    try:
        response = ai_client.chat.completions.create(
            model=AI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15,
            max_tokens=150,
            extra_body={"reasoning_effort": "low"}
        )
        text = response.choices[0].message.content.strip()
        set_cached_ai(prompt, text)
        return {"joke": text}
    except Exception as e:
        print(f"Błąd AI Get Joke: {e}")
        return {"joke": "Smacznego! Ten burger to legenda."}

@app.get("/api/get_story")
async def get_story(item: str = "burger"):
    if not ai_client: return {"story": "Czy wiesz, że pierwszy burger powstał z potrzeby zjedzenia posiłku w biegu?"}
    prompt = f"Jesteś historykiem kulinarnym. Napisz jedną, fascynującą anegdotę o: {item}. Max 300 znaków. Zakończ kropką."

    cached = get_cached_ai(prompt)
    if cached: return {"story": cached}

    try:
        response = ai_client.chat.completions.create(
            model=AI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15,
            max_tokens=400,
            extra_body={"reasoning_effort": "low"}
        )
        text = response.choices[0].message.content.strip()
        set_cached_ai(prompt, text)
        return {"story": text}
    except Exception as e:
        print(f"Błąd AI Get Story: {e}")
        return {"story": "Czy wiesz, że pierwszy burger powstał z potrzeby zjedzenia posiłku w biegu?"}

@app.get("/api/get_burger_story")
async def get_burger_story(items: Optional[str] = None):
    if not ai_client: return {"story": "Jeden kęs dobrego burgera potrafi przenieść w wymiar prawdziwej rozkoszy gastronomicznej. Chrupiąca bułka i soczyste mięso tworzą kompozycję idealną!"}
    prompt = "Jesteś Duchem Burgera, wesołym i mądrym duchem kuchni. "
    if items:
        prompt += f"Klient zamówił: {items}. Napisz krótką, zabawną anegdotę lub żart związany z tymi produktami. "
    else:
        prompt += "Napisz krótką, pozytywną i ciekawą historię o jedzeniu burgerów. "
    prompt += "Maksymalnie 3 zdania. Ma być śmiesznie, ciepło i kulinarnie. Używaj polskiego. Nie powtarzaj ogólnych cytatów o kęsach i rozkoszy."

    cached = get_cached_ai(prompt)
    if cached: return {"story": cached}

    try:
        response = ai_client.chat.completions.create(
            model=AI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15,
            max_tokens=500,
            extra_body={"reasoning_effort": "low"}
        )
        text = response.choices[0].message.content.strip()
        branding = "\n\n<i>\"Jeden kęs dobrego burgera potrafi przenieść w wymiar prawdziwej rozkoszy gastronomicznej. Chrupiąca bułka i soczyste mięso tworzą kompozycję idealną.\"</i>"
        full_story = text + branding
        set_cached_ai(prompt, full_story)
        return {"story": full_story}
    except Exception as e:
        print(f"Błąd AI Story: {e}")
        return {"story": "Jeden kęs dobrego burgera potrafi przenieść w wymiar prawdziwej rozkoszy gastronomicznej. Chrupiąca bułka i soczyste mięso tworzą kompozycję idealną!"}

@app.get("/api/get_order_knowledge")
async def get_order_knowledge(items: Optional[str] = None):
    """Generuje historyczną wiedzę edukacyjną o zamawianym jedzeniu (zamiast żartów)."""
    if not ai_client:
        return {"knowledge": "Czy wiesz, że burger jest jednym z najpopularniejszych posiłków na świecie? Historia sięga XIX wieku!"}

    prompt = "Jesteś znawcą historii kulinarnej i edukujesz gości o pochodzeniu i ciekawostkach jedzenia. "
    if items:
        prompt += f"Gość zamówił: {items}. Napisz JEDNĄ, KRÓTKĄ ciekawostkę historyczną lub edukacyjną o tych produktach. "
    else:
        prompt += "Napisz jedną fascynującą historyczną ciekawostkę o burgerach. "

    prompt += "Max 2 zdania. Bądź edukacyjny, ciekawy i entuzjastyczny. Używaj polskiego. Unikaj generycznych cytatów."

    cached = get_cached_ai(prompt)
    if cached: return {"knowledge": cached}

    try:
        response = ai_client.chat.completions.create(
            model=AI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
            extra_body={"reasoning_effort": "low"}
        )
        text = response.choices[0].message.content.strip()
        set_cached_ai(prompt, text)
        return {"knowledge": text}
    except Exception as e:
        print(f"Błąd AI Knowledge: {e}")
        return {"knowledge": "Pierwszy burger odbył wokół 1900 roku w USA! 🍔"}


@app.get("/api/dash/ai_config")
async def get_dash_ai_config(master_pin: str):
    with open("config.json", "r") as f:
        cfg = json.load(f)
        if master_pin != cfg.get("master_pin", "1234"): raise HTTPException(401, "Invalid PIN")
    
    load_ai_config()
    safe_key = f"{API_KEY[:4]}***{API_KEY[-4:]}" if API_KEY and len(API_KEY) > 8 else ""
    return {
        "AI_MODEL_NAME": AI_MODEL_NAME,
        "MASKED_KEY": safe_key,
        "STATUS": "OK" if ai_client else "NOT INITIALIZED"
    }

@app.post("/api/dash/ai_config")
async def post_dash_ai_config(request: Request):
    data = await request.json()
    master_pin = data.get("master_pin")
    with open("config.json", "r") as f:
        cfg = json.load(f)
        if master_pin != cfg.get("master_pin", "1234"): return {"error": "Invalid PIN"}
        
    new_model = data.get("AI_MODEL_NAME")
    new_key = data.get("GEMINI_API_KEY")
    
    ai_cfg = {}
    if AI_CONFIG_PATH.exists():
        with open(AI_CONFIG_PATH, "r", encoding="utf-8") as f:
            ai_cfg = json.load(f)
            
    if new_model: ai_cfg["AI_MODEL_NAME"] = new_model
    if new_key: ai_cfg["OVH_AI_ENDPOINTS_ACCESS_TOKEN"] = new_key
    
    with open(AI_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(ai_cfg, f, indent=4)
        
    load_ai_config()
    return {"ok": True}

class AITestRequest(BaseModel):
    master_pin: str
    model: Optional[str] = None
    token: Optional[str] = None

@app.post("/api/dash/ai_test")
async def dash_ai_test(payload: AITestRequest):
    with open("config.json", "r") as f:
        cfg = json.load(f)
        if payload.master_pin != cfg.get("master_pin", "1234"): return {"error": "Invalid PIN"}
        
    test_key = payload.token or API_KEY
    if not test_key: return {"error": "Brak tokenu AI. Check API Key."}
    
    test_model = payload.model or AI_MODEL_NAME
    try:
        from openai import OpenAI
        test_client = OpenAI(
            base_url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
            api_key=test_key
        )
        res = test_client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Return exactly: READY"}]
        )
        return {"response": res.choices[0].message.content.strip()}
    except Exception as e:
        return {"error": str(e)}

# --- STAFF MANAGEMENT & PIN AUTH ---

@app.post("/api/admin/save_staff")
async def save_staff(request: Request):
    """Saves or updates staff members. PIN is now a field, allowing shared PINs."""
    try:
        data = await request.json()
        name = data.get("name")
        pin = str(data.get("pin"))
        role = data.get("role")
        
        if not name or not pin or len(pin) < 4:
            return {"ok": False, "error": "Imię i PIN (min. 4 cyfry) są wymagane."}
            
        print(f"DEBUG: Saving staff: {name}, Role: {role}")

        # We use name as the document ID for personality, but PIN is searchable.
        # This allows different names to have the same PIN.
        get_db()["staff"].replace_one({"_id": name}, {
            "_id": name,
            "name": name,
            "pin": pin,
            "role": role,
            "updated_at": datetime.now(timezone.utc)
        }, upsert=True)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"Błąd zapisu: {str(e)}"}

@app.get("/api/admin/get_staff")
async def get_staff():
    """Returns all staff members with their full data."""
    conn = get_db()
    if not conn: return []
    try:
        staff_docs = conn["staff"].find({})
        return [doc for doc in staff_docs]
    except Exception as e:
        print(f"ERROR: get_staff failed: {e}")
        return []
@app.post("/api/admin/delete_order/{order_id}")
async def delete_order(order_id: str):
    database = get_db()
    if database is not None:
        database["orders"].delete_one({"_id": order_id})
    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}

@app.post("/api/mark_paid_no_fiscal/{table_num}")
async def mark_paid_no_fiscal(table_num: str):
    # Logika identyczna jak mark_paid, ale NIE zapisuje "last_receipt" i nie wysyła typu "receipt"
    database = get_db()
    if database is not None:
        table_ref = database["active_tables"].find_one({"_id": table_num})
        if table_ref:
            session = table_ref.get("session_id")
            docs = database["orders"].find({"table_number": table_num, "session_id": session})
            order_ids = [d["_id"] for d in docs]
            if order_ids:
                database["orders"].update_many({"_id": {"$in": order_ids}}, {"$set": {"paid": True}})
        database["active_tables"].delete_one({"_id": table_num})  # Zwalniamy stolik
    else:
        # Fallback to in-memory storage if DB unavailable
        pass
    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}
    
@app.post("/api/admin/delete_staff")
async def delete_staff(request: Request):
    """Deletes a staff member by name."""
    conn = get_db()
    if conn is None: return {"ok": False, "error": "Baza danych niedostępna"}

    try:
        data = await request.json()
        name = data.get("name")
        if not name:
            return {"ok": False, "error": "Brak imienia do usunięcia."}

        conn["staff"].delete_one({"_id": name})
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/auth/staff_login")
async def staff_login(request: Request):
    """Expert login handler supporting shared PINs and personalized selection."""
    conn = get_db()
    if conn is None:
        # Emergency access if DB is down
        data = await request.json()
        pin = str(data.get("pin"))
        if pin == "019283": return {"ok": True, "name": "MASTER (DB DOWN)", "role": "master"}
        if pin == "102938": return {"ok": True, "name": "ADMIN (DB DOWN)", "role": "admin"}
        return {"ok": False, "error": "Baza danych niedostępna. Użyj kodu ratunkowego."}

    try:
        data = await request.json()
        pin = str(data.get("pin"))
        name = data.get("name")

        # Hardcoded overrides for recovery/initial setup
        if pin == "019283":
            return {"ok": True, "name": "MASTER", "role": "master"}
        if pin == "102938":
            return {"ok": True, "name": "ADMIN", "role": "admin"}

        # 1. Search by PIN field
        staff_query = conn["staff"].find({"pin": pin})
        matches = [doc for doc in staff_query]

        # 2. Add backward compatibility search (where doc.id was the PIN)
        if not matches:
            compat_doc = conn["staff"].find_one({"_id": pin})
            if compat_doc:
                d = compat_doc
                if not d.get("name"): d["name"] = f"User-{pin}" # Fallback
                matches.append(d)

        if not matches:
            return {"ok": False, "error": "Nieprawidłowy PIN."}

        if name:
            match = next((m for m in matches if m.get("name") == name), None)
            if match:
                return {"ok": True, "name": match["name"], "role": match["role"]}
            return {"ok": False, "error": "PIN nie pasuje do wybranego pracownika."}

        if len(matches) == 1:
            return {"ok": True, "name": matches[0]["name"], "role": matches[0]["role"]}
        
        return {
            "ok": False,
            "error": "AMBIGUOUS",
            "names": [m["name"] for m in matches]
        }
    except Exception as e:
        return {"ok": False, "error": f"Błąd autoryzacji: {str(e)}"}

# --- ROLE-BASED ACCESS CONTROL ---
def check_role_access(required_role: str, auth_role: Optional[str] = None):
    """Check if user has required role access"""
    if not auth_role:
        return False
    
    # Define role hierarchy (higher roles can access lower roles)
    role_hierarchy = {
        "master": ["master"],
        "admin": ["master", "admin"],
        "waiter": ["master", "admin", "waiter"],
        "wydawka": ["master", "admin", "wydawka"],
        "kds": ["master", "admin", "kds"],
        "client": ["master", "admin", "client"],
        "foodtruck": ["master", "admin", "foodtruck"]
    }
    
    return auth_role in role_hierarchy.get(required_role, [])

@app.get("/api/auth/staff_list")
async def staff_list():
    """Zwraca listę pracowników (bez PINów) do wyświetlenia na ekranie logowania."""
    conn = get_db()
    if conn is None: return []

    staff = []
    for doc in conn["staff"].find({}):
        staff.append({
            "name": doc.get("name"),
            "role": doc.get("role")
        })
    return sorted(staff, key=lambda x: x.get("name", ""))


# --- MENU & LAYOUT ---

@app.get("/api/get_menu")
async def get_menu():
    conn = get_db()
    if conn is None: return {}

    menu_dict = {d["_id"]: {k: v for k, v in d.items() if k != "_id"} for d in conn["menu"].find({})}
    return dict(sorted(menu_dict.items(), key=lambda x: int(x[1].get('sort_order', 99))))


def get_brand(request: Request = None):
    # 0. ENV override
    env_brand = os.environ.get("BRAND")
    if env_brand: return env_brand
    
    # 1. Dynamic from subdomain (e.g. bar.zjedz.it -> BAR)
    if request:
        host = request.url.hostname
        if host and "zjedz.it" in host:
            parts = host.split('.')
            if len(parts) >= 3:
                return parts[0].upper()
    
    return "ZJEDZ.IT"

@app.get("/api/get_layout")
async def get_layout():
    conn = get_db()
    mode = get_system_mode()
    
    # In Food Truck mode, always provide 30 virtual slots if layout is empty or generic
    if mode == "foodtruck":
        tables = []
        for i in range(1, 31):
            row = (i - 1) // 5
            col = (i - 1) % 5
            tables.append({"n": str(i), "x": col * 1.5 + 0.5, "y": row * 1.5 + 0.5})
        return {"width": 8.5, "height": 10, "tables": tables}

    if conn is None:
        return {"width": 10, "height": 10, "tables": []}
    
    doc = conn["config"].find_one({"_id": "floor_plan"})
    if doc:
        return {k: v for k, v in doc.items() if k != "_id"}
    return {"width": 10, "height": 10, "tables": []}

@app.post("/api/admin/save_layout")
async def save_layout(request: Request):
    conn = get_db()
    if conn is None:
        return JSONResponse(status_code=500, content={"ok": False, "error": "Database not connected"})
        
    try:
        payload = await request.json()
        print(f"DEBUG: Saving layout: {len(payload.get('tables', []))} tables")
        conn["config"].update_one({"_id": "floor_plan"}, {"$set": payload}, upsert=True)
        await manager.broadcast(json.dumps({"type": "update"}))
        return {"ok": True}
    except Exception as e:
        print(f"ERROR: Save layout failed: {str(e)}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

# --- AUTHENTICATION & ROLES ---

@app.post("/api/admin/set_role")
async def set_role(request: Request):
    data = await request.json()
    auth_role = data.get("auth_role")
    if not check_role_access("admin", auth_role): return {"error": "Brak uprawnień"}

    target_email = data.get("email")
    new_role = data.get("role")
    if not target_email: return {"error": "Brak email"}
    if auth_role == "admin" and new_role == "admin": return {"error": "Admin nie może nadać roli Admina"}

    conn = get_db()
    if conn is not None:
        conn["users"].update_one({"_id": target_email}, {"$set": {"role": new_role}}, upsert=True)
    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}

@app.post("/api/admin/reset_day")
async def reset_day(request: Request):
    data = await request.json()
    auth_role = data.get("auth_role")
    if auth_role not in ["master", "admin"]: return {"error": "Brak uprawnień"}

    conn = get_db()
    if conn is None: return {"error": "Baza danych niedostępna"}


    # 1. Usuwamy aktywne stoliki
    conn["active_tables"].delete_many({})

    # 2. Usuwamy aktywne zamówienia (status != "closed")
    conn["orders"].delete_many({"status": {"$ne": "closed"}})

    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}

@app.post("/api/admin/wipe_db")
async def wipe_db(request: Request):
    data = await request.json()
    auth_role = data.get("auth_role")
    if auth_role != "master": return {"error": "Tylko MASTER może wyczyścić bazę!"}

    collections_to_wipe = ["menu", "active_tables", "orders", "config", "pos_history", "ratings", "staff"]

    conn = get_db()
    if conn is None: return {"error": "Baza danych niedostępna"}
    for coll in collections_to_wipe:
        docs = conn[coll].find({})
        ids_to_delete = []
        for doc in docs:
            # Zachowaj mapę sali domyślnie, aby nie rzucała błędów
            if coll == "config" and doc["_id"] == "floor_plan": continue
            # Zachowaj uzytkownikow master i admin
            if coll == "staff":
                doc_data = doc or {}
                role = doc_data.get("role", "")
                if role in ["master", "admin"] or doc["_id"] in ["master", "admin"]:
                    continue

            ids_to_delete.append(doc["_id"])
            if len(ids_to_delete) >= 400:
                conn[coll].delete_many({"_id": {"$in": ids_to_delete}})
                ids_to_delete = []
        if ids_to_delete:
            conn[coll].delete_many({"_id": {"$in": ids_to_delete}})

    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}

# --- DATABASE MANAGEMENT (INIT / EXPORT / IMPORT) ---

@app.post("/api/admin/init_db")
async def init_db(request: Request):
    data = await request.json()
    auth_role = data.get("auth_role")
    if auth_role != "master": return {"error": "Tylko MASTER może inicjalizować bazę!"}

    # Rozszerzone menu z kategoriami
    default_menu = {
        # === DANIA GŁÓWNE ===
        "burger_elvis": {
            "name": "Elvis Burger", "price": 38.0, "category": "Dania Główne",
            "description": "Klasyka z bekonem i serem cheddar. 200g wołowiny, chrupiący boczek, sos Elvis.",
            "allergens": "gluten, mleko", "kcal": "650", "weight": "320",
            "sort_order": 1, "to_kitchen": True, "no_rating": False
        },
        "burger_dynamite": {
            "name": "Dynamite Burger", "price": 42.0, "category": "Dania Główne",
            "description": "Pikantny z jalapeño i sosem dynamite. 220g wołowiny, pepper jack.",
            "allergens": "gluten, mleko", "kcal": "720", "weight": "340",
            "sort_order": 2, "to_kitchen": True, "no_rating": False
        },
        "burger_cheese": {
            "name": "Double Cheese", "price": 36.0, "category": "Dania Główne",
            "description": "Podwójny ser, podwójna przyjemność. 180g wołowiny, podwójny cheddar.",
            "allergens": "gluten, mleko", "kcal": "580", "weight": "280",
            "sort_order": 3, "to_kitchen": True, "no_rating": False
        },
        
        # === PRZEKĄSKI ===
        "frytki": {
            "name": "Frytki Belgijskie", "price": 14.0, "category": "Przekąski",
            "description": "Chrupiące, z solą morską. Podawane z sosem do wyboru.",
            "allergens": "", "kcal": "280", "weight": "180",
            "sort_order": 10, "to_kitchen": True, "no_rating": False
        },
        "onion_rings": {
            "name": "Onion Rings", "price": 16.0, "category": "Przekąski",
            "description": "Krwiszki cebulowe w chrupiącej panierce. 6 sztuk.",
            "allergens": "gluten", "kcal": "320", "weight": "160",
            "sort_order": 11, "to_kitchen": True, "no_rating": False
        },
        "nuggets": {
            "name": "Nuggets (6szt)", "price": 18.0, "category": "Przekąski",
            "description": "Kurczak w chrupiącej panierce. 6 sztuk z dipem.",
            "allergens": "gluten", "kcal": "380", "weight": "200",
            "sort_order": 12, "to_kitchen": True, "no_rating": False
        },
        "salad": {
            "name": "Sałatka Sezonowa", "price": 22.0, "category": "Przekąski",
            "description": "Świeże warzywa, feta, sos balsamiczny. Wegańska opcja.",
            "allergens": "", "kcal": "120", "weight": "250",
            "sort_order": 13, "to_kitchen": True, "no_rating": True
        },
        
        # === NAPOJE ===
        "cola": {
            "name": "Coca-Cola", "price": 8.0, "category": "Napoje",
            "description": "0.33l - Klasyczny smak orzeźwiający.",
            "allergens": "", "kcal": "140", "weight": "330",
            "sort_order": 20, "to_kitchen": False, "no_rating": True
        },
        "cola_zero": {
            "name": "Coca-Cola Zero", "price": 8.0, "category": "Napoje",
            "description": "0.33l - Zero cukru, pełny smak.",
            "allergens": "", "kcal": "0", "weight": "330",
            "sort_order": 21, "to_kitchen": False, "no_rating": True
        },
        "sprite": {
            "name": "Sprite", "price": 8.0, "category": "Napoje",
            "description": "0.33l - Cytrusowa orzeźwienie.",
            "allergens": "", "kcal": "130", "weight": "330",
            "sort_order": 22, "to_kitchen": False, "no_rating": True
        },
        "fanta": {
            "name": "Fanta Orange", "price": 8.0, "category": "Napoje",
            "description": "0.33l - Pomarańczowa rozgrzewka.",
            "allergens": "", "kcal": "135", "weight": "330",
            "sort_order": 23, "to_kitchen": False, "no_rating": True
        },
        "water": {
            "name": "Woda 0.5l", "price": 6.0, "category": "Napoje",
            "description": "0.5l - Woda źródlana gazowana.",
            "allergens": "", "kcal": "0", "weight": "500",
            "sort_order": 24, "to_kitchen": False, "no_rating": True
        },
        "juice": {
            "name": "Sok Pomarańczowy", "price": 10.0, "category": "Napoje",
            "description": "0.3l - Świeżo wyciskany sok.",
            "allergens": "", "kcal": "110", "weight": "300",
            "sort_order": 25, "to_kitchen": False, "no_rating": True
        },
        
        # === DESERY ===
        "brownie": {
            "name": "Brownie z lodami", "price": 18.0, "category": "Desery",
            "description": "Czekoladowe brownie, 2 kulki lodów waniliowych, polewa.",
            "allergens": "gluten, mleko, jaja", "kcal": "450", "weight": "180",
            "sort_order": 30, "to_kitchen": False, "no_rating": False
        },
        "icecream": {
            "name": "Lody Gałki (3)", "price": 12.0, "category": "Desery",
            "description": "3 gałki lodów do wyboru: wanilia, czekolada, truskawka.",
            "allergens": "mleko", "kcal": "220", "weight": "120",
            "sort_order": 31, "to_kitchen": False, "no_rating": True
        },
        "shake": {
            "name": "Shake Czekoladowy", "price": 16.0, "category": "Desery",
            "description": "0.4l - Kremowy shake z lodami czekoladowymi.",
            "allergens": "mleko", "kcal": "380", "weight": "400",
            "sort_order": 32, "to_kitchen": False, "no_rating": True
        }
    }
    conn = get_db()
    if conn is None: return {"error": "Baza danych niedostępna"}
    for k, v in default_menu.items():
        conn["menu"].update_one({"_id": str(k)}, {"$set": v}, upsert=True)

    # Przykładowa mapa sali (1 stolik)
    default_layout = {
        "_id": "floor_plan",
        "width": 10, "height": 10,
        "tables": [{"id": 1, "x": 2, "y": 2, "label": "Stół 1"}]
    }
    get_db()["config"].replace_one({"_id": "floor_plan"}, default_layout, upsert=True)

    # Domyślny personel
    get_db()["staff"].replace_one({"_id": "102938"}, {"_id": "102938", "name": "ADMIN", "role": "admin"}, upsert=True)

    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True, "message": "Baza zainicjalizowana domyślnymi danymi (menu z kategoriami: Dania Główne, Przekąski, Napoje, Desery)."}

@app.get("/api/admin/export_db")
async def export_db(auth_role: Optional[str] = None):
    if not check_role_access("master", auth_role): return JSONResponse({"error": "Brak uprawnień"}, status_code=403)

    collections = ["menu", "staff", "users", "config", "active_tables", "orders"]
    export_data = {}

    conn = get_db()
    if conn is None: return {"error": "Baza danych niedostępna"}
    for coll_name in collections:
        docs = conn[coll_name].find({})
        export_data[coll_name] = {str(d["_id"]): {k: v for k, v in d.items() if k != "_id"} for d in docs}

    return export_data

@app.post("/api/admin/import_db")
async def import_db(request: Request):
    data = await request.json()
    auth_role = data.get("auth_role")
    payload = data.get("payload")
    if auth_role != "master": return {"error": "Brak uprawnień"}
    if not payload: return {"error": "Brak danych do importu"}

    conn = get_db()
    if conn is None: return {"error": "Baza danych niedostępna"}
    for coll_name, docs in payload.items():
        for doc_id, doc_data in docs.items():
            # ... (timestamp conversion code)
            conn[coll_name].replace_one({"_id": doc_id}, {"_id": doc_id, **doc_data}, upsert=True)

    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}


@app.get("/api/admin/get_users")
async def get_users():
    conn = get_db()
    if conn is None: return []
    return [{"email": str(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}} for d in conn["users"].find({})]

@app.post("/api/admin/set_password")
async def set_password(request: Request):
    data = await request.json()
    auth_role = data.get("auth_role")
    if auth_role not in ["master", "admin"]: return {"error": "Brak uprawnień"}

    view = data.get("view")
    pwd = data.get("password")
    conn = get_db()
    if conn is not None:
        conn["config"].update_one({"_id": "passwords"}, {"$set": {f"{view}_pwd": pwd}}, upsert=True)
    return {"ok": True}

@app.post("/api/auth/verify_password")
async def verify_pwd(request: Request):
    data = await request.json()
    view = data.get("view")
    pwd = data.get("password")
    conn = get_db()
    doc = conn["config"].find_one({"_id": "passwords"}) if conn else None
    correct = doc.get(f"{view}_pwd") if doc else None
    if not correct: return {"ok": True}
    return {"ok": pwd == correct}

@app.post("/api/admin/save_product")
async def save_product(
    key: str = Form(...), name: str = Form(...), price: float = Form(...), description: str = Form(""),
    allergens: str = Form(""), kcal: str = Form(""), weight: str = Form(""),
    sort_order: int = Form(10), to_kitchen: str = Form("true"), no_rating: str = Form("false"),
    category: str = Form(""),
    file: Optional[UploadFile] = File(None),
    auth_role: Optional[str] = Form(None)
):
    # Skip role check for now if not provided, to maintain backward compatibility,
    # but ideally we should require it.
    if auth_role and not check_role_access("admin", auth_role):
        return JSONResponse({"ok": False, "error": "Brak uprawnień admina."}, status_code=403)

    try:
        database = get_db()
        if database is None:
            return JSONResponse({"ok": False, "error": "Brak połączenia z bazą danych."}, status_code=500)

        print(f"DEBUG: Saving product {key}, Name: {name}, Price: {price}, NoRating: {no_rating}")
        is_kitchen = str(to_kitchen).lower() == "true"
        is_no_rating = str(no_rating).lower() == "true"
        
        update_data = {
            "name": name, "price": float(price), "description": description, "allergens": allergens,
            "kcal": kcal, "weight": weight, "sort_order": int(sort_order), 
            "to_kitchen": is_kitchen, "no_rating": is_no_rating, "category": category
        }
        
        if file and file.filename:
            img_dir = APP_DIR / "static" / "images"
            try:
                img_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create image directory: {e}")
                return JSONResponse({"ok": False, "error": f"Błąd systemu plików: {e}"}, status_code=500)
            
            # Use UUID to avoid filename collisions and special char issues
            original_filename = file.filename
            extension = Path(original_filename).suffix or ".jpg"
            new_filename = f"prod_{uuid.uuid4().hex[:8]}{extension}"
            
            try:
                content = await file.read()
                filepath = img_dir / new_filename
                with open(filepath, "wb+") as f: 
                    f.write(content)
                update_data["image"] = new_filename
                logger.info(f"Saved new image: {new_filename} for product {key}")
            except Exception as e:
                logger.error(f"Error saving image file: {e}")
                return JSONResponse({"ok": False, "error": f"Błąd zapisu pliku: {e}"}, status_code=500)
            
        database["menu"].update_one({"_id": str(key)}, {"$set": update_data}, upsert=True)
        await manager.broadcast(json.dumps({"type": "update"}))
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error in save_product: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": f"Błąd serwera: {str(e)}"}, status_code=500)


# --- TABLES & CALLS ---

@app.get("/api/admin/debug_sql")
async def debug_sql():
    try:
        with get_db() as db:
            orders = list(db["orders"].find({}))
            actives = list(db["active_tables"].find({}))
            return {
                "orders_count": len(orders),
                "actives_count": len(actives),
                "raw_orders": orders[:5],
                "raw_actives": actives[:5]
            }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/active_tables")
async def active_tables():
    conn = get_db()
    if conn is None: return {"tables": []}

    return {"tables": [{k: v for k, v in d.items() if k != "_id"} for d in conn["active_tables"].find({})]}

@app.post("/api/call_waiter/{table_num}")
async def call_waiter(table_num: str):
    conn = get_db()
    if conn is not None:
        conn["active_tables"].update_one({"_id": str(table_num)}, {"$set": {"call_waiter": True}}, upsert=True)
    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}

@app.post("/api/pay_request/{table_num}")
async def pay_request(table_num: str):
    conn = get_db()
    if conn is not None:
        conn["active_tables"].update_one({"_id": str(table_num)}, {"$set": {"pay_request": True}}, upsert=True)
    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}

@app.post("/api/reset_call/{table_num}")
async def reset_call(table_num: str):
    conn = get_db()
    if conn is not None:
        conn["active_tables"].update_one({"_id": str(table_num)}, {"$set": {"call_waiter": False, "pay_request": False}}, upsert=True)
    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}


# --- ORDERS ---

@app.post("/api/update_status/{id}")
async def update_status(id: str, request: Request):
    try:
        conn = get_db()
        if conn is None: return {"error": "Baza danych niedostępna"}
        payload = await request.json()
        conn["orders"].update_one({"_id": id}, {"$set": {"status": payload.get("status")}})
        await manager.broadcast(json.dumps({"type": "update"}))
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/soft_pay/{table_num}")
async def soft_pay(table_num: str):
    """Marks all orders for this table/session as paid without printing/history."""
    conn = get_db()
    if conn is None: return {"error": "DB offline"}
    table_str = str(table_num)
    
    table_ref = conn["active_tables"].find_one({"_id": table_str})
    if not table_ref: return {"error": "Nieaktywny stolik"}
    current_session = table_ref.get("session_id")
    
    conn["orders"].update_many(
        {"table_number": table_str, "session_id": current_session},
        {"$set": {"paid": True}}
    )
    conn["active_tables"].update_one({"_id": table_str}, {"$set": {"pay_request": False}})
    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}

@app.post("/api/orders")
async def add_order(order: dict):
    try:
        table_num = str(order.get("table_number"))
        current_session = order.get("session_id")
        conn = get_db()
        if conn is None: return {"error": "Database disconnected"}


        if not current_session:
            table_ref = conn["active_tables"].find_one({"_id": table_num})

            current_session = table_ref.get("session_id") if table_ref else "unknown"

        # Bezpieczniejsza konwersja ceny
        price_val = order.get("price", 0.0)
        try:
            price_val = float(price_val)
        except ValueError:
            price_val = 0.0

        with get_db() as conn:
            # Ensure table is in active_tables
            table_doc = conn["active_tables"].find_one({"_id": table_num})
            if not table_doc or table_doc.get("session_id") != current_session:
                conn["active_tables"].update_one({"_id": table_num}, {"$set": {
                    "table_number": table_num,
                    "session_id": current_session,
                    "timestamp": datetime.now(timezone.utc)
                }}, upsert=True)

            order_data = {
                "_id": str(uuid.uuid4()),
                "table_number": table_num,
                "burger_name": order.get("burger_name"),
                "price": price_val,
                "status": "nowe",
                "paid": False,
                "session_id": current_session,
                "timestamp": datetime.now(timezone.utc),
                "note": order.get("note", ""),
                "to_kitchen": order.get("to_kitchen", True)
            }
            conn["orders"].insert_one(order_data)
            
        await manager.broadcast(json.dumps({"type": "update"}))
        await manager.broadcast(json.dumps({"type": "NEW_ORDER"}))
        return {"ok": True}

    except Exception as e:
        print("Błąd dodawania zamówienia:", e)
        return {"error": str(e)}

# BARDZO WAŻNE: Poniższej funkcji brakowało w przesłanym kodzie!
@app.get("/api/all_orders")
async def get_all_orders():
    try:
        with get_db() as conn:
            docs = conn["orders"].find({}).sort("timestamp", -1).limit(100)
            orders = []
            for d in docs:
                data = {k: v for k, v in d.items() if k != "_id"}
                data["id"] = str(d["_id"])
                if "to_kitchen" not in data:
                    menu_ref = conn["menu"].find_one({"_id": data.get("burger_name", "")})
                    data["to_kitchen"] = menu_ref.get("to_kitchen", True) if menu_ref else True
                if data.get("timestamp") and isinstance(data["timestamp"], datetime):
                    data["timestamp"] = data["timestamp"].isoformat()
                orders.append(data)
            return {"orders": orders}
    except Exception as e:
        logger.error(f"Error in all_orders: {e}")
        return {"orders": [], "error": str(e)}

@app.get("/api/admin/floor_layout")
async def get_floor_layout():
    if get_system_mode() == "foodtruck":
        return {"tables": [{"id": i, "x": 0, "y": 0} for i in range(1, 31)]}
    try:
        with get_db() as db:
            config = db["config"].find_one({"_id": "floor_layout"})
            return config if config else {"tables": []}
    except Exception as e:
        print("Błąd pobierania zamówień:", e)
        return {"error": str(e), "orders": []}

@app.post("/api/mark_paid/{table_num}")
async def mark_paid(table_num: str, request: Request):
    """Marks orders as paid and triggers POS printing via JSON."""
    data = await request.json()
    fiscal = data.get("fiscal", True)
    table_str = str(table_num)
    conn = get_db()
    if conn is None: return {"error": "Database disconnected"}

    table_ref = conn["active_tables"].find_one({"_id": table_str})

    if not table_ref:
        # Próba odzyskania sesji z zamówień jeśli brak w aktywnej tablicy (np. Wynos)
        last_order = conn["orders"].find({"table_number": table_str}).sort("timestamp", -1).limit(1)
        last_order_list = list(last_order)
        if last_order_list:
            current_session = last_order_list[0].get("session_id")
            print(f"DEBUG: Recovered session {current_session} for table {table_str} from orders")
        else:
            return {"error": "Brak aktywnej sesji dla tego stolika"}
    else:
        current_session = table_ref.get("session_id")

    # If foodtruck mode, we might want to print ALL items even if they were 'soft-paid' earlier.
    # But usually, it prints only Unpaid. 
    # Let's ensure it handles both scenarios.
    
    docs = list(conn["orders"].find({"table_number": table_str, "session_id": current_session, "paid": False}))
    if not docs:
        # If nothing is 'unpaid', check if we need to print 'already paid' items (for foodtruck wydaj logic)
        docs = list(conn["orders"].find({"table_number": table_str, "session_id": current_session}))

    found = False
    orders_to_print = []
    order_ids_to_update = []
    for d in docs:
        order_ids_to_update.append(d["_id"])
        order_data = {k: v for k, v in d.items() if k != "_id"}
        order_data["id"] = d["_id"]
        orders_to_print.append(order_data)
        found = True

    if found:
        print(f"DEBUG: Updating orders for table {table_str}")
        conn["orders"].update_many({"_id": {"$in": order_ids_to_update}}, {"$set": {"paid": True}})
        # Save to POS history
        history_id = f"pos_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{table_str}"
        print(f"DEBUG: Creating History Entry: {history_id}")
        conn["pos_history"].insert_one({
            "_id": history_id,
            "table_number": table_str,
            "session_id": current_session,
            "items": orders_to_print,
            "total": sum(float(i.get("price", 0)) for i in orders_to_print),
            "fiscal": fiscal,
            "timestamp": datetime.now(timezone.utc)
        })

    # Reset pay request and call waiter flags
    conn["active_tables"].update_one(
        {"_id": table_str}, 
        {"$set": {"pay_request": False, "call_waiter": False}}, 
        upsert=True
    )
    
    await manager.broadcast(json.dumps({"type": "update"}))

    if orders_to_print:
        total = sum(float(i.get("price", 0)) for i in orders_to_print)
        receipt_data = {
            "table_number": table_str,
            "items": orders_to_print,
            "total": total,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_key": "Elvis_KWI_0326",
            "fiscal": fiscal,
            "receipt_id": history_id
        }
        conn["config"].update_one({"_id": "last_receipt"}, {"$set": receipt_data}, upsert=True)

        msg = {"type": "receipt", **receipt_data}
        print(f"DEBUG: Broadcasting {msg['type']} (fiscal={fiscal}) to clients")
        await manager.broadcast(json.dumps(msg))

    return {"ok": True, "waiting_for_ack": fiscal}

@app.get("/api/admin/last_receipt")
async def get_last_receipt():
    doc = get_db()["config"].find_one({"_id": "last_receipt"})
    return {k: v for k, v in doc.items() if k != "_id"} if doc else {"error": "Brak danych"}

@app.post("/api/admin/resend_receipt")
async def resend_receipt(payload: dict):
    # Dopisujemy typ receipt by T520 wiedziało co z tym zrobić
    payload["type"] = "receipt"
    await manager.broadcast(json.dumps(payload))
    return {"ok": True}

@app.get("/api/admin/print_history")
async def get_print_history():
    """Returns the last 50 fiscal/non-fiscal print jobs from pos_history."""
    database = get_db()
    if database is None:
        logger.error("Database connection failed during get_print_history")
        return [] # Return empty list if DB is down
        
    try:
        docs = database["pos_history"].find({}).sort("timestamp", -1).limit(50)
        history = []
        for d in docs:
            data = {k: v for k, v in d.items() if k != "_id"}
            data["id"] = str(d["_id"])
            if data.get("timestamp") and isinstance(data["timestamp"], datetime):
                data["timestamp"] = data["timestamp"].isoformat()
            history.append(data)
        return history
    except Exception as e:
        logger.error(f"Error in get_print_history: {e}")
        return []


# --- WYDAWKA API ---

@app.get("/api/wydawka/bony")
async def get_wydawka_bony():
    conn = get_db()
    if conn is None: return {"do_oplacenia": [], "gotowe_do_wydania": []}
    
    docs = conn["orders"].find({"status": {"$in": ["nowe", "preparing", "ready"]}})
    grouped_orders = defaultdict(list)
    for d in docs:
        data = {k: v for k, v in d.items() if k != "_id"}
        data["id"] = str(d["_id"])
        key = f"{data.get('table_number')}_{data.get('session_id')}"
        grouped_orders[key].append(data)

    do_oplacenia = []
    gotowe_do_wydania = []
    for key, items in grouped_orders.items():
        total_price = sum(float(item.get("price", 0)) for item in items)
        is_unpaid = any(item.get("paid") == False for item in items or item.get("paid") is None)
        is_ready = all(item.get("status") == "ready" for item in items)
        bon_id = str(abs(hash(items[0].get("session_id", "brak"))))[:3]

        # Find the oldest timestamp in this session to calculate accurate wait time
        valid_timestamps = [item.get("timestamp") for item in items if item.get("timestamp")]
        oldest_ts = min(valid_timestamps) if valid_timestamps else None

        ticket = {
            "bon_id": f"#{bon_id}",
            "table_number": items[0].get("table_number"),
            "session_id": items[0].get("session_id"),
            "items": items,
            "total_price": total_price,
            "is_unpaid": is_unpaid,
            "timestamp": oldest_ts.isoformat() if oldest_ts and hasattr(oldest_ts, 'isoformat') else str(oldest_ts) if oldest_ts else None
        }
        if is_ready: gotowe_do_wydania.append(ticket)
        else: do_oplacenia.append(ticket)

    return {"do_oplacenia": do_oplacenia, "gotowe_do_wydania": gotowe_do_wydania}

@app.post("/api/wydawka/wydaj_bon")
async def wydaj_bon(payload: dict):
    conn = get_db()
    if conn is None: return {"error": "Baza danych niedostępna"}
    session_id = payload.get("session_id")
    table_number = str(payload.get("table_number"))
    conn["orders"].update_many({"table_number": table_number, "session_id": session_id, "status": "ready"}, {"$set": {"status": "closed"}})
    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True}

@app.get("/api/admin/stats")
async def admin_stats(start_date: str, end_date: str):
    try:
        with get_db() as conn:
            docs = list(conn["orders"].find({}))
            revenue = 0.0
            revenue_fiscal = 0.0
            revenue_non_fiscal = 0.0
            products = defaultdict(int)

            # Pobieramy historię POS dla dokładniejszych statystyk fiskalnych
            pos_docs = list(conn["pos_history"].find({}))
            for p in pos_docs:
                ts = p.get("timestamp")
                if ts:
                    ts_str = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
                    if start_date <= ts_str[:10] <= end_date:
                        val = float(p.get("total", 0))
                        if p.get("fiscal"):
                            revenue_fiscal += val
                        else:
                            revenue_non_fiscal += val

            for d in docs:
                ts = d.get("timestamp")
                if ts:
                    ts_str = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
                    date_str = ts_str[:10]
                    if start_date <= date_str <= end_date:
                        revenue += float(d.get("price", 0))
                        name = d.get("burger_name", "Nieznany")
                        if name:
                            products[name] += 1
            return {
                "revenue": revenue,
                "revenue_fiscal": revenue_fiscal,
                "revenue_non_fiscal": revenue_non_fiscal,
                "products": dict(sorted(products.items(), key=lambda x: x[1], reverse=True)[:10])
            }
    except Exception as e:
        logger.error(f"Error in admin_stats: {e}")
        return {"revenue": 0.0, "products": {}, "error": str(e)}

# --- HTML PAGES ---

@app.post("/api/clear_table/{table_id}")
async def clear_table(table_id: str):
    # Całkowite usunięcie dokumentu = stolik w 100% ZIELONY/WOLNY
    try:
        db = get_db()
        if db is not None:
            # Usuń przypisaną sesję
            table_doc = db["active_tables"].find_one({"_id": table_id})
            if table_doc and table_doc.get("session_id"):
                db["sessions"].delete_one({"_id": table_doc["session_id"]})
            
            db["active_tables"].delete_one({"_id": table_id})
        
        await manager.broadcast(json.dumps({"type": "update"}))
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error in clear_table: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200) # Still 200 so UI doesn't alert "refused"

@app.post("/api/master/set_admin_password")
async def set_admin_password(new_pin: str = Form(...), admin_pin: str = Form(...)):
    """Set a new PIN for the Boss (formerly Admin).
    Requires the current admin PIN for verification.
    Stores the PIN securely in MongoDB under the 'staff' collection.
    """
    # Verify current admin PIN
    admin_doc = get_db()["staff"].find_one({"_id": "admin"})
    if not admin_doc:
        return JSONResponse({"error": "Admin not configured"}, status_code=400)
    stored_pin = admin_doc.get("pin")
    if stored_pin != admin_pin:
        return JSONResponse({"error": "Invalid current PIN"}, status_code=403)
    # Update PIN
    get_db()["staff"].update_one({"_id": "admin"}, {"$set": {"pin": new_pin}}, upsert=True)
    return {"ok": True, "message": "Admin PIN updated"}

@app.get("/api/master/get_nfc_status")
async def get_nfc_status():
    db = get_db()
    settings = db["config"].find_one({"_id": "system_settings"}) or {}
    return {"nfc_required": settings.get("nfc_required", True)}

@app.post("/api/master/toggle_nfc")
async def toggle_nfc(nfc_required: str = Form(...)):
    required_bool = nfc_required.lower() == "true"
    db = get_db()
    db["config"].update_one(
        {"_id": "system_settings"},
        {"$set": {"nfc_required": required_bool}},
        upsert=True
    )
    return {"ok": True, "nfc_required": required_bool}

@app.get("/api/admin/ai_report")
async def ai_report():
    """Generates an expert AI report for the last day's performance."""
    if not ai_client: return {"error": "AI model not configured"}
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = await admin_stats(today, today)
        revenue = stats.get("revenue", 0.0)
        products = stats.get("products", {})
        
        ratings_docs = get_db()["ratings"].find({})
        ratings_data = defaultdict(list)
        for d in ratings_docs:
            data = d
            for item, stars in data.get("ratings", {}).items():
                ratings_data[item].append(stars)
        
        avg_ratings = {item: sum(scores)/len(scores) for item, scores in ratings_data.items()}
        top_rated = dict(sorted(avg_ratings.items(), key=lambda x: x[1], reverse=True)[:5])

        prompt = f"Jesteś ekspertem gastronomii i analitykiem biznesowym. Oto statystyki z dzisiejszego dnia ({today}):\n"
        prompt += f"Przychód: {revenue} PLN\n"
        prompt += f"Sprzedane produkty: {json.dumps(products)}\n"
        prompt += f"Najlepiej oceniane produkty: {json.dumps(top_rated)}\n"
        prompt += "\nNapisz profesjonalny raport podsumowujący (ok. 10 zdań). Skup się na trendach i rekomendacjach dla menedżera (Boss). Używaj języka polskiego."

        response = ai_client.chat.completions.create(
            model=AI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15,
            max_tokens=800,
            extra_body={"reasoning_effort": "low"}
        )
        report_text = response.choices[0].message.content.strip()
        
        return {
            "report": report_text,
            "revenue": revenue,
            "chart_data": {
                "labels": list(products.keys()),
                "values": list(products.values())
            },
            "top_rated": top_rated
        }
    except Exception as e:
        print(f"Error AI Report: {e}")
        return {"error": str(e)}

@app.post("/api/admin/day_reset")
async def day_reset(request: Request):
    """Clears all orders and active tables for a fresh start."""
    data = await request.json()
    auth_role = data.get("auth_role")
    if auth_role not in ["master", "admin"]:
        return JSONResponse({"error": "Brak uprawnień"}, status_code=403)

    # Delete orders
    get_db()["orders"].delete_many({})

    # Delete active tables
    get_db()["active_tables"].delete_many({})

    await manager.broadcast(json.dumps({"type": "update"}))
    return {"ok": True, "message": "System wyczyszczony na nowy dzień!"}

@app.post("/api/rate_order")
async def rate_order(request: Request):
    """Saves customer ratings for ordered items."""
    data = await request.json()
    table_num = data.get("table_number")
    session_id = data.get("session_id")
    ratings = data.get("ratings") # {item_name: stars}

    if not ratings: return {"ok": False}

    get_db()["ratings"].insert_one({
        "_id": str(uuid.uuid4()),

        "table_number": table_num,
        "session_id": session_id,
        "ratings": ratings,
        "timestamp": datetime.now(timezone.utc)
    })
    return {"ok": True}

@app.get("/api/get_ratings")
async def get_ratings():
    """Returns average ratings for all products."""
    docs = get_db()["ratings"].find({})
    scores = defaultdict(list)
    for d in docs:
        data = d
        for item, star in data.get("ratings", {}).items():
            scores[item].append(star)

    result = {}
    for item, vals in scores.items():
        result[item] = round(sum(vals)/len(vals), 1)
    return result

@app.get("/api/wydawka/table_details/{num}")
async def table_details(num: str):
    """Returns all active orders for a specific table."""
    conn = get_db()
    if conn is None: return {"orders": []}
    
    table_ref = conn["active_tables"].find_one({"_id": str(num)})
    if not table_ref:
        return {"orders": []}

    session_id = table_ref.get("session_id")
    docs = conn["orders"].find({"table_number": str(num), "session_id": session_id})
    orders = []
    for d in docs:
        data = {k: v for k, v in d.items() if k != "_id"}
        data["id"] = str(d["_id"])
        orders.append(data)
    return {"orders": orders}

# --- HTML PAGES ---

@app.get("/zamowienie")
async def zamowienie_entry(request: Request, burger_session: Optional[str] = Cookie(None)):
    """Automatyczne przydzielanie numerka (persystencja w DB)."""
    conn = get_db()
    
    # 1. Sprawdź czy gość ma już aktywną sesję w DB
    if burger_session and conn:
        active_table = conn["active_tables"].find_one({"session_id": burger_session})
        if active_table:
            return RedirectResponse(url=f"/?table={active_table['_id']}")
        
        # Jeśli ma ciasteczko, ale nie ma go w active_tables, sprawdź czy jest w ogóle sesja
        session = conn["sessions"].find_one({"_id": burger_session})
        if session and session.get("session_number"):
            # Przywróć aktywność
            conn["active_tables"].update_one(
                {"_id": str(session["session_number"])}, 
                {"$set": {"table_number": str(session["session_number"]), "session_id": burger_session}}, 
                upsert=True
            )
            return RedirectResponse(url=f"/?table={session['session_number']}")

    # 2. Jeśli nie ma, stwórz nową trwałą sesję
    session = create_session(mode="foodtruck")
    assigned_number = session.get("session_number")
    
    if not assigned_number:
        return HTMLResponse(content="<div style='background:#000;color:#fff;height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:20px;text-align:center;'><h1>🛑 BRAK WOLNYCH MIEJSC</h1><p>Wszystkie sesje (1-30) są zajęte.</p></div>", status_code=503)

    response = RedirectResponse(url=f"/?table={assigned_number}")
    # ZAWSZE ustawiamy/aktualizujemy ciasteczko, aby zgadzało się z sesją w bazie
    response.set_cookie(key="burger_session", value=session["session_id"], max_age=86400, path="/")
    
    return response

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request, table: Optional[str] = None, burger_session: Optional[str] = Cookie(None)):
    if get_brand(request) == "DASH":
        return templates.TemplateResponse(request=request, name="dash.html", context={"request": request})

    if not burger_session:
        burger_session = str(uuid.uuid4())

    db_conn = get_db()
    if db_conn is None:
        return HTMLResponse(content=f"<h1>Błąd połączenia z bazą danych ({get_brand(request)})</h1><p>System startuje lub baza jest niedostępna. Spróbuj odświeżyć za chwilę.</p>", status_code=503)

    menu_dict = {d["_id"]: {k: v for k, v in d.items() if k != "_id"} for d in db_conn["menu"].find({})}
    menu = dict(sorted(menu_dict.items(), key=lambda x: int(x[1].get('sort_order', 99))))

    # JAWNY SŁOWNIK CONTEXT
    ctx = {
        "request": request,
        "menu": menu,
        "session_table": table,
        "table_locked": False,
        "locked_num": None,
        "my_session_id": burger_session,
        "system_mode": get_system_mode()
    }

    if table:
        conn = get_db()
        if conn is not None:
            table_doc = conn["active_tables"].find_one({"_id": str(table)})
            if table_doc:
                existing_session = table_doc.get("session_id")
                if existing_session and existing_session != burger_session:
                    ctx["table_locked"] = True
                    ctx["locked_num"] = table
                    ctx["session_table"] = None

            if not ctx["table_locked"]:
                conn["active_tables"].update_one({"_id": str(table)}, {"$set": {"table_number": str(table), "session_id": burger_session}}, upsert=True)

    ctx["brand"] = get_brand(request)
    resp = templates.TemplateResponse(request=request, name="index.html", context=ctx)
    resp.set_cookie(key="burger_session", value=burger_session, max_age=86400)
    return resp

@app.get("/wydawka", response_class=HTMLResponse)
async def wydawka_page(request: Request):
    return templates.TemplateResponse(request=request, name="wydawka.html", context={
        "request": request, 
        "brand": get_brand(request),
        "system_mode": get_system_mode(),
        "nfc_required": is_nfc_required()
    })

# Kiosk Wydawka - dedykowany interfejs dla Lenovo T520
@app.get("/kiosk/wydawka", response_class=HTMLResponse)
@app.get("/kiosk", response_class=HTMLResponse)
async def kiosk_wydawka_page(request: Request):
    """Dedykowany interfejs kiosku wydawki dla Lenovo T520"""
    return templates.TemplateResponse(request=request, name="kiosk_wydawka.html", context={
        "request": request,
        "brand": get_brand(request),
        "system_mode": get_system_mode()
    })

@app.get("/rcp", response_class=HTMLResponse)
async def rcp_page(request: Request):
    return templates.TemplateResponse(request=request, name="rcp.html", context={
        "request": request, 
        "brand": get_brand(request),
        "system_mode": get_system_mode()
    })


@app.get("/kds", response_class=HTMLResponse)
async def kds(request: Request):
    return templates.TemplateResponse(request=request, name="kds.html", context={
        "request": request, 
        "brand": get_brand(request),
        "system_mode": get_system_mode(),
        "nfc_required": is_nfc_required()
    })

@app.get("/waiter", response_class=HTMLResponse)
async def waiter(request: Request):
    return templates.TemplateResponse(request=request, name="waiter.html", context={
        "request": request, 
        "brand": get_brand(request),
        "system_mode": get_system_mode(),
        "nfc_required": is_nfc_required()
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html", context={
        "request": request, 
        "brand": get_brand(request),
        "system_mode": get_system_mode()
    })

@app.get("/master", response_class=HTMLResponse)
async def master_page(request: Request):
    brand = get_brand(request)
    mode = get_system_mode()
    return templates.TemplateResponse(request=request, name="master.html", context={
        "request": request, 
        "brand": brand,
        "system_mode": mode
    })

@app.get("/pracownicy", response_class=HTMLResponse)
async def pracownicy_direct(request: Request):
    # Dedykowany skrót do zarządzania pracownikami
    return templates.TemplateResponse(request=request, name="admin.html", context={
        "request": request, 
        "brand": get_brand(request),
        "system_mode": get_system_mode(),
        "initial_tab": "tab-staff" # Ta zmienna zostanie odczytana w admin.html przez Jinja2
    })

@app.get("/portal", response_class=HTMLResponse)
async def portal_page(request: Request):
    return templates.TemplateResponse(request=request, name="portal.html", context={
        "request": request, 
        "brand": get_brand(request),
        "system_mode": get_system_mode()
    })

@app.get("/oferta", response_class=HTMLResponse)
async def oferta_page(request: Request):
    return templates.TemplateResponse(request=request, name="oferta.html", context={"request": request})

@app.get("/health")
async def health_check():
    db_alive = False
    try:
        db = get_db()
        if db is not None:
            conn = db.session if hasattr(db, 'session') else SessionLocal()
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
            db_alive = True
    except:
        pass
    return {"status": "ok", "db_alive": db_alive, "timestamp": datetime.now().isoformat()}

@app.get("/api/dash/status")
async def get_dash_status():
    """Detailed health check for Docker, DB, and Tenants"""
    status = {"db_alive": False, "db_size": "---", "pings": []}
    
    # 1. Check DB
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        status["db_alive"] = True
        db.close()
    except Exception as db_err:
        logger.error(f"DASH DB ERROR: {db_err}")

    # 2. Check Docker
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(all=True)
        
        db_count = 0
        for c in containers:
            name = c.name
            if "_db" in name or "postgres" in name:
                db_count += 1
                
            if name.endswith("_app") or name == "zjedzit_app":
                prefix = "elvis" if name == "zjedzit_app" else name.split("_")[0]
                is_running = c.status == "running"
                
                status["pings"].append({
                    "domain": f"{prefix}.zjedz.it",
                    "alive": is_running,
                    "db_alive": is_running, # Assume DB is up if app is running for now
                    "app_health_db": is_running,
                    "latency_ms": 1 if is_running else 0,
                    "db_size": "OK" if is_running else "ERR",
                    "app_status": c.status,
                    "custom_template": False,
                    "template_path": f"/opt/elvis/{prefix}"
                })
        status["db_instances"] = db_count
        logger.info(f"DASH: Found {len(status['pings'])} tenant containers and {db_count} DBs.")
    except Exception as e:
        logger.error(f"DASH DOCKER ERROR: {str(e)}")
        status["error"] = f"Docker Error: {str(e)}"
        
    return status

@app.get("/test_docker")
async def test_docker():
    """Directly test docker connectivity without JS"""
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(all=True)
        names = [c.name for c in containers]
        return {"status": "ok", "count": len(names), "containers": names}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/dash/allow")
async def allow_domain(domain: str):
    """Caddy calls this to check if it should issue an SSL certificate for a domain"""
    # Allow main domains and anything that looks like our tenants
    allowed_roots = ["zjedz.it", "start.zjedz.it"]
    if any(domain == root or domain.endswith(f".{root}") for root in allowed_roots):
        return Response(status_code=200)
    
    # Check database for tenant slugs
    try:
        db = SessionLocal()
        slug = domain.split(".")[0]
        exists = db.query(Tenant).filter(Tenant.slug == slug).first()
        db.close()
        if exists:
            return Response(status_code=200)
    except:
        pass

    return Response(status_code=403)

class TenantRequest(BaseModel):
    tenant: str
    pin: str
    tenant_token: str = None

@app.post("/api/dash/create_tenant")
async def create_tenant(payload: TenantRequest):
    tenant = payload.tenant.lower().strip()
    pin = payload.pin
    tenant_token = payload.tenant_token
    
    import json
    import os
    from pathlib import Path
    cfg_path = Path(__file__).parent / "ai_config.json"
    master_pin = os.environ.get("MASTER_PIN", "1234")
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                master_pin = json.load(f).get("master_pin", master_pin)
        except: pass
        
    if pin != master_pin: raise HTTPException(401, "Błędny PIN Architekta.")
    if not tenant.isalnum():
        return JSONResponse({"error": "Nazwa musi być alfanumeryczna."}, status_code=400)
        
    try:
        import docker
        import yaml
        
        # 1. Edycja pliku Caddyfile
        caddyfile_path = "ovh/Caddyfile"
        try:
            with open(caddyfile_path, "r", encoding="utf-8") as f:
                caddy_content = f.read()
        except:
            caddyfile_path = "/app/ovh/Caddyfile" # Fallback absolute path in docker
            with open(caddyfile_path, "r", encoding="utf-8") as f:
                caddy_content = f.read()

        if f"{tenant}.zjedz.it" in caddy_content:
            return JSONResponse({"error": "Ten tenant już istnieje."}, status_code=400)
            
        new_caddy_block = f"\n\n{tenant}.zjedz.it {{\n    reverse_proxy {tenant}_app:8080\n}}\n"
        with open(caddyfile_path, "a", encoding="utf-8") as f:
            f.write(new_caddy_block)
            
        # 2. Edycja pliku docker-compose.yml za pomocą yaml (bezpiecznie omijając blok 'volumes' na końcu)
        compose_path = "ovh/docker-compose.yml"
        import os as _os
        if not _os.path.exists(compose_path):
            compose_path = "/app/ovh/docker-compose.yml"
            
        with open(compose_path, "r", encoding="utf-8") as f:
            compose_data = yaml.safe_load(f)
            
        if "volumes" not in compose_data or compose_data["volumes"] is None: 
            compose_data["volumes"] = {}
        
        db_vol_name = f"{tenant}_db_data"
        compose_data["volumes"][db_vol_name] = {}
        
        compose_data["services"][f"{tenant}_db"] = {
            "image": "postgres:15-alpine",
            "restart": "always",
            "environment": {
                "POSTGRES_USER": "marcin",
                "POSTGRES_PASSWORD": _os.environ.get("DATABASE_PASSWORD", "Haslo123!"),
                "POSTGRES_DB": "saas_db"
            },
            "volumes": [f"{db_vol_name}:/var/lib/postgresql/data"],
            "networks": ["elvis_net"]
        }
        
        app_env = [
            f"DATABASE_URL=postgresql://marcin:{_os.environ.get('DATABASE_PASSWORD', 'Haslo123!')}@{tenant}_db:5432/saas_db",
            f"BRAND={tenant.upper()}"
        ]
        if tenant_token:
            app_env.append(f"GEMINI_API_KEY={tenant_token}")
            
        compose_data["services"][f"{tenant}_db"]["container_name"] = f"{tenant}_db"
        compose_data["services"][f"{tenant}_app"] = {
            "build": {"context": "..", "dockerfile": "Dockerfile" if compose_path.endswith("ovh/docker-compose.yml") else "ovh/Dockerfile"},
            "image": "ovh-app",
            "container_name": f"{tenant}_app",
            "restart": "always",
            "environment": app_env,
            "depends_on": [f"{tenant}_db"],
            "volumes": [
                "/opt/elvis:/app:cached",
                "/var/run/docker.sock:/var/run/docker.sock"
            ],
            "networks": ["elvis_net"]
        }
        
        with open(compose_path, "w", encoding="utf-8") as f:
            yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)

        # 3. Uruchomienie dockera za pomocą zainstalowanego klienta Docker CLI w kontenerze
        import subprocess
        try:
            print(f"Starting orchestration for {tenant}...")
            # Użyj poprawnego katalogu jeśli w dockrze
            cmd = f"docker compose -f {compose_path} up -d {tenant}_db {tenant}_app"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True, text=True
            )
            print("Compose output:", result.stdout)
            if result.returncode != 0:
                print("Compose error:", result.stderr)
                return JSONResponse({"error": f"Błąd w Docker Compose: {result.stderr}"}, status_code=500)
        except Exception as compose_err:
            print("Compose orchestrator error, but YAML updated:", compose_err)
            return JSONResponse({"error": f"Błąd komunikacji z docker-compose: {str(compose_err)}"}, status_code=500)
            
        # 4. Reload Caddy
        try:
            client = docker.from_env()
            caddy_c = client.containers.get("elvis_caddy")
            caddy_c.exec_run("caddy reload --config /etc/caddy/Caddyfile")
        except Exception as caddy_err:
            try:
                # Fallback to other possible name
                caddy_c = client.containers.get("zjedzit_caddy")
                caddy_c.exec_run("caddy reload --config /etc/caddy/Caddyfile")
            except:
                print("Caddy reload error:", caddy_err)
            
        return {"success": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/dash/delete_tenant")
async def delete_tenant(payload: TenantRequest):
    tenant = payload.tenant.lower().strip()
    pin = payload.pin
    
    import json
    import os
    from pathlib import Path
    cfg_path = Path(__file__).parent / "ai_config.json"
    master_pin = os.environ.get("MASTER_PIN", "1234")
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                master_pin = json.load(f).get("master_pin", master_pin)
        except: pass
        
    if pin != master_pin: raise HTTPException(401, "Błędny PIN Architekta.")
    
    try:
        import docker
        import yaml
        import subprocess
        
        # 1. Stop and remove containers and volumes via Docker API
        client = docker.from_env()
        for suffix in ["_app", "_db"]:
            c_name = f"{tenant}{suffix}"
            try:
                c = client.containers.get(c_name)
                print(f"Stopping and removing container: {c_name}")
                c.stop(timeout=5)
                c.remove(v=True, force=True) 
            except Exception as e:
                print(f"Container {c_name} not found or already removed: {e}")

        # 2. Edycja pliku Caddyfile (bardziej elastyczny regex)
        caddyfile_path = "ovh/Caddyfile"
        if not os.path.exists(caddyfile_path):
            caddyfile_path = "/app/ovh/Caddyfile"
            
        if os.path.exists(caddyfile_path):
            with open(caddyfile_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Pattern matches: optional newlines + domain { ... } + optional newlines
            # Handles different spacing and variations in block content
            import re
            pattern = re.compile(rf"\s*{tenant}\.zjedz\.it\s*\{{[^}}]*\s*\}}", re.DOTALL)
            new_content = pattern.sub("", content).strip()
            
            # Ensure Caddyfile stays clean
            if new_content != content:
                with open(caddyfile_path, "w", encoding="utf-8") as f:
                    f.write(new_content + "\n")
                print(f"Removed {tenant} from Caddyfile")

        # 3. Edycja pliku docker-compose.yml
        compose_path = "ovh/docker-compose.yml"
        if not os.path.exists(compose_path):
            compose_path = "/app/ovh/docker-compose.yml"
            
        if os.path.exists(compose_path):
            with open(compose_path, "r", encoding="utf-8") as f:
                compose_data = yaml.safe_load(f)
            
            modified = False
            if "services" in compose_data:
                for suffix in ["_app", "_db"]:
                    svc_name = f"{tenant}{suffix}"
                    if svc_name in compose_data["services"]:
                        del compose_data["services"][svc_name]
                        modified = True
            
            if "volumes" in compose_data and compose_data["volumes"]:
                vol_name = f"{tenant}_db_data"
                if vol_name in compose_data["volumes"]:
                    del compose_data["volumes"][vol_name]
                    modified = True
            
            if modified:
                with open(compose_path, "w", encoding="utf-8") as f:
                    yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
                print(f"Removed {tenant} from docker-compose.yml")

        # 4. Reload Caddy
        try:
            caddy_c = None
            try:
                caddy_c = client.containers.get("zjedzit_caddy")
            except:
                caddy_c = client.containers.get("elvis_caddy")
            
            if caddy_c:
                caddy_c.exec_run("caddy reload --config /etc/caddy/Caddyfile")
                print("Caddy reloaded")
        except Exception as ce:
            print(f"Caddy reload failed: {ce}")
            
        # 5. Usunięcie wpisu z bazy danych (tenancy)
        try:
            db = SessionLocal()
            db.query(Tenant).filter(Tenant.slug == tenant).delete()
            db.commit()
            db.close()
            print(f"Removed {tenant} from tenants table")
        except Exception as dbe:
            print(f"Failed to remove from DB: {dbe}")

        return {"success": True}
    except Exception as e:
        logger.error(f"Error in delete_tenant: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/dash", response_class=HTMLResponse)
async def dash_page(request: Request):
    if request.url.hostname == "dash.zjedz.it":
        return templates.TemplateResponse(request=request, name="dash.html", context={"request": request})
    # Redirect or handle otherwise
    return templates.TemplateResponse(request=request, name="dash.html", context={"request": request})