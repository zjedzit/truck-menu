#!/bin/bash

# Script do instalacji aplikacji Elvis Burger POS na Ubuntu 24.04
# Skrypt konfiguruje środowisko, instaluje wymagane pakiety i uruchamia aplikację

set -e  # Przerwij skrypt przy pierwszym błędzie

echo "=== Instalacja aplikacji Elvis Burger POS ==="

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
sudo mkdir -p /opt/elvis
sudo chown $USER:$USER /opt/elvis

# 5. Klonowanie repozytorium (jeśli nie istnieje)
if [ ! -d "/opt/elvis/.git" ]; then
    echo "Klonowanie repozytorium..."
    cd /opt/elvis
    git clone https://github.com/sensorwifi1/elvis.zjedz.it.git .
else
    echo "Repozytorium już istnieje, aktualizacja..."
    cd /opt/elvis
    git pull
fi

# 6. Konfiguracja środowiska
echo "Konfiguracja środowiska..."
cd /opt/elvis/ovh
cp .env.example .env

echo "=== Instalacja zakończona ==="
echo "Teraz edytuj plik /opt/elvis/ovh/.env z odpowiednimi wartościami"
echo "Następnie uruchom: docker compose up -d --build"