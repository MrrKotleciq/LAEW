# Integralność lokalnej bazy konfiguracji
## Włączanie kontroli relacji
Ustawienie PRAGMA foreign_keys dotyczy połączenia z bazą. Zmianę należy wykonać przed rozpoczęciem transakcji. Próba przełączenia kontroli kluczy obcych wewnątrz aktywnej transakcji nie zmienia ustawienia. Aplikacja nie powinna zakładać wartości domyślnej; po otwarciu połączenia ustawia ją jawnie i odczytuje wynik kontrolnego zapytania.
```sql
PRAGMA foreign_keys = ON;
PRAGMA foreign_keys;
BEGIN;
```
## Obsługa konfiguracji
Polecenia PRAGMA są rozszerzeniem SQLite, a nie przenośnym interfejsem wszystkich baz SQL. Nieznana nazwa ustawienia może zostać zignorowana bez komunikatu błędu. Dlatego procedura uruchomieniowa sprawdza wynik odczytu zamiast polegać wyłącznie na braku wyjątku. Włączenie kontroli relacji i wykonanie kopii zapasowej to osobne działania; poprawny wynik jednego nie potwierdza drugiego.
