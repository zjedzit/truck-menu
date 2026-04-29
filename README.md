# Elvis POS — Gastronomiczny System Hybrydowy (Cloud-Edge)

Elvis to nowoczesny system POS (Point of Sale) stworzony z myślą o food truckach i restauracjach, które potrzebują 100% niezawodności. Łączy moc serwera w chmurze (VPS) z lokalnym terminalem (T520) zdolnym do pracy offline.

## 📖 Dokumentacja
Cała dokumentacja została przeniesiona i zoptymalizowana w folderze `/docs`.

**Zacznij tutaj:** 👉 [**DOKUMENTACJA (00_INDEKS.md)**](docs/00_INDEKS.md)

### Szybkie linki:
- [Jak zainstalować VPS (OVH)?](docs/02_WDROZENIE_VPS.md)
- [Jak przygotować terminal T520?](docs/03_TERMINAL_T520.md)
- [Plany rozwoju (Roadmap 2026)](docs/06_ROADMAP_2026.md)

---
## 🚀 Szybki start na VPS

1. **Pobranie i aktualizacja:**
   ```bash
   cd /opt/zjedzit
   git pull origin fix-deployment-v2
   ```

2. **Uruchomienie kontenerów:**
   ```bash
   docker compose -f ovh/docker-compose.yml up -d --build
   ```

3. **Inicjalizacja bazy danych (Produkty ze zdjęciami):**
   Aby dodać domyślne produkty (Double Cheese, Dynamite Burger, Frytki Belgijskie itd.) wraz z przypisanymi zdjęciami z folderu `static/images`, wykonaj:
   ```bash
   docker exec -it zjedzit_app python seed_products.py
   ```
   *Możesz zmienić brand (np. na elvis) ustawiając zmienną środowiskową:*
   ```bash
   docker exec -e BRAND=elvis -it zjedzit_app python seed_products.py
   ```

---
*Created with ❤️ by the Zjedz.it Team*