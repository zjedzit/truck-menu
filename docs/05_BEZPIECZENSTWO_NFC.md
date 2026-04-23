# Bezpieczeństwo i RCP (System NFC)

System Elvis wykorzystuje karty NFC do autoryzacji personelu oraz rejestracji czasu pracy (RCP).

## 🔒 Lock Screen (Blokada Panelu)
Panel wydawki (`/wydawka`) posiada wbudowany **Lock Screen**. Interfejs jest zablokowany (Overlay), dopóki pracownik nie "odbije" swojej karty na czytniku NFC podłączonym do T520.

## 🛠️ Konfiguracja Techniczna

### 1. Rejestracja Karty w Bazie
Każda karta musi mieć swój odpowiednik w bazie danych (tabela `staff`, pole `nfc_id`).
Aby przypisać kartę do pracownika:
```bash
docker exec -it elvis_db psql -U postgres -d elvis_db
# Wewnątrz SQL:
UPDATE staff SET nfc_id = 'A1B2C3D4' WHERE name = 'Marcin';
```

### 2. Logowanie Aktywności
Każde zbliżenie karty jest logowane w tabeli `staff_activity`. Pozwala to na:
- Generowanie raportów czasu pracy.
- Śledzenie, kto anulował dane zamówienie lub udzielił rabatu.

### 3. Hardware Bridge (Edge Gateway)
Skrypt `edge_gateway.py` na T520 nasłuchuje zdarzeń z czytnika USB HID i przesyła ID karty przez WebSocket do przeglądarki. Browser sprawdza ID w chmurze (OVH) i odblokowuje interfejs.

---

## 📋 Lista Uprawnień
| Funkcja | Wymaga NFC? |
| :--- | :---: |
| Przyjmowanie zamówień | Tak |
| Podgląd menu | Nie |
| Anulowanie zamówienia | Tak (Manager) |
| Raport dobowy | Tak (Manager) |
| Zmiana cen | Tak (Admin) |
