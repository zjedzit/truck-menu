# Integracja Sprzętowa: Drukarki i Urządzenia USB

Elvis POS wspiera szeroką gamę urządzeń peryferyjnych niezbędnych w gastronomii.

## 🖨️ Drukarki Bonowe (ESC/POS)
Drukarki kuchenne podłączane są przez USB lub sieć LAN do T520.
- **Protokół**: ESC/POS (standard przemysłowy).
- **Zalecane modele**: Epson TM-T20, Bixolon, Star Micronics lub chińskie drukarki 80mm.
- **Konfiguracja**: Mapowanie w `edge_gateway.py` na `/dev/usb/lp0`.

## 🧾 Drukarki Fiskalne (Polska)
Obsługa protokołów fiskalnych dla poprawnej rejestracji sprzedaży:
- **Posnet Thermal**: Protokół używany przez Posnet, Elzab (częściowo).
- **Novitus**: Obsługa nowszych modeli przez protokół XML lub natywny.
- **Wymagania**: Drukarka musi być podłączona do T520 (Edge Node).

## 💳 Czytniki NFC / RCP
System wspiera logowanie kartami zbliżeniowymi:
1. **Tryb HID**: Czytnik emuluje klawiaturę. Pracownik przykłada kartę, a system odczytuje ciąg znaków (ID karty).
2. **Tryb PCSC**: Dedykowana obsługa kart inteligentnych (wymaga dodatkowych bibliotek w Gatewayu).

---

## 🛠️ Rozwiązywanie Problemów
- **Drukarka nie drukuje**: 
  - Sprawdź czy jest włączona i ma papier.
  - Sprawdź uprawnienia do portu: `ls -l /dev/usb/lp0`.
  - Zrestartuj kontener gatewaya: `docker restart elvis-edge-gateway`.
- **NFC nie reaguje**:
  - Upewnij się, że kursor w przeglądarce nie "uciekł" z pola nasłuchiwania (jeśli używasz trybu HID).
  - Sprawdź logi gatewaya: `docker logs elvis-edge-gateway`.
