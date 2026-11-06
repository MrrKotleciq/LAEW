# Stage 2B.2 — zachowanie kontekstu i trudne przypadki

## Decyzja

**B — kontynuować eksperyment; nie migrować produkcji.** Nowy wariant poprawia kompletność względem structure-v1 i przy ograniczeniu do jednego wyniku także względem legacy. Przy top_k=5 trudny korpus nadal nie wykazuje przewagi nad legacy, a zwracany kontekst jest droższy. Na zamrożonym zbiorze występują regresje MRR i nDCG. Strategia pozostaje jawnie wybieranym eksperymentem, domyślna konfiguracja i produkcyjne indeksy nie zostały przełączone.

## Poprzednia ocena i przyczyny błędów

Poprzedni korpus strukturalny oznaczał zwykle pojedynczą wartość lub zdanie, nie zestaw warunków interpretacyjnych. Krótkie sekcje i pięć wyników maskowały odrywanie tabel, kodu i procedur od opisu. Nowy korpus zawiera 13 pytań, 11 z odpowiedzią, i wiele atomów dowodowych na pytanie. Zapisano go przed implementacją v2, z podziałem dev/validation; po obejrzeniu walidacji algorytm nie był dostrajany. Jest to jednak mały, samodzielnie opracowany korpus syntetyczny, bez zewnętrznej walidacji.

Diagnostyka q19 (context-q19-ranks.json): wymagany fragment Akceptacja zajmuje pozycję 6 w legacy (0,3094) i v1 (0,3276), powyżej progu 0,3. Przyczyną braku jest limit pięciu kandydatów, nie budżet ani odrzucenie progiem. W v2 fragment zajmuje pozycję 5 (0,3372). Zmiana wejścia embeddingu wpływa więc na ranking bez zmiany jego algorytmu. Nie jest to dowód, że grupowanie sekcji rozwiązało ten historyczny przypadek.

## Architektura i reprezentacje

Nowy moduł contextual_chunker.py korzysta z rozpoznawania bloków v1 bez zmiany jego znaczenia. Grupuje bloki w tej samej sekcji i dołącza nagłówki bez treści do pierwszej sekcji potomnej. Krótkie opisy, kod, tabela i końcowe zastrzeżenie tworzą jeden fragment, gdy mieszczą się w limicie. Dłuższe grupy otrzymują kontekst opisów przed i po strukturze oraz wstępów przodków, istotny dla procedur. Stały przydział na kontekst dzielony jest między kandydatów; długi opis nie wypiera automatycznie zastrzeżenia końcowego.

Cały tekst chunku, wraz z dodatkami, mieści się w chunk_size=1000. Kontekst opisowy ma najwyżej 1/4 tego limitu; powtarzany nagłówek tabeli jest dodatkowo ograniczony do 1/5, a pozostałe miejsce przypada treści źródłowej. Podział preferuje puste wiersze, potem całe wiersze, a dla ogromnej linii stosuje podział znakowy. To heurystyka granic akapitów/funkcji, bez AST. Kontynuacje kodu mają język i identyfikator grupy, tabele powtarzane kolumny.

W v2 wejście embeddingu jest dokładnie tekstem chunku, bez dodatkowego ukrytego prefiksu. Retrieved content zawiera ten sam tekst. Provider context dodaje istniejące etykiety źródła i hierarchii, a Context Assembly może ograniczyć widoczny fragment zgodnie z istniejącym budżetem. Pomiar ocenia fragmenty po Context Assembly. Tokeny są szacowane przez znaki/4, nie mierzone tokenizatorem.

Metadane zachowują dotychczasowy frontmatter, hierarchię, typ i język, zakres linii/offsetów oraz wersję. V2 dodaje context_spans, synthetic_chars, limited_context i block_id. Treść źródłową rekonstruuje się z rozłącznych start_offset/end_offset, a nie z powtarzanych prefiksów. Offsety odnoszą się do dekodowanego tekstu po normalizacji końców linii. Global/Project i aliasy wynikają z dotychczasowych zaufanych granic.

## Metoda i wyniki

Wszystkie pomiary użyły lokalnego laew-qwen3-embedding, 1024 wymiarów, progu 0,3, limitu 8000 szacowanych tokenów i osobnych tymczasowych Chroma PersistentClient. Bez zmian modelu, rankingu lub routingu. Wartości czasu są pojedynczymi pomiarami. Metryki rankingowe dotyczą unikalnych dokumentów w kolejności pierwszego trafienia; Evidence Coverage i Complete Evidence oceniają treść, więc sam Document Recall nie maskuje braków. Nie ma wiarygodnej wspólnej miary chunk Recall dla różnych granic, dlatego nie przedstawiamy jej jako porównywalnego wyniku.

### Zamrożony baseline, K=5

| Metryka | Legacy | Structure v1 | Structure v2 |
|---|---:|---:|---:|
| Document Recall | 1.0000 | 1.0000 | 1.0000 |
| Precision | 0.2417 | 0.2417 | 0.2417 |
| MRR | 0.9306 | 0.9375 | 0.9167 |
| nDCG | 0.9451 | 0.9539 | 0.9385 |
| Evidence Coverage | 0.9792 | 0.9792 | 1.0000 |
| Complete Evidence | 0.9583 | 0.9583 | 1.0000 |
| No-answer empty | 0.2500 | 0.2500 | 0.2500 |
| Średni szacowany kontekst | 243.5000 | 244.3929 | 242.3929 |
| Chunki globalne | 15.0000 | 15.0000 | 15.0000 |
| Embeddingi obu zakresów | 16.0000 | 16.0000 | 16.0000 |
| Średnie znaki | 107.6667 | 109.6667 | 109.6667 |
| Maksymalne znaki | 155.0000 | 158.0000 | 158.0000 |
| Chunki <64 znaków | 0.0000 | 0.0000 | 0.0000 |
| Przekroczenia limitu | 0.0000 | 0.0000 | 0.0000 |
| Przygotowanie (s) | 0.0136 | 0.0143 | 0.0182 |
| Indeksowanie (s) | 3.4438 | 3.7868 | 3.3372 |
| Indeks na dysku (B) | 1151304.0000 | 1171784.0000 | 1179976.0000 |

Kategorie językowe, multi-document oraz podział dev/validation i rozkład długości znajdują się w odpowiednich plikach JSON.

| Zapytanie | Evidence Legacy | Evidence v1 | Evidence v2 |
|---|---:|---:|---:|
| q01 | 1.000 | 1.000 | 1.000 |
| q02 | 1.000 | 1.000 | 1.000 |
| q03 | 1.000 | 1.000 | 1.000 |
| q04 | 1.000 | 1.000 | 1.000 |
| q05 | 1.000 | 1.000 | 1.000 |
| q06 | 1.000 | 1.000 | 1.000 |
| q07 | 1.000 | 1.000 | 1.000 |
| q08 | 1.000 | 1.000 | 1.000 |
| q09 | 1.000 | 1.000 | 1.000 |
| q10 | 1.000 | 1.000 | 1.000 |
| q11 | 1.000 | 1.000 | 1.000 |
| q12 | 1.000 | 1.000 | 1.000 |
| q13 | 1.000 | 1.000 | 1.000 |
| q14 | 1.000 | 1.000 | 1.000 |
| q15 | 1.000 | 1.000 | 1.000 |
| q16 | 1.000 | 1.000 | 1.000 |
| q17 | 1.000 | 1.000 | 1.000 |
| q18 | 1.000 | 1.000 | 1.000 |
| q19 | 0.500 | 0.500 | 1.000 |
| q20 | 1.000 | 1.000 | 1.000 |
| q21 | 1.000 | 1.000 | 1.000 |
| q22 | 1.000 | 1.000 | 1.000 |
| q27 | 1.000 | 1.000 | 1.000 |
| q28 | 1.000 | 1.000 | 1.000 |

### Trudny korpus, K=5

| Metryka | Legacy | Structure v1 | Structure v2 |
|---|---:|---:|---:|
| Document Recall | 1.0000 | 1.0000 | 1.0000 |
| Precision | 0.2182 | 0.2182 | 0.2182 |
| MRR | 1.0000 | 1.0000 | 1.0000 |
| nDCG | 1.0000 | 1.0000 | 1.0000 |
| Evidence Coverage | 1.0000 | 0.9091 | 1.0000 |
| Complete Evidence | 1.0000 | 0.7273 | 1.0000 |
| No-answer empty | 0.0000 | 0.0000 | 0.0000 |
| Średni szacowany kontekst | 404.6154 | 368.1538 | 706.8462 |
| Chunki globalne | 33.0000 | 44.0000 | 25.0000 |
| Embeddingi obu zakresów | 34.0000 | 45.0000 | 26.0000 |
| Średnie znaki | 490.3333 | 312.1364 | 687.2000 |
| Maksymalne znaki | 1000.0000 | 1000.0000 | 1000.0000 |
| Chunki <64 znaków | 9.0000 | 16.0000 | 1.0000 |
| Przekroczenia limitu | 0.0000 | 0.0000 | 0.0000 |
| Przygotowanie (s) | 0.0496 | 0.0102 | 0.0161 |
| Indeksowanie (s) | 24.0372 | 24.2544 | 26.5014 |
| Indeks na dysku (B) | 1306952.0000 | 1409352.0000 | 1306952.0000 |

Kategorie językowe, multi-document oraz podział dev/validation i rozkład długości znajdują się w odpowiednich plikach JSON.

| Zapytanie | Evidence Legacy | Evidence v1 | Evidence v2 |
|---|---:|---:|---:|
| h01 | 1.000 | 1.000 | 1.000 |
| h02 | 1.000 | 1.000 | 1.000 |
| h03 | 1.000 | 1.000 | 1.000 |
| h04 | 1.000 | 1.000 | 1.000 |
| h05 | 1.000 | 0.667 | 1.000 |
| h06 | 1.000 | 0.667 | 1.000 |
| h07 | 1.000 | 1.000 | 1.000 |
| h08 | 1.000 | 0.667 | 1.000 |
| h09 | 1.000 | 1.000 | 1.000 |
| h10 | 1.000 | 1.000 | 1.000 |
| h11 | 1.000 | 1.000 | 1.000 |

### Trudny korpus, K=1 — diagnostyka

| Metryka | Legacy | Structure v1 | Structure v2 |
|---|---:|---:|---:|
| Document Recall | 0.9545 | 0.9545 | 0.9545 |
| Precision | 1.0000 | 1.0000 | 1.0000 |
| MRR | 1.0000 | 1.0000 | 1.0000 |
| nDCG | 1.0000 | 1.0000 | 1.0000 |
| Evidence Coverage | 0.5909 | 0.2955 | 0.7576 |
| Complete Evidence | 0.4545 | 0.0909 | 0.5455 |
| No-answer empty | 0.0000 | 0.0000 | 0.0000 |
| Średni szacowany kontekst | 80.3846 | 37.2308 | 109.9231 |
| Chunki globalne | 33.0000 | 44.0000 | 25.0000 |
| Embeddingi obu zakresów | 34.0000 | 45.0000 | 26.0000 |
| Średnie znaki | 490.3333 | 312.1364 | 687.2000 |
| Maksymalne znaki | 1000.0000 | 1000.0000 | 1000.0000 |
| Chunki <64 znaków | 9.0000 | 16.0000 | 1.0000 |
| Przekroczenia limitu | 0.0000 | 0.0000 | 0.0000 |
| Przygotowanie (s) | 0.0089 | 0.0109 | 0.0129 |
| Indeksowanie (s) | 24.6314 | 28.1708 | 28.3776 |
| Indeks na dysku (B) | 1306952.0000 | 1409352.0000 | 1302856.0000 |

Kategorie językowe, multi-document oraz podział dev/validation i rozkład długości znajdują się w odpowiednich plikach JSON.

| Zapytanie | Evidence Legacy | Evidence v1 | Evidence v2 |
|---|---:|---:|---:|
| h01 | 1.000 | 0.333 | 1.000 |
| h02 | 0.000 | 0.000 | 0.000 |
| h03 | 0.500 | 0.500 | 0.500 |
| h04 | 0.000 | 0.000 | 0.667 |
| h05 | 0.000 | 0.333 | 0.667 |
| h06 | 1.000 | 0.000 | 1.000 |
| h07 | 1.000 | 0.000 | 1.000 |
| h08 | 1.000 | 0.333 | 1.000 |
| h09 | 0.500 | 0.250 | 1.000 |
| h10 | 1.000 | 1.000 | 1.000 |
| h11 | 0.500 | 0.500 | 0.500 |

## Koszty i ograniczenia

Na trudnym korpusie v2 zawiera 3508 znaków dodatków syntetycznych na 17245 indeksowanych znaków obu zakresów, około 20,3%. Oryginalne zakresy są rozłączne; dodatki nie są kopiami oryginalnych danych na potrzeby rekonstrukcji. V1 i legacy mają odmienną duplikację (powtarzane kolumny lub overlap), więc same sumy znaków nie dowodzą utraty tekstu. Testy v2 sprawdzają partycję zakresów i ograniczenie rozmiaru niezależnie od treści syntetycznej. Wzrost średniego kontekstu przy K=5 jest znaczący i nie jest uzasadniony przewagą nad legacy w tym korpusie. Rozmiar dyskowy obejmuje SQLite i strukturę Chroma, nie tylko wektory; pojedynczy pomiar nie dowodzi oszczędności produkcyjnej.

Pozostają ograniczenia liniowego parsera: brak pełnego CommonMark i Setext, brak rozumienia semantyki kodu, możliwe przecięcie długiej funkcji lub komórki, skracanie bardzo szerokich kolumn i kontekstu. Flaga limited_context wskazuje ograniczenie, ale nie gwarantuje samodzielności każdego fragmentu. Wstępy rodziców są heurystyką — bardzo długi wstęp może utracić istotne zastrzeżenie. Małe podsekcje mieszczące się w limicie nie otrzymują automatycznie kontekstu rodzica. Testy nietypowych danych sprawdzają niezawodność i brak utraty, a nie pełne zrozumienie semantyczne.

## Synchronizacja, wdrożenie i rollback

Wersja v2 jest osobnym składnikiem fingerprintu i ID, pozostawiając legacy/v1 odtwarzalne. Standardowy synchronizator planuje odczyt i embedding przed zapisem, upsertuje nową reprezentację i usuwa stare ID. Błąd po częściowym zapisie blokuje standardowy retrieval przez istniejącą generację; ponowienie synchronizacji uzgadnia rekordy. Dodano kontrolę strategii w statusie freshness i zapisano strategię w markerze generacji. To ochrona współpracujących procesów, nie transakcja ani zabezpieczenie przed zewnętrznym klientem Chroma omijającym protokół.

Nie wykonano migracji produkcji. Nowa strategia wymaga nowego indeksowania i jest dostępna przez jawny konstruktor KnowledgeBase oraz runner eksperymentu. Przed ewentualnym wdrożeniem: odrębna baza/instancja Chroma, pełne indeksowanie Global i wszystkich projektów, walidacja kompletności i metadanych, zachowanie starej konfiguracji i bazy, spójne przełączenie wszystkich procesów dopiero po zatwierdzeniu. Rollback przełącza razem kod, konfigurację i stary indeks, a następnie synchronizuje zmiany plików powstałe od przełączenia. Samo cofnięcie flagi w tej samej kolekcji wymaga pełnej synchronizacji. Blue-green nie zostało zaimplementowane.

## Pliki i zakres

Nowe: laew/rag/contextual_chunker.py (algorytm), tests/rag/hard_cases_v1 i generator (zamrożone dane), test_contextual_chunker.py oraz test_contextual_evaluation.py (inwarianty i ocena), diagnose_q19.py (diagnostyka). Zmienione w tej iteracji: knowledge_base.py (integracja v2), sync.py (wersja w freshness), rag_baseline.py (trzy strategie, K=1/5, dowody i koszty). Nie dodano zależności. Istniejące zmiany executor.py, routing.py i dokumentacji niezwiązanej z eksperymentem pozostawiono.

## Analiza przypadków

- **h09, długi kod, K=1:** legacy odzyskuje 50% atomów, v1 25%, v2 100%. W v2 opis jednostek i znaczenia kanałów pozostaje przy fragmencie funkcji. Wzrost wynika z jawnego kontekstu dodanego do chunku, ze zmierzonym kosztem.
- **h04/h05, duża tabela, K=1:** v2 odzyskuje po 66,7% atomów, legacy 0%. Nadal brakuje pełnego zestawu wartości i ograniczeń; odległych wierszy nie można zagwarantować samą lokalną segmentacją. Przy K=5 wszystkie warianty odzyskują pełne dowody dla tych pytań.
- **h01 i h06, opis z kodem:** przy K=1 v2 odzyskuje komplet dowodów, v1 odpowiednio 33,3% i 0%; legacy również odzyskuje komplet. Jest to naprawa ograniczenia v1, nie przewaga nad legacy.
- **h02, nominalne parametry kontra maksymalne:** przy K=1 wszystkie strategie mają 0% wymaganych atomów pomimo znalezienia właściwego dokumentu. Pobrano niewłaściwy fragment; powiększenie lokalnego opisu tabeli nie zapewnia poprawy rankingu na to pytanie. Przy K=5 komplet dowodów jest dostępny.
- **h03, procedura, K=1:** wszystkie strategie mają 50% pokrycia. Powtarzanie wstępu nie gwarantuje znalezienia odległego kroku końcowego. Przy K=5 wszystkie osiągają komplet.
- **h11, dwa dokumenty, K=1:** wszystkie strategie mają 50%, ponieważ jeden wynik nie dostarcza dwóch dokumentów. To ograniczenie diagnostycznego K=1, nie błąd parsera.
- **q13, zamrożony baseline:** pozycja pierwszego trafienia pogarsza się z 1 do 2 w v2. q09 poprawia się z pozycji 3 do 2. Ogólne MRR v2 spada do 0,9167 wobec 0,9306 legacy i 0,9375 v1. Nie ukrywamy tej regresji za poprawą Evidence Coverage q19.
- **No-answer:** wszystkie warianty zwracają wyniki dla obu nowych pytań bez odpowiedzi; brak poprawy. Nie wprowadzano dodatkowego filtra, kalibracji progu ani routingu.

## Wykonane testy

Pełna regresja offline: `.venv/Scripts/python.exe -m pytest tests -m 'not live and not ollama' -q`, z TEMP/TMP i basetemp pod `.context-eval-temp`. Wynik: **1362 passed, 4 skipped, 2 deselected, 3 failed**, 188,82 s. Kolekcja tego przebiegu zawierała już testy v2, lecz nie dwa dodane później testy ewaluatora. Ostatnie dwa testy są objęte osobnym zestawem opisanym niżej.

Dwa błędy dotyczyły nieaktualnych liczników w PROJECT_STATUS: faktycznie zbierane jest 938 testów jednostkowych w 48 plikach. Zaktualizowano dokumentację, bez zmiany asercji testów. Trzeci błąd to `test_chief_uses_selected_project_and_shared_global`: izolowane ChromaDB zgłosiło `Error creating hnsw segment reader: Nothing found on disk`. Nie ma dowodu, że przyczyną jest v2 (test używa domyślnego legacy), ale błąd pełnego przebiegu pozostaje potwierdzony. Nie został zamaskowany.

Ponowienie całego pliku walidacji dokumentacji i pliku scope Chief Agenta: **8 passed**, 4,48 s. To nie unieważnia sporadycznego błędu pełnego przebiegu. Pełnego pakietu po aktualizacji liczników nie powtarzano. Zachowano logi `context-full-regression.log` i `context-recheck.log`.

Osobny zestaw nowego i poprzedniego chunkera, ewaluatorów, synchronizacji i zakresów Chief Agenta: **46 passed**, 3,34 s; bez pominięć i błędów. Obejmuje kontrolę partycji treści, zakresów linii, wielkości dodatków, odzyskania po częściowym błędzie zapisu, usuwania dokumentów, aktualizacji kodu/tabel, zmiany strategii i rollbacku. Nie wszystkie scenariusze uruchomiono osobno na każdym rodzaju persystencji; pełny zestaw offline zawiera istniejące testy blokad, trwałego Chroma, crash recovery, prefetch, RagTool i Context Assembly. Atrapy sprawdzają mechanikę; dziewięć pomiarów jakości (trzy strategie, baseline K=5 i hard cases K=5/K=1) korzysta z rzeczywistego lokalnego modelu embeddingowego.

Przy dostępie do endpointu i pełnej regresji użyto uzgodnionej ścieżki poza sandboxem; produkcyjne gniazda w regresji są odcinane istniejącą fixture offline_service_boundary. Nie restartowano Workbench, nie użyto płatnych API, nie zapisywano produkcyjnego vaultu, Chroma, Memory ani rozmów. Nie wykonano commitów, push ani zmiany gałęzi.

## Backlog i kolejny krok

Zachowano wszystkie wcześniejsze pozycje backlogu. Do istniejącego zadania weryfikacji środowiska dopisano konkretne wystąpienie błędu izolowanego HNSW. Nie oznaczono go jako naprawionego. Nowe ograniczenia v2 pozostają częścią eksperymentu, nie rozbudowano systemu zadań.

Rekomendacja: **kontynuować eksperyment (B)**. Przed migracją potrzebne są niezależne dokumenty techniczne o większej różnorodności, większy polski zbiór walidacyjny, sprawdzenie szerokich tabel oraz decyzja o akceptowalnym koszcie kontekstu. Przy K=5 wzrost kosztu bez przewagi nad legacy nie uzasadnia przełączenia produkcji. Mocniejszy wynik przy K=1 wskazuje potencjał zachowania kontekstu, ale K=1 nie jest proponowaną polityką retrievalu LAEW. Kalibracja Memory-to-RAG, ranking i embeddingi pozostają poza tą iteracją.

Uwaga porządkowa: po usunięciu wygenerowanych danych tymczasowych pozostały dwa katalogi repozytoriów testowych pod `.context-eval-temp/full`, zablokowane przez proces środowiska. Nie kończono obcych procesów w celu ich usunięcia. Logi pomiarów i regresji skopiowano do docs/reports; pozostałe katalogi są artefaktami testów, nie danymi produkcyjnymi.
