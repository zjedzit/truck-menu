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
Jeśli jesteś na serwerze OVH i chcesz uruchomić system:
```bash
cd ovh
./setup-ubuntu.sh
docker compose up -d --build
```

---
*Created with ❤️ by the Zjedz.it Team*