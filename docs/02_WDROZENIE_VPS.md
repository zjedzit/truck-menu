# Instalacja i Konfiguracja VPS (OVH)

Ten dokument opisuje proces wdrożenia centralnego serwera systemu Elvis na maszynie wirtualnej (VPS) w chmurze OVH.

## 📋 Wymagania
- **System**: Debian 12 (rekomendowany) lub Ubuntu 24.04.
- **Zasoby**: Min. 2GB RAM, 20GB SSD.
- **Domena**: Skierowana na IP serwera (np. przez Cloudflare).

---

## 🚀 Szybki Start (Skrypt)
Najszybszą metodą instalacji jest użycie skryptu `setup-ubuntu.sh`:
```bash
cd ~/truck-menu/ovh
chmod +x setup-ubuntu.sh
./setup-ubuntu.sh
```

---

## 🛠️ Instalacja Ręczna

### 1. Przygotowanie Systemu
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-plugin git curl certbot python3-certbot-nginx
sudo usermod -aG docker $USER
```

### 2. Pobranie Kodu
```bash
git clone https://github.com/zjedzit/truck-menu.git ~/truck-menu
cd ~/truck-menu/ovh
```

### 3. Konfiguracja Środowiska (.env)
Skopiuj przykład i uzupełnij dane:
```bash
cp .env.example .env
nano .env
```
Kluczowe zmienne:
- `POSTGRES_PASSWORD`: Hasło do bazy danych.
- `CLOUD_API_KEY`: Klucz do komunikacji z Edge Node.
- `BRAND_NAME`: Nazwa Twojego food trucka.

### 4. Uruchomienie Kontenerów
```bash
docker compose up -d --build
```
System uruchomi:
- **FastAPI**: Backend aplikacji.
- **PostgreSQL**: Bazę danych.
- **Caddy/Nginx**: Reverse proxy z obsługą SSL.

---

## 🔄 Aktualizacja Systemu
Aby pobrać najnowszą wersję kodu i zrestartować usługi:
```bash
cd ~/truck-menu/ovh
./update.sh
```

---

## 🥗 Inicjalizacja Danych (Seeding)

Po pierwszym uruchomieniu systemu baza danych jest pusta. Możesz ją wypełnić przykładowymi danymi (menu, zdjęcia, historia sprzedaży) za pomocą skryptu:

1. **Dla domyślnego brandu (bar):**
   ```bash
   docker exec -it zjedzit_app python seed_products.py
   ```

2. **Dla konkretnego tenanta (np. elvis):**
   ```bash
   docker exec -e BRAND=elvis -it zjedzit_app python seed_products.py
   ```

Skrypt automatycznie przypisuje zdjęcia z katalogu `static/images/` do produktów i generuje symulowaną historię sprzedaży z ostatnich 30 dni.

---

## 📱 System Kluczy Jednorazowych (QR)

System wspiera generowanie jednorazowych dostępów do menu (idealne dla Food Trucków):
1. Przejdź do `/admin` -> zakładka **KOD QR**.
2. Kliknij **GENERUJ KLUCZ JEDNORAZOWY**.
3. Skopiuj link lub wydrukuj wygenerowany kod QR.
4. Po złożeniu pierwszego zamówienia przez klienta, klucz wygasa automatycznie, co zapobiega nieautoryzowanym zamówieniom spoza kolejki.

---

## 🔐 Bezpieczeństwo i Backup
1. **SSL**: Caddy automatycznie zarządza certyfikatami. Jeśli używasz Nginx, użyj `certbot --nginx`.
2. **Backup DB**: 
   ```bash
   docker exec -t elvis_db pg_dumpall -c -U postgres > backup_$(date +%Y%m%d).sql
   ```
3. **Firewall**: Upewnij się, że porty 80, 443 są otwarte, a porty bazy danych (5432) są zamknięte dla świata.

---

> [!NOTE]
> Oryginalne notatki z pliku `VPS.docx` zostały scalone z tym dokumentem w celu ujednolicenia dokumentacji technicznej.
