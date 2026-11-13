# Fikcyjny profil produkcyjny bramy Atlas R3
## Kontrakt zatwierdzenia ramki
Ten dokument jest autorskim scenariuszem testowym, a nie instrukcją obsługi rzeczywistego urządzenia. W profilu produkcyjnym Atlas R3 ramka pomiarowa ma 48 bajtów. Odbiornik nie potwierdza niepełnej ramki i nie miesza jej z następną sesją. Przed potwierdzeniem odbioru należy sprawdzić długość 48 bajtów i zgodność numeru sesji. Licznik sesji jest zerowany dopiero po zakończeniu kontrolowanego rozłączenia. Sam kod odpowiedzi transportu nie jest potwierdzeniem poprawnej interpretacji pomiaru.
## Diagnostyka i wycofanie
Jeżeli numer sesji jest niezgodny, ramka trafia do kwarantanny diagnostycznej bez potwierdzenia. Kwarantanna przechowuje identyfikator sesji oraz kategorię błędu, ale nie pełne prywatne dane. Procedura wymaga porównania konfiguracji z etykietą R3 na stanowisku. Profil laboratoryjny Atlas R2 ma inny rozmiar ramki i nie jest dopuszczony do tego odbiornika. Wynik testu w laboratorium nie zastępuje zgodności wersji po stronie urządzenia produkcyjnego.
## Powiązanie z transportem
Transport TCP może dostarczyć pomiar w kilku odczytach. Poprawność produkcyjnej ramki wymaga zarówno złożenia pełnych danych, jak i kontroli sesji. Zmiana czasu oczekiwania nie uprawnia do pominięcia żadnej z tych kontroli.
