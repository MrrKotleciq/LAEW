# Fikcyjne wydanie konfiguracji C7
## Pakiet do zatwierdzenia
Ten autorski scenariusz łączy weryfikację konfiguracji z dokumentacją pomiarów. Pakiet C7 musi zawierać wynik kopii bazy oraz protokół kalibracji C7. Operator porównuje identyfikator kopii z identyfikatorem uruchomienia. Plik o poprawnej nazwie bez potwierdzonego wyniku wykonania kopii nie spełnia tego wymagania. Protokół kalibracji musi odpowiadać temu samemu urządzeniu i nie może być zastąpiony wynikami archiwalnego C6.
## Zachowanie po niepowodzeniu
Po błędzie kopii baza źródłowa pozostaje bez zmian, a wydanie jest wstrzymane. Po błędzie kalibracji wynik kopii nie daje prawa do zatwierdzenia współczynników. Każdy warunek ma oddzielny status w raporcie, tak aby poprawne wykonanie jednej operacji nie ukrywało awarii drugiej. Następna próba zachowuje identyfikator poprzedniego nieudanego uruchomienia w dzienniku zdarzeń.
## Identyfikatory i wersje
Digest współczynników w pakiecie musi być identyczny z digestem w protokole kalibracji. Sama nazwa pliku konfiguracji nie stanowi takiej kontroli. Przywrócenie kopii oraz wycofanie wersji aplikacji są oddzielnymi zadaniami; żadne z nich nie jest wykonywane przez wyszukiwarkę dokumentacji.
