# Kopia działającej bazy pomiarowej
## Kopiowanie aktywnej bazy
Interfejs SQLite Online Backup API pozwala wykonywać kopię aktywnej bazy przyrostowo. Krótkie etapy kopiowania ograniczają czas blokowania źródła. Zwykłe skopiowanie pojedynczego pliku działającej bazy nie zastępuje świadomej procedury tworzenia spójnej kopii, zwłaszcza gdy baza jest równocześnie zmieniana.
## Wynik i ponowienie
Operację inicjuje sqlite3_backup_init, etapy wykonuje sqlite3_backup_step, a zasoby zwalnia sqlite3_backup_finish. Procedura rozróżnia pomyślne zakończenie od chwilowego zajęcia źródła; SQLITE_BUSY lub SQLITE_LOCKED mogą wymagać odczekania i ponowienia. Wynik końcowy należy sprawdzić, zamiast uznać sam fakt utworzenia pliku docelowego za potwierdzenie sukcesu. Raport kopii obejmuje wynik oraz ścieżkę kontrolowanego pliku docelowego, ale nie zawartość rekordów pomiarowych.
