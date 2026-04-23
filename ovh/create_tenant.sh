#!/usr/bin/env bash
set -euo pipefail

# === USTAWIENIA DOMYŚLNE ===
BASE_DIR="/opt/elvis/ovh"
CODE_DIR="/home/debian/truck-menu"          # tu MUSI być main.py + tenancy.py (bind-mount -> /app)
MAIN_ENV="/home/debian/truck-menu/ovh/.env" # główny env, skąd weźmiemy hasła/tokeny
DOMAIN_ROOT_DEFAULT="zjedz.it"

usage() {
  cat <<EOF
Użycie:
  $0 <slug> [--brand BRAND] [--mode perdb|shareddb] [--domain-root zjedz.it]

Przykłady:
  sudo $0 stary --brand STARY --mode perdb
  sudo $0 pizza --mode shareddb

Tryby:
  perdb     - tenant ma własny Postgres (kontener <slug>_db)
  shareddb  - tenant używa wspólnego Postgresa (zjedzit_postgres)

EOF
}

# === PARSOWANIE ARGUMENTÓW ===
if [[ ${#} -lt 1 ]]; then usage; exit 1; fi

SLUG="$1"; shift || true
BRAND=""
MODE="perdb"
DOMAIN_ROOT="$DOMAIN_ROOT_DEFAULT"

while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --brand) BRAND="${2:-}"; shift 2;;
    --mode) MODE="${2:-}"; shift 2;;
    --domain-root) DOMAIN_ROOT="${2:-}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Nieznany argument: $1"; usage; exit 1;;
  esac
done

# slug sanitation
if ! [[ "$SLUG" =~ ^[a-z0-9-]{2,32}$ ]]; then
  echo "BŁĄD: slug musi mieć 2-32 znaki i pasować do ^[a-z0-9-]{2,32}$"
  exit 1
fi

if [[ -z "$BRAND" ]]; then
  BRAND="$(echo "$SLUG" | tr '[:lower:]-' '[:upper:]_')"
fi

TEMPLATE_DIR="${BASE_DIR}/templates_${SLUG}"

# === WALIDACJE KRYTYCZNE ===
if [[ ! -f "${CODE_DIR}/main.py" ]]; then
  echo "BŁĄD: Nie znaleziono ${CODE_DIR}/main.py"
  echo "Tenant kontener nie wystartuje (gunicorn nie znajdzie modułu 'main')."
  exit 1
fi

if [[ ! -f "${CODE_DIR}/tenancy.py" ]]; then
  echo "BŁĄD: Nie znaleziono ${CODE_DIR}/tenancy.py"
  echo "Dodaj tenancy.py obok main.py: ${CODE_DIR}/tenancy.py"
  exit 1
fi

# Wczytaj hasła/zmienne z MAIN_ENV jeśli istnieje
PG_APPUSER="app_user"
PG_APPPASS="zjedzit09"
PG_DB="saas_db"
DASH_ADMIN_TOKEN=""

if [[ -f "$MAIN_ENV" ]]; then
  # shellcheck disable=SC1090
  set +u; source "$MAIN_ENV"; set -u
  PG_APPUSER="${PG_APPUSER:-${PG_APPUSER:-app_user}}"
  PG_APPPASS="${PG_APPPASS:-${PG_APPPASS:-zjedzit09}}"
  PG_DB="${PG_DB:-${PG_DB:-saas_db}}"
  DASH_ADMIN_TOKEN="${DASH_ADMIN_TOKEN:-}"
fi

mkdir -p "$TEMPLATE_DIR"

# === .env TENANTA ===
cat > "${TEMPLATE_DIR}/.env" <<EOF
DASH_ADMIN_TOKEN=${DASH_ADMIN_TOKEN}
EOF

# === docker-compose.yml TENANTA ===
if [[ "$MODE" == "perdb" ]]; then
  DB_SERVICE="${SLUG}_db"
  DB_CONTAINER="${SLUG}_db"
  DB_NAME="${SLUG}_db"
  DB_URL="postgresql://${PG_APPUSER}:${PG_APPPASS}@${DB_SERVICE}:5432/${DB_NAME}"

  cat > "${TEMPLATE_DIR}/docker-compose.yml" <<EOF
services:
  ${DB_SERVICE}:
    image: postgres:15-alpine
    container_name: ${DB_CONTAINER}
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${PG_APPUSER}
      POSTGRES_PASSWORD: ${PG_APPPASS}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - ${SLUG}_db_data:/var/lib/postgresql/data
    networks:
      - ${SLUG}_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_APPUSER} -d ${DB_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 10

  ${SLUG}_app:
    build:
      context: ${CODE_DIR}
      dockerfile: Dockerfile
    container_name: ${SLUG}_app
    restart: unless-stopped
    depends_on:
      ${DB_SERVICE}:
        condition: service_healthy
    environment:
      BRAND: ${BRAND}
      SYSTEM_MODE: restaurant
      DOMAIN_ROOT: ${DOMAIN_ROOT}
      DATABASE_URL: ${DB_URL}
      DASH_ADMIN_TOKEN: \${DASH_ADMIN_TOKEN}
    volumes:
      - ${CODE_DIR}:/app:cached
    networks:
      - ${SLUG}_net
      - ovh_elvis_net

networks:
  ${SLUG}_net:
    driver: bridge
  ovh_elvis_net:
    external: true
    name: ovh_elvis_net

volumes:
  ${SLUG}_db_data:
EOF

elif [[ "$MODE" == "shareddb" ]]; then
  # wspólny Postgres (z głównego stacka)
  DB_URL="postgresql://${PG_APPUSER}:${PG_APPPASS}@zjedzit_postgres:5432/${PG_DB}"

  cat > "${TEMPLATE_DIR}/docker-compose.yml" <<EOF
services:
  ${SLUG}_app:
    build:
      context: ${CODE_DIR}
      dockerfile: Dockerfile
    container_name: ${SLUG}_app
    restart: unless-stopped
    environment:
      BRAND: ${BRAND}
      SYSTEM_MODE: restaurant
      DOMAIN_ROOT: ${DOMAIN_ROOT}
      DATABASE_URL: ${DB_URL}
      DASH_ADMIN_TOKEN: \${DASH_ADMIN_TOKEN}
    volumes:
      - ${CODE_DIR}:/app:cached
    networks:
      - ovh_elvis_net

networks:
  ovh_elvis_net:
    external: true
    name: ovh_elvis_net
EOF
else
  echo "BŁĄD: --mode musi być perdb albo shareddb"
  exit 1
fi

echo "✅ Utworzono tenant: ${SLUG}"
echo "📁 Folder: ${TEMPLATE_DIR}"
echo "▶ Start:"
echo "   cd ${TEMPLATE_DIR} && docker compose --env-file .env up -d --build"
echo ""
echo "🧪 Test /health (z kontenera Caddy lub innego w sieci ovh_elvis_net):"
echo "   docker exec -it zjedzit_caddy sh -c 'wget -qO- http://${SLUG}_app:8080/health ; echo'"
