# OVH / VPS (Debian 12 / Ubuntu) — instalacja aplikacji Zjedz.it POS (MongoDB)

To jest gotowe środowisko wdrożeniowe dla serwerów VPS opartych na Debian 12 (oraz Ubuntu 24.04) z bazą MongoDB. Zawiera krok po kroku instalację, konfigurację `nginx` oraz pomocniczych kontenerów dla Dockera.

> Uwaga: Całe główne repozytorium aplikacji powinno być sklonowane do katalogu `/opt/elvis` na VPS (wymagane ponieważ docker-compose wychodzi kontekstem wyżej).

## 1. Wymagania
- Serwer VPS: Debian 12 (lub Ubuntu Linux x86_64)
- konto z uprawnieniami `root` lub `sudo`
- publiczny adres IP
- środowisko Docker i wtyczka Docker Compose

## 2. Krok 1: przygotowanie serwera

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-plugin git curl
sudo usermod -aG docker $USER
newgrp docker
```

## 3. Krok 2: umieść kod w katalogu projektu

Przykład:

```bash
sudo mkdir -p /opt/elvis
sudo chown $USER:$USER /opt/elvis
cd /opt/elvis
git clone https://github.com/sensorwifi1/elvis.zjedz.it.git .
```

Jeżeli repozytorium już jest na serwerze, po prostu przejdź do katalogu:

```bash
cd /opt/elvis
```

## 4. Krok 3: konfiguracja środowiska

Skopiuj plik `.env.example` i dostosuj zmienne:

```bash
cd /opt/elvis/ovh
cp .env.example .env
```

Edytuj `ovh/.env`:

```bash
OVH_AI_ENDPOINTS_ACCESS_TOKEN=TWÓJ_TOKEN_OVH
AI_MODEL_NAME=gpt-oss-120b
MONGO_URI=mongodb://mongo:27017
```

## 5. Krok 4: uruchomienie aplikacji w Dockerze

Docker Compose uruchomi trzy kontenery:
- **mongo** — baza danych MongoDB (port wewnętrzny 27017, dane w named volume)
- **app** — aplikacja Elvis POS (port wewnętrzny 8080)
- **nginx** — reverse proxy (porty 80 i 443)

```bash
cd /opt/elvis/ovh
docker compose up -d --build
```

Sprawdzić status kontenerów:

```bash
docker compose ps
```

Powinno być 3 kontenery ze statusem `running`:

```
NAME         STATUS
elvis_mongo  Up
elvis_app    Up
elvis_nginx  Up
```

## 6. Krok 5: weryfikacja działania

### Sprawdzenie logów aplikacji
```bash
docker compose logs app
```

Powinno pokazać logi Gunicorna bez błędów połączenia MongoDB.

### Sprawdzenie MongoDB
```bash
docker compose exec mongo mongosh --eval "db.adminCommand('ping')"
```

Odpowiedź: `ok: 1`

### Dostęp do aplikacji
Wejdź na `http://localhost` (lub na IP serwera). Aplikacja powinna być dostępna.

## 7. Krok 6: SSL / HTTPS

Na Ubuntu 24.04 najlepiej użyć Certbota:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d twoja-domena.pl
```

## 8. Backup bazy danych

### Eksport bazy
```bash
docker compose exec mongo mongodump --out /dump
docker cp elvis_mongo:/dump ./mongo_backup_$(date +%Y%m%d)
```

### Import bazy
```bash
docker cp ./mongo_backup_20240101 elvis_mongo:/dump
docker compose exec mongo mongorestore /dump
```

## 9. Zarządzanie kontenerami

### Restart aplikacji (bez utraty danych MongoDB)
```bash
docker compose restart app
```

### Restart MongoDB
```bash
docker compose restart mongo
# Dane zostaną zachowane w named volume `mongo_data`
```

### Pełny reset (czyszczenie wszystkich danych)
```bash
docker compose down -v
# -v usuwa nazwane volumy, łącznie z mongo_data
docker compose up -d --build
```

### Logi
```bash
# Logi aplikacji
docker compose logs app -f

# Logi MongoDB
docker compose logs mongo -f

# Logi nginx
docker compose logs nginx -f
```

## 10. Skalowanie aplikacji (kilku klientów)

Jeśli obsługujesz kilkunastu klientów, każdy może mieć swoją instancję:

**Opcja 1: Oddzielne docker-compose dla każdego klienta**

```bash
mkdir -p /opt/elvis_klient1
cd /opt/elvis_klient1
# Sklonuj repozytorium lub skopiuj strukturę
docker compose -f /opt/elvis/ovh/docker-compose.yml up -d \
  -e MONGO_URI=mongodb://mongo1:27017
```

**Opcja 2: Jedna baza MongoDB dla wszystkich klientów**

Usuń `mongo` service z docker-compose, skonfiguruj wszystkie instancje aplikacji aby łączyły się z jednym MongoDB:

```yaml
environment:
  - MONGO_URI=mongodb://mongo-server.internal:27017
```

## 11. Uwaga dotycząca bazy danych

- **MongoDB** jest uruchamiane w kontenerze Docker z named volume `mongo_data`
- Dane są **trwałe** — przetrwają restart kontenera
- Wszystkie 8 kolekcji (orders, staff, menu, ratings, itp.) są automatycznie tworzone przy pierwszym dostępie

## 12. Zalecenia bezpieczeństwa

- Nie commituj pliku `.env` do repozytorium
- Zmienne środowiskowe (tokeny, hasła) przechowuj w `.env`
- Jeżeli masz publiczny dostęp do aplikacji, **zawsze używaj HTTPS**
- Regularnie twórz backupy bazy danych (`mongodump`)
- Ograniczaj dostęp do portów 27017 (MongoDB) — nie powinien być dostępny z internetu

## 13. Rozwiązywanie problemów

### Aplikacja nie łączy się z MongoDB
```bash
docker compose logs app | grep -i mongo
```

Sprawdź czy kontener `mongo` jest uruchomiony:
```bash
docker compose ps mongo
```

### Port 80/443 jest zajęty
```bash
sudo lsof -i :80
sudo lsof -i :443
# Zatrzymaj konfliktujące serwisy i uruchom ponownie docker compose
```

### Dane MongoDB się popsuły
```bash
# Backup starych danych
docker compose down
mv mongo_data mongo_data.backup
# Restart (nowa czyszczenie baza)
docker compose up -d --build
```

## 14. Poprawki i ulepszenia

### Ulepszenie bezpieczeństwa
- Usunięto hardcoded tokeny z pliku `elvis.service`
- Teraz tokeny są ładowane z pliku `.env` za pomocą `EnvironmentFile`
- Plik `.env` jest ignorowany przez `.gitignore`

### Dodano skrypt instalacyjny
- Dodano `setup-ubuntu.sh` który automatyzuje proces instalacji
- Skrypt zawiera wszystkie niezbędne kroki instalacji i konfiguracji
