# Konfiguracja Terminala Edge (Lenovo T520)

Ten dokument opisuje konfigurację fizycznego terminala znajdującego się w lokalu/food trucku.

## 💻 Dlaczego Lenovo T520?
- **Niezawodność**: Klasyczna konstrukcja ThinkPad.
- **Wbudowany UPS**: Bateria pozwala na bezpieczne dokończenie zamówienia przy zaniku zasilania.
- **Wydajność**: Znacznie szybszy niż Raspberry Pi, co zapewnia płynność interfejsu Chromium.

---

## 🛠️ Instalacja (Debian + Docker)

### 1. OS
Zainstaluj **Debian 12** (wersja bez środowiska graficznego lub z lekkim Openbox).

### 2. Edge Gateway
Na T520 musi działać skrypt `edge_gateway.py`. Odpowiada on za:
- **Drukarkę USB**: Pośrednictwo w wydrukach bonów i paragonów.
- **NFC (RCP)**: Odczyt kart pracowników.
- **Offline Sync**: Buforowanie zamówień przy braku internetu.

### 3. Uruchomienie Gatewaya w Dockerze
```bash
cd ~/truck-menu
# Zbuduj i uruchom kontener gatewaya
docker compose -f docker-compose.local.yml up -d
```

---

## 📺 Tryb Kiosk (Automatyczny Start)
Aby terminal po włączeniu od razu pokazywał panel sprzedażowy:

1. Zainstaluj Chromium: `sudo apt install chromium`
2. Dodaj skrypt do autostartu X11:
```bash
chromium --kiosk --app=https://elvis.zjedz.it/wydawka --noerrdialogs --disable-infobars
```

---

## 🔌 Podłączenie Urządzeń
- **Drukarka**: Podpięta pod USB (zazwyczaj `/dev/usb/lp0`).
- **NFC**: Czytnik USB HID (widziany jako klawiatura) lub dedykowany moduł obsługiwany przez gateway.

---

## 📡 Zarządzanie Stanem Offline
Gdy ikona połączenia w prawym górnym rogu zmieni kolor na **czerwony**:
1. Nie odświeżaj strony (aplikacja działa z pamięci przeglądarki).
2. Kontynuuj przyjmowanie zamówień – zostaną zapisane w lokalnym pliku `offline_orders.db`.
3. Po odzyskaniu sieci, system automatycznie wypchnie ("push") dane do chmury na VPS.
