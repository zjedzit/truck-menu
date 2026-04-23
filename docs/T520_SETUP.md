# Konfiguracja Terminala T520 (Edge Node)

Ten dokument opisuje proces przygotowania laptopa Lenovo ThinkPad T520 jako pancernego terminala POS dla systemu Elvis.

## 🏗️ Architektura
T520 działa jako **Thin Client**. Nie przechowuje głównej bazy danych, ale posiada lokalną kolejkę synchronizacji (Offline Sync) oraz zarządza sprzętem (drukarki, NFC).

- **OS**: Debian (rekomendowany 12 Bookworm, wersja stabilna).
- **Runtime**: Docker + Docker Compose.
- **Frontend**: Chromium w trybie Kiosk.
- **Gateway**: `edge_gateway.py` (obsługa USB/NFC/Sync).

---

## 🛠️ Instalacja Krok po Kroku

### 1. Przygotowanie Systemu (Debian)
Zainstaluj Debiana w wersji minimalnej (bez ciężkiego GNOME/KDE). Rekomendowany jest lekki menedżer okien (np. **Openbox**) lub samo środowisko graficzne X11 dla Chromium.

### 2. Instalacja Dockera
Wykonaj na terminalu:
```bash
# Dodaj klucze GPG i repozytorium Docker
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Dodaj repozytorium do źródeł APT
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 3. Konfiguracja Edge Gateway (Docker)
Stwórz plik `docker-compose.yml` dla terminala:

```yaml
version: '3.8'
services:
  edge-gateway:
    build: .
    container_name: elvis-edge-gateway
    restart: always
    network_mode: "host" # Ważne dla łatwej komunikacji z localhost
    devices:
      - "/dev/usb/lp0:/dev/usb/lp0" # Drukarka bonowa
      - "/dev/bus/usb:/dev/bus/usb" # Czytnik NFC
    volumes:
      - ./data:/app/data
      - ./edge_gateway.py:/app/edge_gateway.py
    environment:
      - CLOUD_URL=https://bar.zjedz.it/api/sync
      - DEVICE_KEY=TRUCK-01-T520
```

### 4. Tryb Kiosk (Automatyczny start przeglądarki)
Aby T520 po włączeniu od razu pokazywał menu, stwórz skrypt autostartu:

```bash
# Zainstaluj Chromium i xautomation
sudo apt-get install chromium x11-xserver-utils

# Skrypt startowy (np. ~/.xsession)
chromium --kiosk --app=https://elvis.zjedz.it --noerrdialogs --disable-infobars --window-position=0,0
```

---

## 🔌 Podłączenie Sprzętu
- **Drukarka USB**: Powinna pojawić się jako `/dev/usb/lp0`. Jeśli nie masz uprawnień, dodaj użytkownika docker do grupy `lp`: `sudo usermod -aG lp $USER`.
- **NFC**: Większość czytników działa jako emulacja klawiatury (HID). Gateway nasłuchuje zdarzeń wejścia i przekazuje je przez WebSocket do frontendu.

## 📡 Tryb Offline
Jeśli internet zgaśnie:
1. Przeglądarka nadal działa (dzięki Service Workerom i lokalnemu Gatewayowi).
2. `edge_gateway.py` zapisuje zamówienie w pliku `data/offline_orders.db`.
3. Po powrocie sieci, ikona statusu w aplikacji zmieni się na zieloną, a zamówienia zostaną wysłane na serwer OVH.

---

## 🔋 Dlaczego T520 w Food Trucku?
1. **Pancerna obudowa**: Wytrzyma wibracje i trudne warunki.
2. **Bateria**: Działa jako wbudowany UPS. Nagły brak prądu nie powoduje korupcji bazy danych.
3. **Klawiatura**: Klasyczna klawiatura ThinkPada pozwala na szybką konfigurację bez podpinania zewnętrznych akcesoriów.
