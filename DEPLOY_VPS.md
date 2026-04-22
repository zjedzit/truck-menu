# Raport Wdrożenia - Elvis POS NFC Security

## Co zostało zrobione?
1.  **Backend (`main.py`):**
    *   Dodano pola `nfc_id` i `is_active` do modelu `Staff`.
    *   Dodano logowanie historii w tabeli `staff_activity`.
    *   Endpoint `POST /auth/nfc_toggle` - obsługuje odbijanie kart (HID USB).
    *   Endpoint `GET /api/active_staff` - do synchronizacji statusu blokady.
2.  **Frontend (`templates/wydawka.html`):**
    *   Wprowadzono **Lock Screen** blokujący interfejs bez autoryzacji NFC.
    *   Dodano nasłuchiwanie klawiaturowe (HID) dla czytników USB.
    *   Implementacja WebSocket (`nfc_auth`) dla natychmiastowego odblokowania.

## Jak wdrożyć na VPS (dla kolejnego Agenta)?

Jeśli pracujesz z innym agentem na VPS, wykonaj te kroki:

1.  **Pobierz najnowszy kod:**
    ```bash
    git pull origin main
    ```

2.  **Zrestartuj kontenery (Build wymagany ze względu na zmiany w modelach DB):**
    ```bash
    cd ovh
    docker compose down
    docker compose up -d --build
    ```

3.  **Migracja Bazy Danych:**
    System Elvis używa SQLAlchemy z `Base.metadata.create_all`, więc przy restarcie bazy tabele `staff_activity` oraz nowe kolumny w `staff` powinny utworzyć się automatycznie.
    Jeśli używasz istniejącej bazy Postgres, może być potrzebny ręczny ALTER lub reset wolumenu, jeśli SQLAlchemy nie doda kolumn automatycznie do istniejących tabel.

4.  **Konfiguracja pierwszego pracownika:**
    Przypisz fizyczny ID karty do rekordu w bazie danych:
    ```bash
    docker exec -it dash_db psql -U marcin -d saas_db
    # Wewnątrz SQL:
    UPDATE staff SET nfc_id = 'TWOJ_KOD_KARTY' WHERE name = 'Marcin';
    ```

## Uwagi:
*   Czytnik USB HID musi być podłączony do urządzenia, na którym wyświetlana jest przeglądarka (np. Lenovo T520).
*   Upewnij się, że WebSocket działa poprawnie (`ws://domain/ws`), aby synchronizacja blokady była natychmiastowa.
