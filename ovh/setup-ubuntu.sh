#!/bin/bash

# Script do instalacji aplikacji Zjedz.it POS na Ubuntu 24.04
# Skrypt konfiguruje środowisko, instaluje wymagane pakiety i uruchamia aplikację

set -e  # Przerwij skrypt przy pierwszym błędzie

echo "=== Instalacja aplikacji Zjedz.it POS ==="

# 1. Aktualizacja systemu
echo "Aktualizacja systemu..."
sudo apt update
sudo apt upgrade -y

# 2. Instalacja wymaganych pakietów
echo "Instalacja pakietów..."
sudo apt install -y docker.io docker-compose-plugin git curl

# 3. Dodanie użytkownika do grupy docker
echo "Dodawanie użytkownika do grupy docker..."
sudo usermod -aG docker $USER
newgrp docker

# 4. Tworzenie katalogu projektu
echo "Tworzenie katalogu projektu..."
sudo mkdir -p /opt/zjedzit
sudo chown $USER:$USER /opt/zjedzit

# 5. Klonowanie repozytorium (jeśli nie istnieje)
if [ ! -d "/opt/zjedzit/.git" ]; then
    echo "Klonowanie repozytorium..."
    cd /opt/zjedzit
    git clone https://github.com/zjedzit/truck-menu.git .
else
    echo "Repozytorium już istnieje, aktualizacja..."
    cd /opt/zjedzit
    git pull
fi

# 6. Konfiguracja środowiska
echo "Konfiguracja środowiska..."
cd /opt/zjedzit/ovh
cp .env.example .env

echo "=== Instalacja zakończona ==="
echo "Teraz edytuj plik /opt/zjedzit/ovh/.env z odpowiednimi wartościami"
echo "Następnie uruchom: docker compose up -d --build"