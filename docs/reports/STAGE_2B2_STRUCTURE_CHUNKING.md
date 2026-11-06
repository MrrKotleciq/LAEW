---
type: report
title: Stage 2B.2 Structure-Aware Chunking Evaluation
scope: project
status: draft
read_when:
  - reviewing structure-aware chunking and its deployment
---

# Stage 2B.2 — ocena chunkingu strukturalnego

## Status i zalecenie

Wdrożono eksperymentalny wariant `structure-v1`, dostępny wyłącznie przez jawny argument konstruktora `KnowledgeBase`. Domyślny runtime pozostaje przy dotychczasowej strategii. Nie rekomendujemy jeszcze migracji produkcyjnej: niewielki test wykazał poprawę części wskaźników rankingu na zamrożonym zbiorze, lecz nie poprawę pokrycia dowodów, a dodatkowy korpus nie wykazał przewagi w tym zakresie. Wymagane jest dalsze sprawdzenie większego i trudniejszego korpusu oraz przedstawionych niżej ograniczeń strukturalnych. Nie przeprowadzono migracji produkcyjnego indeksu.

## Implementacja

Lekki parser liniowy rozpoznaje nagłówki ATX, ich hierarchię, ogrodzone bloki kodu z użyciem backticków i tyld oraz tabele z wierszem separatora. Pozostały tekst, w tym listy, cytaty i linki, pozostaje tekstem źródłowym. Niezamknięty blok kodu trwa do końca dokumentu. Długie bloki są dzielone na granicach wierszy, a bardzo długi wiersz znak po znaku; tekst fragmentu ma maksymalnie `chunk_size` znaków. W dużych tabelach powtarzany jest nagłówek i separator, o ile mieszczą się w połowie budżetu. Wariant ten nie stosuje overlapu zwykłego tekstu. Odcinki źródłowe stanowią rozłączny podział treści bez frontmatteru; jawnie powtarzany nagłówek tabeli jest dodatkiem. Hierarchia trafia do metadanych, kontekstu i wejścia embeddingu; prefiks wejścia embeddingu jest ograniczony do jednej czwartej rozmiaru chunku, oprócz etykiety, więc wejście embeddingu może być dłuższe niż sam chunk.

Dodatkowe metadane obejmują strategię, hierarchię, rodzaj treści, język bloku, indeks oraz zakres wierszy i offsetów w dekodowanym tekście źródłowym po normalizacji końców linii Pythona. Zachowano dotychczasowe metadane notatki i zaufany zakres źródła. Frontmatter jest parsowany istniejącym parserem, a nie dołączany do treści chunku. Ścieżki logiczne są nadal tworzone w istniejącym pipeline.

Istotne ograniczenia: parser nie jest kompletną implementacją CommonMark; nie rozpoznaje m.in. nagłówków Setext ani tabel bez zwykłego separatora. Opis i następujący po nim kod lub tabela tworzą osobne fragmenty. Długie listy mogą rozdzielić warunki wstępne od dalszych kroków. Części dużego bloku kodu nie dostają syntetycznych ogrodzeń, a język pozostaje w metadanych. Bardzo szeroki nagłówek tabeli albo pojedynczy wiersz dłuższy od limitu nie gwarantuje samodzielnej interpretacji każdego fragmentu. Krótkie fragmenty zawierające wyłącznie nagłówki występują w rozbudowanych dokumentach. To ograniczenia wymagające dodatkowej pracy przed uznaniem wszystkich kryteriów strukturalnych za spełnione.

## Metoda

Oba warianty indeksowano oddzielnie w tymczasowym Chroma PersistentClient. Użyto tego samego lokalnego endpointu `laew-qwen3-embedding` (1024 wymiary), tych samych pytań, `top_k=5`, progu 0,3 i limitu kontekstu 8000 szacowanych tokenów. Żaden produkcyjny serwer Chroma ani vault nie był używany. Dane i szczegółowe wyniki, konfiguracja, hashe i rozkłady znajdują się w plikach `stage2b2-*.json`; oryginalne pliki baseline pozostały bez zmian. Ocena dokumentów usuwa duplikaty dokumentu po pobraniu chunków; evidence coverage wymaga dokładnego fragmentu, odpowiedniej sekcji i ścieżki. Są to niewielkie zbiory z etykietami, a nie pomiar jakości odpowiedzi Chief Agenta.

## Wyniki: zamrożony Global RAG v1

| Metryka | Legacy | Structure v1 |
|---|---:|---:|
| Recall@5 dokumentów | 1,000 | 1,000 |
| Precision@5 dokumentów | 0,242 | 0,242 |
| MRR | 0,931 | 0,938 |
| nDCG@5 | 0,945 | 0,954 |
| Evidence coverage | 97,9% | 97,9% |
| Evidence coverage: multi-document | 87,5% | 87,5% |
| Recall@5: cross-language | 1,000 | 1,000 |
| MRR: cross-language | 0,881 | 0,893 |
| Puste wyniki dla pytań bez odpowiedzi | 1/4 | 1/4 |
| Globalne chunki | 15 | 15 |
| Średnia / maksimum znaków w chunku | 107,7 / 155 | 109,7 / 158 |
| Embeddingi global + project | 16 | 16 |
| Czas indeksowania obu zakresów, pojedynczy przebieg | 3,37 s | 4,05 s |
| Średni szacowany koszt kontekstu | 243,5 | 244,4 |

Szacunek kontekstu to sufit liczby znaków renderowanego kontekstu podzielonej przez cztery, nie wynik tokenizatora. Wielkości czasu są pojedynczymi pomiarami i nie stanowią wiarygodnego benchmarku wydajności. Źródła i izolacja zakresów w tych testach były poprawne. Oba warianty pomijają jeden wymagany fragment w zapytaniu wielodokumentowym.

## Osobny korpus strukturalny

`tests/rag/structure_v1` zawiera hierarchiczne i podobne sekcje, polski i angielski tekst, procedurę, opis z kodem i tabelą, długi kod i dużą tabelę oraz prywatny dokument kontrolny. Zawiera 10 pytań z odpowiedzią i jedno bez odpowiedzi. Jest mały i nie stanowi niezależnego dowodu uogólnienia.

| Metryka | Legacy | Structure v1 |
|---|---:|---:|
| Recall@5 / Precision@5 dokumentów | 1,000 / 0,200 | 1,000 / 0,200 |
| MRR / nDCG@5 / Evidence coverage | 1,000 / 1,000 / 100% | 1,000 / 1,000 / 100% |
| Puste wyniki dla pytania bez odpowiedzi | 0/1 | 0/1 |
| Globalne chunki | 20 | 22 |
| Średnia / maksimum znaków | 299,9 / 1000 | 237 / 998 |
| Embeddingi global + project | 21 | 23 |
| Czas indeksowania obu zakresów | 18,99 s | 17,31 s |
| Średni szacowany koszt kontekstu | 285,1 | 297,1 |

Liczba embeddingów wzrosła o 2/21, a średni szacowany kontekst o około 4,2%. Nie ma mierzonej przewagi w pokryciu dowodów; rozmiary pojedynczych przebiegów i zjawisko podobnych sekcji ograniczają siłę wniosków. Oba warianty zwróciły nieistotne wyniki dla pytania bez odpowiedzi.

## Synchronizacja i plan wdrożenia

`structure-v1` ma osobny składnik fingerprintu i identyfikatory chunków. Zwykła synchronizacja po pełnym odczycie i przygotowaniu embeddingów upsertuje nowe chunki i usuwa rozpoznane stare identyfikatory tego dokumentu; przy błędzie przygotowania zachowuje poprzednie rekordy. Standardowy mechanizm generacji i blokad chroni współpracujących odbiorców podczas operacji upsert/delete, które nie są transakcją Chroma. Przy niepowodzeniu po częściowym zapisie trzeba ponowić synchronizację; zewnętrzne klienty pomijające blokady nie mają tej ochrony. Bezpośrednie ładowanie `structure-v1` do niepustego magazynu jest blokowane i wymaga synchronizacji.

Bezpieczna ścieżka produkcyjna wymaga odrębnej decyzji: (1) zakończyć testy i przegląd ograniczeń; (2) zapewnić osobną instancję lub bazę Chroma z kopiami danych i odrębną konfiguracją, wykonać pełną synchronizację i walidację bez dotykania starego indeksu; (3) po zatwierdzeniu przełączyć runtime i synchronizację jako spójną jednostkę, z kontrolą generacji i izolacji projektów; (4) zachować poprzedni runtime i indeks na potrzeby rollbacku. Aktualny runtime nie udostępnia przełącznika tej strategii i nie implementuje automatycznego blue-green. Przełączenie tylko konstruktora w działającym systemie lub mieszanie procesów różnych wersji w jednej kolekcji nie jest zatwierdzonym planem. Powrót do legacy w tej samej kolekcji wymaga pełnej synchronizacji, nie tylko zmiany kodu. Test izolowany sprawdza przejście w obie strony i usunięcie starych ID.

## Weryfikacja i dalsze prace

Zestaw regresyjny RAG, parsera, synchronizacji, scope Chief Agenta i ewaluatora: 101 passed; dodatkowy test błędu embeddingu i ochrony przed mieszaniem: 5 passed łącznie z pozostałymi testami pliku. Osobny zestaw trwałego ChromaDB, izolacji projektów i blokad procesu: 20 passed. Testy używają tymczasowych magazynów i atrap embeddingów, poza pomiarami opisanymi wyżej. Pierwsza próba testów w domyślnym TEMP zakończyła się 13 błędami uprawnień WinError 5; powtórzenie z TEMP w projekcie przeszło. Pierwsza próba modelu w sandboxie zakończyła się WinError 10013; lokalny endpoint działał po uzyskaniu dostępu poza sandboxem. Pełnego pakietu regresyjnego aplikacji nie uruchomiono. Nie dodano zależności. Backlog odłożonych prac uzupełniono w istniejącym `docs/roadmap/BACKLOG.md`.
