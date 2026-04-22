# Elvis Burger POS — System Gastronomiczny v3.0

Kompletny system zarządzania restauracją oparty na chmurze + terminal lokalny (T520).
Architektura: **chmura (FastAPI) + terminal lokalny (T520) + PostgreSQL + WebSocket**.

---

## Architektura systemu

```
┌─────────────────────────────────────────────────────────┐
│                   CHMURA (VPS / Cloud Run)               │
│                                                         │
│   main.py  (FastAPI + Uvicorn)                          │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│   │ /admin   │  │ /waiter  │  │ /kds     │             │
│   │ /master  │  │ /wydawka │  │ /        │             │
│   └──────────┘  └──────────┘  └──────────┘             │
│                   WebSocket Hub (/ws)                   │
│                   PostgreSQL DB                         │
└─────────────────────────┬───────────────────────────────┘
                          │ WebSocket (wss://)
                          │
┌─────────────────────────▼───────────────────────────────┐
│          Terminal Lokalny (Lenovo T520 / Edge Node)      │
│                                                         │
│   Docker Container (FastAPI)                            │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│   │ /        │  │ /pos     │  │ /kds     │             │
│   │ gateway  │  │ (iframe) │  │ (iframe) │             │
│   └──────────┘  └──────────┘  └──────────┘             │
│   WS Client → odbiera receipt → loguje do event_log     │
│   Drukarka fiskalna / Ekran POS                         │
└─────────────────────────────────────────────────────────┘
```

---

## Panele i ich funkcje

### `/` — Menu Klienta
- Zamawianie przez QR kod przy stoliku
- Sesja przypisana do stolika (izolacja między gośćmi)
- Integracja z Gemini AI: żarty i ciekawostki o daniach
- Wezwanie kelnera / prośba o rachunek

### `/waiter` — Stacja Kelnera (POS)
- Logowanie PIN-em pracownika
- Dynamiczna mapa stolików (wolne / zajęte)
- Podgląd zamówień na stoliku w czasie rzeczywistym
- Obsługa wezwań i płatności
- Wystawianie rachunku → broadcast `receipt` do terminala

### `/kds` — Kitchen Display System (Kuchnia)
- Logowanie hasłem
- Lista bonów w kolejności: nowe → w przygotowaniu → gotowe
- Timer na każdym bonie
- Zmiany statusu broadcastowane do wszystkich paneli

### `/wydawka` — Wydawka (Expo)
- Logowanie hasłem
- Bony gotowe do wydania (wszystkie pozycje = ready)
- Wydanie bonu → zamknięcie zamówienia

### `/admin` — Panel Admina
- Logowanie PIN-em (domyślny: `102938`)
- **Dashboard**: utarg dzienny, statystyki, mapa sali
- **Urządzenia**: status połączenia terminala + live kolejka druku (paragonów)
- **Statystyki**: filtrowanie dat, wykres bestselerów
- **Mapa Sali**: edytor Drag & Drop stolików
- **Produkty**: edytor menu z uploadem zdjęć
- **Pracownicy**: zarządzanie PIN-ami i rolami
- **Uprawnienia**: nadawanie dostępu Google (email → rola)

### `/master` — Panel Mastera
- Logowanie Google Auth (tylko `hajdukiewicz@gmail.com`)
- Nadawanie ról Google (admin, kuchnia, wydawka)
- Ustawianie haseł do paneli KDS / Wydawka

---

## Poziomy dostępu

| Poziom   | Metoda logowania        | Dostęp                                  |
|----------|-------------------------|-----------------------------------------|
| Klient   | Brak (sesja cookie)     | Menu, zamówienia, wezwanie kelnera      |
| Kelner   | PIN (6+ znaków)         | `/waiter` — POS                         |
| KDS      | Hasło lub PIN           | `/kds` — kuchnia                        |
| Wydawka  | Hasło lub PIN           | `/wydawka` — expo                       |
| Admin    | PIN `102938` lub własny | `/admin` — zarządzanie + uprawnienia    |
| Master   | Google Auth             | `/master` + pełny admin                 |

---

## Synchronizacja WebSocket

Każda zmiana w systemie broadcastuje `{"type": "update"}` do wszystkich podłączonych klientów.
Paragon po zamknięciu rachunku broadcastuje `{"type": "receipt", ...}` → terminal + zakładka Urządzenia w adminie.

Typy wiadomości:
- `update` — ogólne odświeżenie danych
- `receipt` — paragon z pozycjami, numerem stolika, sumą
- `device_status` — terminal rejestruje się jako online/offline

---

## API — kluczowe endpointy

| Metoda | Endpoint                        | Opis                              |
|--------|---------------------------------|-----------------------------------|
| GET    | `/api/get_menu`                 | Pobierz menu                      |
| GET    | `/api/all_orders`               | Wszystkie zamówienia (100 last)   |
| POST   | `/api/orders`                   | Dodaj zamówienie                  |
| POST   | `/api/update_status/{id}`       | Zmień status zamówienia           |
| POST   | `/api/mark_paid/{table}`        | Zamknij rachunek + wyślij paragon |
| POST   | `/api/admin/save_product`       | Zapisz produkt (multipart)        |
| POST   | `/api/admin/save_layout`        | Zapisz mapę sali                  |
| POST   | `/api/admin/save_staff`         | Dodaj/edytuj pracownika           |
| GET    | `/api/admin/get_staff`          | Lista pracowników                 |
| POST   | `/api/admin/set_role`           | Nadaj rolę Google                 |
| GET    | `/api/admin/get_users`          | Lista dostępów Google             |
| GET    | `/api/admin/stats`              | Statystyki sprzedaży              |
| GET    | `/api/admin/last_receipt`       | Ostatni paragon                   |
| POST   | `/api/admin/resend_receipt`     | Wyślij paragon ponownie           |
| POST   | `/api/auth/staff_login`         | Logowanie PIN-em                  |
| POST   | `/api/auth/login`               | Logowanie Google                  |
| POST   | `/api/auth/verify_password`     | Weryfikacja hasła panelu          |
| GET    | `/api/device_status/{key}`      | Status urządzenia lokalnego       |
| WS     | `/ws?device_key=...`            | WebSocket hub                     |

---

## Baza danych — PostgreSQL

| Tabela          | Klucz                | Zawartość                          |
|-----------------|----------------------|------------------------------------|
| `menu`          | `{klucz}`            | name, price, image, to_kitchen...  |
| `orders`        | auto-ID              | burger_name, table, status, paid.. |
| `active_tables` | `{numer_stolika}`    | session_id, call_waiter, pay_req.. |
| `staff`         | `{pin}`              | name, role                         |
| `users`         | `{email}`            | role                               |
| `devices`       | `{device_key}`       | status, ip, last_seen              |
| `config`        | `floor_plan`         | width, height, tables[]            |
| `config`        | `passwords`          | kds_pwd, wydawka_pwd               |
| `config`        | `last_receipt`       | ostatni paragon                    |

---

## Deploy — VPS / Cloud Run

```bash
# Jednorazowo: buduj i deploy
gcloud run deploy elvis-app \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLIENT_ID=YOUR_ID

# Lub przez Docker
docker build -t elvis-app .
docker run -p 8080:8080 elvis-app
```

Wymagane zmienne środowiskowe:
- `GOOGLE_CLIENT_ID` — ID aplikacji OAuth 2.0 z Google Console
- `DATABASE_URL` — connection string do PostgreSQL

---

## Instalacja lokalna (dev)

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## Pliki projektu

```
elvis/
├── main.py               # Serwer (FastAPI)
├── requirements.txt      # Zależności Python
├── Dockerfile            # Obraz Docker
├── templates/
│   ├── index.html        # Menu klienta
│   ├── waiter.html       # Stacja kelnera
│   ├── kds.html          # Kuchnia
│   ├── wydawka.html      # Wydawka/Expo
│   ├── admin.html        # Panel admina
│   └── master.html       # Panel mastera
├── static/
│   ├── style.css
│   └── images/           # Zdjęcia produktów
├── db/
│   └── sqlite_db.py      # Warstwa kompatybilności DB
└── ovh/                  # Konfiguracja VPS (Caddy, Docker Compose)
```

## Architektura

System składa się z:
- Aplikacji internetowej (FastAPI)
- Bazy danych PostgreSQL
- Odwracającego proxy Caddy (auto-SSL)
- Kontenerów Docker do izolacji

## Współpraca

Współpraca jest mile widziana! Proszę rozwidlić repozytorium i przesłać pull request.

## Licencja

Ten projekt jest objęty licencją MIT.