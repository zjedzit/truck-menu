# Zjedz.it POS — Katalog Funkcji

## 1. Lokalna Potęga: Edge Terminal T520
- **Baza danych Zero-Latency**: PostgreSQL działająca na lokalnym dysku SSD zapewnia natychmiastowe ładowanie stron i przetwarzanie zamówień.
- **Tryb Offline-First**: Twój POS działa bez internetu. Zamówienia są zapisywane lokalnie i synchronizowane, gdy połączenie wróci.
- **Wbudowany Serwer Web**: Brak konieczności korzystania z zewnętrznego hostingu. Terminal T520 serwuje całą aplikację dla gości i personelu.

## 2. Doświadczenie Gościa (Menu QR)
- **Dynamiczne Menu AI**: Dostępność produktów w czasie rzeczywistym na podstawie stanów w kuchni.
- **AI Storyteller**: Wciągające historie i humor dla każdego dania, generowane przez Gemini AI, aby umilić gościom czas oczekiwania.
- **Błyskawiczne Wezwanie i Płatność**: Funkcje „Wezwij kelnera" lub „Poproś o rachunek" jednym kliknięciem, natychmiast powiadamiające personel przez WebSockety.

## 3. Operacje (POS i KDS)
- **Panele Wielozadaniowe**: Specjalistyczne interfejsy dla Kelnerów (POS), Kucharzy (KDS) oraz Wydawców (Master/Expo).
- **Ochrona Personelu kodem PIN**: Bezpieczna kontrola dostępu do każdej akcji (otwieranie stolików, usuwanie zamówień, zwroty).
- **Powiadomienia na żywo**: Natychmiastowe alerty na wszystkich urządzeniach, gdy cokolwiek zmieni się w przepływie zamówienia.

## 4. Zarządzanie Sprzętem
- **Bezpośredni Wydruk ESC/POS**: Natywna obsługa termicznych drukarek bonowych (np. Elzab, Epson) podłączonych przez USB do terminala.
- **Zunifikowana Historia Wydruków**: Szczegółowe logi każdego wydrukowanego paragonu/bonu, dostępne bezpośrednio z panelu managera.

## 5. Zarządzanie (Panel Boss)
- **Analityka w czasie rzeczywistym**: Wizualne dane sprzedaży i wydajności pracowników prosto z lokalnej bazy PostgreSQL.
- **Inżynieria Menu**: Łatwa modyfikacja produktów, cen i kategorii bez konieczności pomocy programisty.
- **Ochrona Cloudflare**: Szyfrowanie SSL i zdalny dostęp zabezpieczony przez globalną sieć Cloudflare.