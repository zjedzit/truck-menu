import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# --- Konfiguracja ---
LOG_FILE = "edge_gateway.log"
DB_FILE = "offline_orders.db"
CLOUD_URL = "https://bar.zjedz.it/api/sync"  # URL Twojego serwera na OVH
DEVICE_KEY = "T520-EDGE-01"
PRINTER_PATH = "/dev/usb/lp0"  # Typowa ścieżka drukarki na Linux

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger("EdgeGateway")

app = FastAPI(title="Elvis Edge Gateway")

# --- Baza Danych Offline ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  payload TEXT, 
                  status TEXT, 
                  created_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rcp_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  staff_id TEXT, 
                  action TEXT, 
                  timestamp TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# --- Modele Danych ---
class Order(BaseModel):
    items: list
    total: float
    payment_method: str
    staff_id: Optional[str] = None

# --- Manager Połączeń WebSocket ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async training_connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- Logika Drukarki ---
def print_receipt(payload: dict):
    logger.info(f"Drukowanie zamówienia: {payload.get('id', 'N/A')}")
    try:
        # Tu wstawić logikę python-escpos lub bezpośredni zapis do /dev/usb/lp0
        # with open(PRINTER_PATH, "wb") as f:
        #     f.write(b"\x1b\x40") # Initialize
        #     f.write(f"ZAMOWIENIE\n{json.dumps(payload, indent=2)}\n\n\n".encode('ascii'))
        pass
    except Exception as e:
        logger.error(f"Błąd drukarki: {e}")

# --- Logika Synchronizacji ---
async def sync_task():
    """Tło: próbuje wysłać zamówienia z bazy offline do chmury."""
    while True:
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT id, payload FROM orders WHERE status = 'pending' LIMIT 10")
            pending = c.fetchall()
            
            if pending:
                async with httpx.AsyncClient() as client:
                    for row_id, payload_str in pending:
                        logger.info(f"Synchronizacja zamówienia {row_id}...")
                        response = await client.post(
                            CLOUD_URL, 
                            json={"device_key": DEVICE_KEY, "order": json.loads(payload_str)},
                            timeout=10.0
                        )
                        if response.status_code == 200:
                            c.execute("UPDATE orders SET status = 'synced' WHERE id = ?", (row_id,))
                            conn.commit()
                            logger.info(f"Zsynchronizowano pomyślnie: {row_id}")
            
            conn.close()
        except Exception as e:
            logger.warning(f"Brak połączenia z chmurą lub błąd sync: {e}")
        
        await asyncio.sleep(30) # Sprawdzaj co 30 sekund

# --- Endpointy ---

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(sync_task())

@app.post("/print")
async def local_print(payload: dict):
    print_receipt(payload)
    return {"status": "sent_to_printer"}

@app.websocket("/ws/hardware")
async def hardware_ws(websocket: WebSocket):
    await manager.training_connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Obsługa przychodzących zdarzeń z przeglądarki
            if message.get("type") == "order_submit":
                # Zapisz offline
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("INSERT INTO orders (payload, status, created_at) VALUES (?, ?, ?)",
                          (json.dumps(message["data"]), "pending", datetime.now()))
                conn.commit()
                conn.close()
                
                # Drukowanie (zawsze lokalnie)
                print_receipt(message["data"])
                
                await websocket.send_json({"type": "order_confirmed", "local_id": "ok"})

            elif message.get("type") == "nfc_read_request":
                # Symulacja odczytu NFC - w realu tu byłaby pętla nasłuchująca na USB
                await websocket.send_json({"type": "nfc_tag", "tag_id": "STAFF_12345"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS Error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    logger.info(f"Uruchamianie Edge Gateway na T520... Device: {DEVICE_KEY}")
    uvicorn.run(app, host="127.0.0.1", port=8001)
