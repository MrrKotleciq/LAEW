# Rozdział 11 — Automatyzacja, synchronizacja i utrzymanie systemu

> **Cel tego rozdziału:** sprawić, aby LAEW nie wymagał ręcznego odświeżania za każdym razem, gdy zmienisz projekt, dokumentację albo wiedzę w Second Brain.

W poprzednim rozdziale stworzyliśmy workflow:

```text
Projekt
 ↓
Git
 ↓
RAG
 ↓
Odysseus
 ↓
Agent
 ↓
Analiza
 ↓
Zmiana
 ↓
Test
 ↓
Dokumentacja
```

Teraz dodajemy automatyzację:

```text
Zmiana
 ↓
Wykrycie
 ↓
Automatyczna synchronizacja
 ↓
RAG
 ↓
Second Brain
 ↓
Odysseus
```

Nie oznacza to jednak, że wszystko powinno być automatyczne.

Nasza zasada pozostaje:

> **Automatyzujemy operacje techniczne, ale decyzje pozostawiamy człowiekowi.**

---

# 11.1 Co właściwie chcemy automatyzować?

System powinien automatycznie obsługiwać przede wszystkim:

* wykrywanie zmian,
* aktualizację indeksu RAG,
* synchronizację metadanych,
* tworzenie snapshotów,
* backup,
* kontrolę spójności dokumentacji,
* aktualizację Project Map,
* housekeeping.

Natomiast nie chcemy automatycznie:

* zmieniać architektury,
* usuwać danych,
* commitować zmian AI,
* publikować kodu,
* zmieniać krytycznej konfiguracji.

---

# 11.2 Automatyzacja warstwowa

Nie budujemy jednego wielkiego skryptu.

Tworzymy warstwy:

```text
                Automation
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
     Git          RAG        Knowledge
       │            │            │
       ▼            ▼            ▼
    Hooks        Indexer       Sync
```

Każdy komponent wykonuje jedno zadanie.

---

# 11.3 Git jako źródło zdarzeń

Git jest idealnym punktem wejścia dla automatyzacji.

Git posiada mechanizm **hooks**, czyli skryptów uruchamianych przy określonych zdarzeniach, np. `pre-commit`, `post-commit`, `post-merge` czy `pre-push`. Git pozwala również zmienić domyślną lokalizację hooków przez `core.hooksPath`. ([Git][1])

Możemy więc zrobić:

```text
git commit
     ↓
post-commit
     ↓
AI Workspace Sync
```

---

# 11.4 Dlaczego `post-commit`?

Nie chcemy indeksować projektu przed każdym commitem.

Najpierw użytkownik wykonuje:

```text
git commit
```

Jeżeli commit się powiedzie:

```text
post-commit
```

uruchamia synchronizację.

Czyli:

```text
Zmiany
 ↓
Commit
 ↓
Commit OK
 ↓
Synchronizacja
```

Dzięki temu RAG może zawsze odpowiadać na podstawie konkretnego stanu projektu.

---

# 11.5 Ale nie każda zmiana wymaga RAG

Załóżmy:

```text
README.md
```

został zmieniony.

Aktualizacja RAG ma sens.

Ale:

```text
build/
```

zmienił 500 plików.

Nie indeksujemy tego.

Dlatego synchronizator powinien posiadać reguły:

```text
INCLUDE

src/
include/
docs/
README.md
ARCHITECTURE.md
hardware/
```

oraz:

```text
EXCLUDE

.git/
build/
dist/
node_modules/
__pycache__/
.cache/
```

---

# 11.6 Incremental RAG

To jedna z najważniejszych optymalizacji.

Nie robimy:

```text
1000 plików
 ↓
usuń całą bazę
 ↓
indeksuj 1000 plików
```

Robimy:

```text
Git diff
 ↓
3 zmienione pliki
 ↓
usuń stare chunki tych plików
 ↓
utwórz nowe embeddingi
 ↓
dodaj nowe chunki
```

Przykład:

```text
Projekt:

5000 plików

Zmiana:

4 pliki
```

System powinien przetworzyć:

```text
4 pliki
```

a nie:

```text
5000 plików
```

---

# 11.7 Hashowanie dokumentów

Żeby wiedzieć, czy plik faktycznie się zmienił, możemy przechowywać hash.

Przykład:

```text
README.md

SHA256:
a81d9f...
```

Po synchronizacji:

```text
Nowy SHA256:
a81d9f...
```

Jeżeli hash jest identyczny:

```text
SKIP
```

Jeżeli różny:

```text
REINDEX
```

---

# 11.8 Pipeline synchronizacji

Docelowy pipeline:

```text
                 Git Event
                     │
                     ▼
               Detect Changes
                     │
                     ▼
                 Filter
                     │
                     ▼
              Hash Comparison
                     │
             ┌───────┴───────┐
             ▼               ▼
          Unchanged        Changed
             │               │
            SKIP             ▼
                       Re-chunk
                           │
                           ▼
                       Embeddings
                           │
                           ▼
                       Vector DB
                           │
                           ▼
                         DONE
```

---

# 11.9 Synchronizacja Second Brain

Obsidian jest trochę inny.

Nie chcemy, aby każda zmiana notatki powodowała ciężką operację.

Dlatego możemy zastosować:

```text
Obsidian
   ↓
Filesystem watcher
   ↓
Change queue
   ↓
Debounce
   ↓
RAG update
```

---

# 11.10 Dlaczego debounce?

Załóżmy, że piszesz notatkę.

Edytor zapisuje plik:

```text
1. zapis
2. zapis
3. zapis
4. zapis
5. zapis
```

Nie chcemy:

```text
RAG
RAG
RAG
RAG
RAG
```

Robimy:

```text
Zmiany
 ↓
czekaj 5–30 sekund
 ↓
brak nowych zmian
 ↓
jedna synchronizacja
```

To jest **debouncing**.

---

# 11.11 Kolejka zmian

Warto również wprowadzić kolejkę:

```text
Change Queue
```

Przykład:

```text
src/main.c
docs/ADR-008.md
README.md
```

System zapisuje:

```text
PENDING

3 files
```

Następnie wykonuje jedną operację.

---

# 11.12 Synchronizacja w tle

Docelowo:

```text
                 LAEW
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
    Foreground          Background
        │                   │
        ▼                   ▼
    Odysseus             Indexer
        │                   │
        ▼                   ▼
     User              RAG update
```

Ty pracujesz z AI.

Indexer działa w tle.

---

# 11.13 Nie indeksujemy podczas pracy modelu

To istotna zasada.

Nie chcemy:

```text
LLM odpowiada
      ↓
RAG zaczyna przebudowę
      ↓
VRAM/RAM rośnie
      ↓
model zwalnia
```

Dlatego synchronizacja powinna mieć niski priorytet.

---

# 11.14 Scheduler

Oprócz event-driven sync możemy mieć synchronizację okresową.

Na przykład:

```text
Co 30 minut:
    sprawdź zmiany
```

albo:

```text
Po uruchomieniu PC:
    sprawdź indeks
```

albo:

```text
Po zamknięciu projektu:
    synchronizuj
```

---

# 11.15 Trzy poziomy synchronizacji

Proponuję:

### FAST

Uruchamiana po zmianie.

```text
Git
Obsidian
```

Cel:

```text
kilka sekund
```

---

### NORMAL

Uruchamiana okresowo.

```text
pełniejszy scan
```

---

### DEEP

Uruchamiana ręcznie.

```text
pełna rekonstrukcja indeksu
```

Przydatna po:

* zmianie embedding modelu,
* migracji ChromaDB,
* zmianie chunkingu,
* uszkodzeniu indeksu.

---

# 11.16 Full Reindex

Powinna istnieć komenda:

```text
laew reindex --full
```

która wykonuje:

```text
Delete index
 ↓
Scan
 ↓
Chunk
 ↓
Embed
 ↓
Store
```

Nie używamy jej codziennie.

---

# 11.17 Backup

Automatyzacja bez backupu jest niepełna.

Musimy chronić:

```text
Knowledge
Projects
Prompts
Configuration
RAG metadata
```

Ale niekoniecznie:

```text
cache
temporary files
model weights
build artifacts
```

---

# 11.18 Co backupować?

Proponowana struktura:

```text
LAEW/
│
├── knowledge/
├── prompts/
├── configs/
├── scripts/
└── manifests/
```

Backup:

```text
LAEW_backup/
```

---

# 11.19 RAG nie jest jedynym źródłem danych

To bardzo ważne.

Nie traktujemy ChromaDB jako jedynej kopii wiedzy.

Jeżeli baza wektorowa zostanie usunięta:

```text
Knowledge
 ↓
rebuild
 ↓
ChromaDB
```

możemy ją odtworzyć.

Dlatego:

> **Vector DB jest cache'em wiedzy, a nie jej źródłem prawdy.**

---

# 11.20 Backup ChromaDB

Możemy robić snapshot:

```text
snapshot/
 └── chroma/
```

ale priorytetem pozostają dane źródłowe.

Czyli:

```text
Markdown > Git > Vector DB
```

---

# 11.21 Backup 3-2-1

Docelowo:

```text
3 kopie danych

2 różne nośniki

1 kopia poza komputerem
```

Przykład:

```text
PC
│
├── SSD
├── backup HDD
└── encrypted cloud
```

Nie musimy tego wdrażać od razu.

---

# 11.22 Snapshoty

Przed dużymi zmianami:

```text
LAEW snapshot 2026-08-11
```

Powinien zawierać:

```text
config
prompts
knowledge metadata
RAG manifest
```

Nie musimy kopiować całych modeli.

---

# 11.23 Manifest systemu

Tworzymy:

```text
SYSTEM_MANIFEST.yaml
```

Przykład:

```yaml
system_version: 1.0

llm:
  provider: ollama
  model: local-model

embedding:
  model: embedding-model

vector_db:
  type: chromadb

knowledge:
  path: ./knowledge

prompts:
  version: 1.3

rag:
  chunking: semantic
  incremental: true
```

Dzięki temu możemy odtworzyć konfigurację.

---

# 11.24 Health Check

System powinien sam potrafić sprawdzić:

```text
Ollama       OK
Odysseus     OK
ChromaDB     OK
RAG          OK
Knowledge    OK
Git          OK
Embeddings   OK
```

Przykład:

```text
LAEW HEALTH

[OK] Ollama
[OK] Odysseus
[OK] ChromaDB
[OK] Knowledge
[OK] RAG
[OK] Git

Index:
12482 documents

Last sync:
2 minutes ago
```

---

# 11.25 Wykrywanie niespójności

System powinien wykrywać sytuacje:

```text
Git:
new commit

RAG:
old index
```

i zgłosić:

> RAG jest nieaktualny o 3 commity.

Albo:

```text
Obsidian:
changed notes = 8

RAG:
indexed = 5
```

Wtedy:

> 3 notatki wymagają indeksowania.

---

# 11.26 RAG Health

Przydatne metryki:

```text
Documents
Chunks
Embeddings
Last Sync
Pending Changes
Failed Documents
Index Age
```

Przykład:

```text
RAG STATUS

Documents:        8,421
Chunks:           31,280
Pending:          3
Failed:           0
Last sync:        14:02
Index age:        32 sec
```

---

# 11.27 Automatyczne wykrywanie błędów

Indexer powinien logować:

```text
ERROR

Failed to index:
docs/hardware/manual.pdf

Reason:
unsupported encoding
```

Ale nie powinien zatrzymywać całej synchronizacji.

Powinien:

```text
31 files → indexed
1 file → failed
```

i poinformować użytkownika.

---

# 11.28 Logi automatyzacji

Tworzymy:

```text
logs/
├── sync.log
├── rag.log
├── backup.log
└── health.log
```

Dzięki temu można sprawdzić:

> "Dlaczego AI nie widzi mojego nowego dokumentu?"

I znaleźć:

```text
12:41
Document detected

12:41
Embedding failed

12:41
Document marked FAILED
```

---

# 11.29 Git Hooks — minimalny zestaw

Nie chcemy 20 hooków.

Na początek:

```text
post-commit
post-merge
```

### `post-commit`

```text
commit
 ↓
RAG incremental update
```

### `post-merge`

```text
pull/merge
 ↓
RAG sync
```

---

# 11.30 `pre-commit`

`pre-commit` powinien służyć przede wszystkim do **walidacji**, a nie do uruchamiania ciężkich operacji AI.

Przykład:

```text
pre-commit

→ lint
→ format check
→ secret scan
```

Jeśli kontrola zakończy się błędem:

```text
commit STOP
```

Git oficjalnie traktuje hooki jako mechanizm uruchamiania programów w określonych momentach workflow, a hook może przerwać operację przez zakończenie działania kodem różnym od zera. ([Git][1])

---

# 11.31 Dlaczego nie używać AI w `pre-commit`?

Wyobraź sobie:

```text
git commit
 ↓
AI analiza
 ↓
30 sekund
 ↓
embedding
 ↓
model
 ↓
commit
```

Każdy commit staje się wolny.

Nie chcemy tego.

AI powinno działać:

```text
po commicie
```

albo:

```text
na żądanie.
```

---

# 11.32 Automatyzacja a kontrola użytkownika

Podział:

| Operacja               |  Automatyczna? |
| ---------------------- | -------------: |
| wykrywanie zmian       |              ✅ |
| RAG incremental update |              ✅ |
| health check           |              ✅ |
| backup                 |              ✅ |
| snapshot               | ⚙️ opcjonalnie |
| analiza dokumentacji   | ⚙️ opcjonalnie |
| zmiana kodu            |              ❌ |
| commit AI              |              ❌ |
| delete                 |              ❌ |
| deploy                 |              ❌ |

---

# 11.33 Automatyzacja Second Brain

Nie chcemy, aby AI automatycznie tworzyło setki notatek.

Zamiast:

```text
Każda rozmowa
 ↓
Notatka
```

stosujemy:

```text
Rozmowa
 ↓
AI wykrywa potencjalnie ważną informację
 ↓
PROPOSE NOTE
 ↓
Użytkownik zatwierdza
 ↓
Obsidian
```

---

# 11.34 Knowledge Promotion

To będzie bardzo ważny mechanizm.

Informacja przechodzi przez poziomy:

```text
Conversation
     ↓
Candidate Knowledge
     ↓
Validated Knowledge
     ↓
Permanent Knowledge
```

Przykład:

Rozmowa:

> "Prawdopodobnie problem powoduje DMA."

To jeszcze nie jest wiedza.

Po potwierdzeniu:

> "DMA powodowało problem."

może zostać zapisane.

---

# 11.35 Dlaczego to ważne?

Bez tego Second Brain szybko stanie się:

```text
10000 notatek
5000 hipotez
3000 duplikatów
```

czyli kolejnym chaosem.

Second Brain powinien być:

> **mały, aktualny i wartościowy.**

---

# 11.36 Automatyczne czyszczenie

System może wykrywać:

* duplikaty,
* stare notatki,
* nieaktualne dokumenty,
* uszkodzone linki,
* brakujące metadane.

Ale:

> **AI może proponować usunięcie — nie powinno usuwać samodzielnie.**

---

# 11.37 Docelowa architektura automatyzacji

```text
                       USER
                        │
                        ▼
                    ODYSSEUS
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
      GIT            OBSIDIAN         FILES
        │               │               │
        ▼               ▼               ▼
   Git Hooks       File Watcher     Change Scan
        │               │               │
        └───────────────┼───────────────┘
                        ▼
                   CHANGE QUEUE
                        │
                        ▼
                   RAG INDEXER
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
         Embeddings           Metadata
              │                   │
              └─────────┬─────────┘
                        ▼
                    CHROMADB
                        │
                        ▼
                   ODYSSEUS RAG
                        │
                        ▼
                       LLM
```

---

# 11.38 Harmonogram systemu

Proponowany harmonogram:

### Natychmiast

```text
Git commit
↓
incremental RAG
```

### Kilkanaście sekund po edycji

```text
Obsidian
↓
debounce
↓
RAG
```

### Co 30–60 minut

```text
health check
```

### Raz dziennie

```text
backup
+
consistency check
```

### Raz w tygodniu

```text
deep health check
+
backup verification
```

### Na żądanie

```text
full reindex
```

---

# 11.39 Problem Windows

Ponieważ nasze środowisko będzie działało na Twoim PC z Windowsem, automatyzacja nie powinna zakładać wyłącznie mechanizmów typowych dla Linuxa.

Dlatego warstwę automatyzacji projektujemy tak, aby skrypty były możliwie przenośne:

```text
Python
```

jako główny orchestrator.

Dzięki temu możemy korzystać z:

```text
Windows
Linux
Docker
WSL
```

bez przepisywania całego systemu.

---

# 11.40 `automation/`

Proponowana struktura:

```text
LAEW/
│
├── automation/
│   │
│   ├── sync/
│   │   ├── rag_sync.py
│   │   ├── knowledge_sync.py
│   │   └── project_scan.py
│   │
│   ├── backup/
│   │   ├── backup.py
│   │   └── verify_backup.py
│   │
│   ├── health/
│   │   └── health_check.py
│   │
│   └── hooks/
│       ├── post_commit.py
│       └── post_merge.py
```

---

# 11.41 Zasada idempotencji

Każda automatyzacja powinna być możliwie **idempotentna**.

Czyli:

```text
sync()
sync()
sync()
```

nie powinno powodować:

```text
3 × duplicate documents
```

tylko:

```text
stan końcowy = ten sam
```

To bardzo ważne dla stabilności systemu.

---

# 11.42 Odporność na awarie

Załóżmy:

```text
Git commit
 ↓
RAG update
 ↓
Ollama crash
```

Nie możemy stracić projektu.

System powinien powiedzieć:

```text
COMMIT: SUCCESS

RAG: FAILED

Reason:
embedding service unavailable

Retry:
automatic
```

Projekt pozostaje bezpieczny.

---

# 11.43 Retry

Dla błędów chwilowych:

```text
retry 1
 ↓
retry 2
 ↓
retry 3
 ↓
FAILED
```

Po trzech próbach:

```text
manual intervention required
```

Nie chcemy nieskończonej pętli.

---

# 11.44 Offline-first

To szczególnie ważne dla naszego projektu.

Jeżeli internet przestanie działać:

```text
RAG          działa
Obsidian     działa
Git          działa
Ollama       działa
Odysseus     działa
```

Research webowy:

```text
NIEDOSTĘPNY
```

Ale cały lokalny workflow nadal działa.

To jedna z głównych zalet lokalnej architektury.

---

# 11.45 Co jeżeli Odysseus jest wyłączony?

Knowledge nie może przestać działać.

Powinniśmy nadal móc:

```text
Git
Obsidian
RAG indexer
backup
health checks
```

To oznacza, że Odysseus jest **warstwą interfejsu i orkiestracji**, a nie pojedynczym punktem awarii całego systemu.

---

# 11.46 Co jeżeli ChromaDB jest uszkodzona?

Procedura:

```text
Detect corruption
 ↓
Backup verification
 ↓
Delete broken index
 ↓
Full reindex
```

Czyli:

```text
Markdown
+
Git
+
Knowledge
      ↓
REBUILD
      ↓
ChromaDB
```

---

# 11.47 Co jeżeli model się zmieni?

To szczególnie ważne.

Zmiana:

```text
Qwen
 ↓
Gemma
```

nie powinna wymagać przebudowania:

```text
Git
Obsidian
Knowledge
```

Natomiast jeżeli zmienimy **embedding model**, konieczny będzie pełny reindex, ponieważ istniejące wektory pochodzą z innej przestrzeni embeddingowej.

Dlatego:

```text
LLM change
→ no RAG rebuild necessarily

Embedding change
→ full RAG rebuild
```

---

# 11.48 Monitoring

W przyszłości możemy stworzyć prosty dashboard:

```text
┌─────────────────────────────┐
│       LAEW STATUS           │
├─────────────────────────────┤
│ Odysseus       ● ONLINE     │
│ Ollama         ● ONLINE     │
│ ChromaDB       ● ONLINE     │
│ RAG            ● HEALTHY    │
│ Git            ● CLEAN      │
│ Knowledge      ● SYNCED     │
├─────────────────────────────┤
│ Documents      8,421        │
│ Chunks         31,280       │
│ Pending        0            │
│ Last sync      12 sec ago   │
└─────────────────────────────┘
```

Na początku nie jest potrzebny.

Ale architektura powinna na niego pozwalać.

---

# 11.49 ADR

### ADR-042

Automatyzacja jest podzielona na niezależne komponenty.

---

### ADR-043

RAG korzysta przede wszystkim z incremental indexing.

---

### ADR-044

Git hooks służą do wyzwalania lekkich operacji, a nie ciężkich procesów AI.

---

### ADR-045

Vector database jest odtwarzalnym indeksem, a nie źródłem prawdy.

---

### ADR-046

Second Brain nie jest automatycznie zapełniany każdą rozmową.

---

### ADR-047

Wiedza przechodzi proces:

```text
Candidate
↓
Validated
↓
Permanent
```

---

### ADR-048

System musi być odporny na awarię pojedynczego komponentu.

---

### ADR-049

Zmiana modelu LLM nie powinna wymagać przebudowy całego systemu.

---

### ADR-050

Zmiana modelu embeddingów wymaga pełnego przebudowania indeksu RAG.

---

# 11.50 Docelowy obraz

Po wdrożeniu automatyzacji LAEW będzie działał mniej więcej tak:

```text
                         YOU
                          │
                          ▼
                       OBSIDIAN
                          │
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
           KNOWLEDGE                PROJECT
              │                       │
              │                       ▼
              │                      GIT
              │                       │
              └───────────┬───────────┘
                          ▼
                    AUTOMATION
                          │
                    ┌─────┴─────┐
                    ▼           ▼
                  RAG         BACKUP
                    │
                    ▼
                CHROMADB
                    │
                    ▼
                ODYSSEUS
                    │
             ┌──────┴──────┐
             ▼             ▼
           AGENT          TOOLS
             │             │
             └──────┬──────┘
                    ▼
                   LLM
                    │
                    ▼
                  USER
```

---

# 11.51 Najważniejszy wniosek

Po rozdziale 11 LAEW nie jest już tylko:

> "lokalnym chatbotem z RAG."

Jest:

> **samoutrzymującym się środowiskiem wiedzy i pracy nad projektami.**

Zmiana w projekcie może automatycznie doprowadzić do:

```text
Git
 ↓
Detection
 ↓
RAG
 ↓
Knowledge state
 ↓
Odysseus
```

Natomiast decyzja:

```text
"czy coś zmienić?"
```

pozostaje po Twojej stronie.

I właśnie ten podział jest kluczowy:

> **Automatyzujemy przepływ informacji, ale nie automatyzujemy odpowiedzialności inżynierskiej.**

---

# Zapowiedź Rozdziału 12

Następny rozdział będzie poświęcony **skalowaniu systemu**.

Zaczniemy od prostego przypadku:

```text
1 projekt
100 plików
100 notatek
```

a następnie przejdziemy do:

```text
10 projektów
1000+ notatek
dziesiątki repozytoriów
wiele modeli
wiele agentów
duże bazy wiedzy
```

Omówimy również, **co należy zrobić już teraz, aby późniejsza rozbudowa nie wymagała przebudowy całego LAEW od zera**.

[1]: https://git-scm.com/docs/githooks?utm_source=chatgpt.com "Git - githooks Documentation"

