# Stage 2B.2 — efektywność kontekstu i decyzja

Data eksperymentu: 2026-11-05. **Decyzja B — kontynuować eksperyment, nie migrować.** V2 daje wyższe pokrycie przy dwóch wynikach na obu małych zbiorach, ale w trudnym zbiorze kosztuje więcej i traci jeden z dwóch wymaganych dokumentów w h11. Wynik nie dowodzi poprawy odpowiedzi Chief Agenta ani korzyści na rzeczywistych danych. Stage 2B.2 nie jest gotowy do bezpiecznego wdrożenia.

## Stan i metoda

Na początku drzewo Git zawierało wiele niezapisanych zmian, w tym implementacje i raporty poprzedniego eksperymentu; zachowano je. Produkcyjny runtime domyślnie używa legacy (1000 znaków, overlap 200); v1 i v2 wymagają jawnego wyboru. Prefetch w `KnowledgeTurn._prefetch` wywołuje `RagTool` z `max_results=2` i `max_context_tokens=500` **oddzielnie na wybrany zakres**; routing może nie uruchomić prefetch wcale. Pipeline ma domyślny top_k=5, limit 8000, próg 0,3 i sortuje podobieństwo bez wyuczonego rerankera. Osobny budżet promptu manifestu ma rag=8000 i total=18000, a rezerwa odpowiedzi domyślnie 2000; executor usuwa starszą historię, ale zachowuje system i bieżące pytanie, nawet gdy pozostały prompt przekracza limit.

Uruchomiono sześć nowych izolowanych indeksów Chroma PersistentClient, na zamrożonych `baseline_v1` i `hard_cases_v1`. Ten sam lokalny `laew-qwen3-embedding`, endpoint manifestu 127.0.0.1:8081, 1024 wymiary i próg 0,3; brak płatnych wywołań. Wyniki, pytania, hashe, ustawienia, czasy i teksty wyników są w sześciu plikach `efficiency-20261105-{dataset}-{strategy}.json`. Każde K jest osobnym rzeczywistym wyszukiwaniem. `runs` to przefiltrowane i posortowane wyniki pipeline przed limitem prefetch; nie zawierają kandydatów odrzuconych progiem. `prefetch.scopes` zapisuje kontekst RagTool, identyfikatory wybranych fragmentów, skrócenia i liczbę pominiętych; można je porównać z wynikami K=2. W przypadku hybrid pipeline pobiera K na każdy zakres, a prefetch wykonuje osobne zapytania. Zakresy w eksperymencie wymuszono zgodnie z etykietą datasetu, nie oceniano decyzji routingu ani wpływu Memory. W tych danych pytania są globalne.

Pokrycie to średnia dla pytań z odpowiedzią z odsetka oznaczonych atomów występujących w odpowiednim dokumencie i sekcji; nie mierzy rozumienia, poprawności odpowiedzi ani semantycznych parafraz. K=1/2/5 poniżej dotyczy pipeline z limitem 8000, a kolumna 500 rzeczywistego RagTool. Budżet to sufit znaków/4, nie tokenizer. Pełna wiadomość systemowa zawiera także instrukcje, etykietę prefetch i inne sekcje, więc podane koszty nie są całkowitym kosztem promptu.

## Wyniki

| Zbiór / strategia | Coverage@1 | Coverage@2 | Coverage@5 | Coverage po 500 | Complete po 500 | Średni koszt po 500 |
|---|---:|---:|---:|---:|---:|---:|
| baseline legacy | 64,58% | 81,25% | 97,92% | 81,25% | 75,00% | 99,3 |
| baseline v1 | 66,67% | 91,67% | 97,92% | 91,67% | 87,50% | 98,8 |
| baseline v2 | 62,50% | 91,67% | 100% | 91,67% | 87,50% | 99,0 |
| hard legacy | 59,09% | 86,36% | 100% | 86,36% | 72,73% | 142,6 |
| hard v1 | 29,55% | 58,33% | 90,91% | 58,33% | 27,27% | 103,1 |
| hard v2 | 75,76% | 92,42% | 100% | 92,42% | 81,82% | 221,4 |

Średni koszt i liczba fragmentów obejmują również pytania bez odpowiedzi. Na hard średnio dostarczono 1,92 / 2,00 / 1,92 fragmentu dla legacy/v1/v2. W h09 limit pominął po jednym fragmencie legacy i v2, bez dodatkowej utraty oznaczonego atomu. Żaden wybrany fragment nie był skrócony; obserwowana strata pokrycia przez budżet wynosi zero, co nie oznacza braku ryzyka na innych danych. Pipeline pomija niepasujący późniejszy fragment zamiast go skrócić; pierwszy może być skrócony, gdy sam nie mieści się w limicie. Cztery pytania baseline wymagające kilku dokumentów po limicie mają pokrycie legacy 0,5/0,5/1/0,5, v1 i v2 0,5/0,5/1/1. W hard h11 legacy ma 1, a v1 i v2 0,5. Ograniczenie dwóch trafień i ranking mogą więc zdominować wpływ parsera.

Na 1000 szacowanych tokenów kontekstu dla pytań z odpowiedzią przypada odpowiednio 8,87/10,15/10,12 oznaczonych atomów baseline i 13,33/11,61/10,61 hard. To suma odnalezionych atomów podzielona przez sumę kosztów, nie miara wartości informacji ani dokładnych tokenów. Na hard v2 odnajduje 26 atomów wobec 23 legacy, ale przy 2450 zamiast 1725 szacowanych tokenów dla pytań z odpowiedzią. Poprawa pokrycia ma więc wymierny koszt, a nie jest poprawą efektywności na token.

W hard h04/h05/h09 pokrycie V2 względem legacy zmienia się odpowiednio 1/3→2/3, 2/3→1 i 1/2→1; h11 1→1/2. W baseline poprawiają się q09, q11 i q22. No-answer nie jest oceną jakości odmowy; poprzedni K=5 zwracał wyniki dla obu takich pytań hard.

## Koszt i reprezentacje

Hard, legacy/v1/v2: odpowiednio 33/44/25 chunków globalnych, 34/45/26 embeddingów obu zakresów, średnio 490/312/687 znaków na globalny chunk i maksimum 1000. Wcześniejszy i bieżący kontekst K=5 wynosi 404,6/368,2/706,8 szacowanych tokenów. Większe grupy opisu z kodem, tabelą i zastrzeżeniem utrzymują potrzebne atomy razem, lecz częściej pobierają całe większe sekcje. W v2 3508 z 17245 znaków indeksowanych obu zakresów to oznaczone syntetyczne prefiksy: powtarzany opis/prerekwizyty, etykiety kontynuacji i nagłówki tabel. Legacy indeksuje 16245 znaków, v1 13799; overlap legacy również powiela tekst. Same sumy nie są porównywalnym pomiarem unikalnych informacji. Nagłówki i ścieżki występują także w atrybucji wyników; 500 obejmuje atrybucję i separatory. Nie wykonano ablacji, więc nie można liczbowo przypisać wzrostu poszczególnym elementom ani udowodnić, jaka część dodatkowych znaków jest użyteczna poza oznaczonymi atomami.

Legacy i v2 wysyłają do embeddingu tekst chunku; v1 dodaje prefiks hierarchii. V2 indeksuje i zwraca ten sam wzbogacony tekst, a pipeline dodaje atrybucję i może skrócić/pominąć wynik. Rozdzielenie reprezentacji embeddingowej i prezentacyjnej może ograniczyć koszt, ale wymaga osobnej decyzji architektonicznej i oceny; tutaj go nie wdrożono. Rozkłady długości i rozmiar indeksów są w JSON. Jednorazowe czasy indeksowania hard to 34,0/32,3/38,2 s, mediana pojedynczych zapytań K=2 170/182/196 ms; obciążenie współbieżną regresją i brak powtórzeń uniemożliwiają wnioski wydajnościowe. Długości wejścia embeddingowego v1 obejmują dodatkowy prefiks, którego `indexed_chars` nie uwzględnia. Nie mierzono rzeczywistego tokenizatora ani osobnego rozmiaru metadanych.

## Ranking i przypadki strukturalne

MRR@5 baseline dla dokumentów to 0,9306/0,9375/0,9167. W q13 właściwy `chroma.md` przechodzi z pierwszego na drugi dokument: wynik 0,5011 legacy wobec 0,4942 v2, a konkurencyjny `vault.md` 0,4752 wobec 0,5007. Teksty są krótkie i bardzo podobne; nie ma dowodu, że przyczyną jest duży chunk lub łączenie tematów. Zmiana wejścia i granic zmienia embedding i bliskie wyniki. W q09 właściwy `sampling.md` awansuje z trzeciego na drugi dokument. W q19 potrzebna sekcja `Akceptacja` jest szósta w legacy/v1, piąta w v2: to wpływ rankingu i limitu, nie dowód zmiany semantyki grupowania. MRR mierzy pierwsze trafienie pozytywnie ocenionego dokumentu, nie pozycję konkretnego fragmentu. Dane per-query i wcześniejsza diagnostyka q19 pozwalają sprawdzić szczegóły.

Istniejące testy sprawdzają długi kod, procedury, tabele, odtwarzanie zakresów oraz uszkodzony Markdown. Szerokie tabele, bardzo długie wiersze i opisy nadal mogą być dzielone lub ograniczone; `limited_context` sygnalizuje ograniczenie, ale nie gwarantuje zachowania sensu. Heurystyka nie jest pełnym CommonMark. Żadnej zmiany V2 ani nowej strategii nie wprowadzono: mała różnica jakości i regresja h11 nie uzasadniają strojenia na tym zbiorze.

## Dostarczenie do adaptera i testy

Zapisane konteksty odtworzono dla 123 przypadków przez `AgentExecutor` i prawdziwy builder payloadu adaptera llama.cpp; transport i odpowiedź zostały zastąpione atrapą. Wszystkie konteksty znalazły się w serializowanym payloadzie (`efficiency-20261105-llamacpp-replay.json`). To replay bez historii i z wymuszonymi zakresami, nie pełne uruchomienie routingu dla każdego pytania ani rzeczywisty request do modelu. Istniejące testy integracyjne w pełnej regresji dodatkowo sprawdzają rzeczywisty przebieg prefetch do obserwującego providera, RagTool, provenance, izolację projektów, synchronizację, usuwanie i obsługę błędów, z atrapami embeddingu/modelu tam, gdzie przewidują to fixture.

Pełne `pytest tests -m 'not live and not ollama' -q` w izolowanym basetemp: **1367 passed, 4 skipped, 2 deselected, 39 warnings**, 245,17 s; log `efficiency-20261105-regression.log`. Nie zmieniano asercji. Poprzedni sporadyczny błąd Chroma HNSW `Nothing found on disk` tym razem nie wystąpił; pięć dodatkowych uruchomień pliku `test_chief_rag_scopes.py` przeszło. Test używa tymczasowego katalogu i PersistentClient, dwa projekty, upsert/synchronizację i odczyt; nie wskazuje jednoznacznie przyczyny. Nie dowiedziono związku z lifecycle, cleanup, blokadami, współbieżnością ani wersją 1.5.9. Problem pozostaje w istniejącym backlogu; nie przebudowano storage. Izolowane powtórzenia nie dowodzą jego usunięcia.

## Zmiany i następny krok

Dodano wyłącznie dwa izolowane narzędzia ewaluacji `laew/eval/prefetch_efficiency.py`, `prefetch_adapter_replay.py`, nowe JSON-y, log i ten raport. Nie zmieniono produkcyjnej strategii, modelu, algorytmu wyszukiwania, konfiguracji ani danych. Odwzorowanie: `.venv/Scripts/python.exe -m laew.eval.prefetch_efficiency --dataset tests/rag/hard_cases_v1 --strategy structure-v2 --output <new-file>`; analogicznie dla pozostałych kombinacji. Replay: `.venv/Scripts/python.exe -m laew.eval.prefetch_adapter_replay --inputs 'docs/reports/efficiency-20261105-*v1-*.json' --output <new-file>`.

Następnie przygotować niezależny, większy zbiór rzeczywistych wielodokumentowych pytań z wyprzedzającymi etykietami; ocenić pełny routing i odpowiedzi modelu przy tych samych budżetach, a także powtórzyć pomiary kosztu i opóźnień bez współbieżnego obciążenia. Osobno zbadać możliwą kompaktową reprezentację po wyszukiwaniu i przedstawić warianty przed większą zmianą architektury. Ewentualne wdrożenie wymaga osobnej zgody: nowy indeks obu zakresów, walidacja kompletności i wersji, spójne przełączenie runtime i synchronizacji z kontrolą generacji, zachowanie starego indeksu i przetestowany rollback wraz z uzgodnieniem późniejszych zmian źródeł. Produkcyjnej migracji nie było.
