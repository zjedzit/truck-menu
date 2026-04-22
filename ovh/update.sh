#!/bin/bash
# Skrypt do aktualizacji Elvisa na OVH

echo "🚀 Rozpoczynam aktualizację..."

# Idź do głównego folderu
cd "$(dirname "$0")/.." || exit

# Aktualizacja z Git
echo "📥 Pobieranie zmian z Git..."
git pull

# Idź do folderu ovh
cd ovh || exit

# Rebuild kontenerów
echo "🏗️ Przebudowywanie kontenerów..."
docker compose up -d --build

echo "✅ Gotowe! Elvis został zaktualizowany."
docker compose ps
docker compose logs -f
