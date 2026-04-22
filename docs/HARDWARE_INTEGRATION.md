# Elvis POS — Przewodnik Integracji Sprzętowej (Hardware API)

Elvis POS wspiera komunikację z drukarkami bonowymi (ESC/POS) oraz drukarkami fiskalnymi poprzez architekturę **Edge-Cloud**.

## 🏗️ Architektura
Urządzenia (drukarki) podłączone są fizycznie do lokalnego węzła **Lenovo T520 (Edge Master)**. Serwer VPS wysyła polecenia druku przez bezpieczny kanał WebSocket.

## 📡 Endpointy API

### 1. Zlecenie wydruku (Cloud to Edge)
`POST /api/hardware/print`

**Przykład JSON (Drukarka Bonowa):**
```json
{
  "device_key": "kuchnia_t520_1",
  "type": "receipt",
  "content": {
    "title": "ZAMÓWIENIE #5",
    "items": [
      {"name": "Elvis Burger", "qty": 2, "price": 45.00},
      {"name": "Frytki", "qty": 1, "price": 12.00}
    ],
    "total": 102.00,
    "table": "5"
  }
}
```

**Przykład JSON (Drukarka Fiskalna):**
```json
{
  "device_key": "bar_t520_1",
  "type": "fiscal",
  "content": {
    "nip": "123-456-78-90",
    "items": [
      {"name": "Burger Wołowy", "tax": "A", "price": 39.00}
    ],
    "payment": "card"
  }
}
```

## 🛠️ Implementacja po stronie Edge Node (Agent)
Aby obsłużyć drukarkę, lokalny Agent na terminalu T520 musi nasłuchiwać na zdarzenie `print_job` w WebSocetcie:

```javascript
// Przykład w Node.js / Python na terminalu T520
socket.on('message', (msg) => {
    const data = JSON.parse(msg);
    if (data.type === 'print_job') {
        if (data.job_type === 'receipt') {
            printEscPos(data.data); // Użycie biblioteki escpos-php lub python-escpos
        } else if (data.job_type === 'fiscal') {
            printFiscal(data.data); // Wywołanie sterownika Posnet/Novitus
        }
    }
});
```

## 📦 Wspierane Protokoły
1. **ESC/POS**: Standard dla 99% drukarek termicznych (USB/Ethernet/Bluetooth).
2. **Posnet Thermal**: Najpopularniejszy protokół fiskalny w Polsce.
3. **Novitus Deon**: Protokoły obsługiwane przez nowsze modele Novitus.

## 🚀 Korzyści
- **Zero Port-Forwarding**: Nie musisz otwierać portów na routerze w lokalu.
- **Monitoring w czasie rzeczywistym**: Wiesz od razu, czy w drukarce skończył się papier.
- **Wielu użytkowników**: Każdy terminal (waiter, admin) może wysłać druk na dowolną drukarkę w sieci.
