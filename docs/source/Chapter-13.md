# Rozdział 13 — Roadmapa wdrożenia systemu

> **Cel tego rozdziału:** przełożyć całą zaprojektowaną architekturę LAEW na konkretny, etapowy plan implementacji, który można wykonać na obecnym komputerze bez budowania całej infrastruktury jednocześnie.

Do tego momentu zaprojektowaliśmy system od strony architektonicznej. Wiemy już:

* **co** chcemy zbudować,
* **dlaczego** poszczególne komponenty są potrzebne,
* jak mają ze sobą współpracować,
* jak system ma obsługiwać projekty,
* jak ma działać RAG,
* jak ma wyglądać Second Brain,
* jak AI ma korzystać z narzędzi,
* oraz jak system ma być rozwijany w przyszłości.

Teraz należy odpowiedzieć na najważniejsze pytanie:

> **W jakiej kolejności należy to wszystko zbudować?**

---

# 13.1 Zasada wdrażania

Największym błędem byłoby rozpoczęcie od instalacji wszystkiego naraz:

```text
Docker
Ollama
Odysseus
Obsidian
Chroma
RAG
embeddingi
reranker
Git hooks
agenci
automatyzacja
monitoring
```

i próba uruchomienia całego systemu jednocześnie.

W przypadku problemu nie wiedzielibyśmy:

```text
co nie działa?
```

Dlatego system będzie budowany **warstwami**.

Każdy etap powinien:

1. działać samodzielnie,
2. być przetestowany,
3. zostać udokumentowany,
4. dopiero potem stać się fundamentem następnego etapu.

---

# 13.2 Docelowa roadmapa

Cały proces można przedstawić następująco:

```text
                 ┌─────────────────────┐
                 │       ETAP 0        │
                 │    Przygotowanie    │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │       ETAP 1        │
                 │     Ollama + LLM    │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │       ETAP 2        │
                 │      Odysseus       │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │       ETAP 3        │
                 │    Tools + Git      │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │       ETAP 4        │
                 │      Obsidian       │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │       ETAP 5        │
                 │        RAG          │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │       ETAP 6        │
                 │    Second Brain     │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │       ETAP 7        │
                 │    Automatyzacja    │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │       ETAP 8        │
                 │ Monitoring + Eval   │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │       ETAP 9        │
                 │    Optymalizacja    │
                 └──────────┬──────────┘
                            ▼
                 ┌─────────────────────┐
                 │      ETAP 10        │
                 │    Rozbudowa        │
                 └─────────────────────┘
```

---

# 13.3 ETAP 0 — Przygotowanie środowiska

Pierwszym krokiem jest przygotowanie komputera.

Obecna konfiguracja:

```text
CPU: Ryzen 7 3700X
GPU: RTX 4060
RAM: 16 GB
SSD: NVMe 1 TB
```

powinna być traktowana jako **ograniczenie projektowe**.

Nie próbujemy od razu uruchamiać ogromnych modeli.

---

## 13.3.1 Oprogramowanie bazowe

Podstawowe środowisko:

```text
Windows
│
├── WSL2
├── Docker Desktop
├── Git
├── Python
├── Ollama
└── Obsidian
```

Nie wszystkie komponenty muszą od razu działać w Dockerze.

---

## 13.3.2 Struktura dysku

Warto od początku ustalić strukturę:

```text
D:\LAEW\
│
├── projects\
├── knowledge\
├── models\
├── data\
├── backups\
├── config\
├── logs\
└── archive\
```

Nie powinno się mieszać:

```text
projekty
```

z:

```text
danymi AI
```

---

# 13.4 ETAP 1 — Ollama + lokalny model

Pierwszym działającym komponentem AI powinien być Ollama.

Architektura:

```text
Application
     │
     ▼
  Ollama
     │
     ▼
 Local LLM
```

Na tym etapie nie potrzebujemy jeszcze:

```text
RAG
Obsidian
multi-agent
automatyzacji
```

---

## 13.4.1 Cel etapu

Po zakończeniu:

```text
prompt
  ↓
Ollama
  ↓
model
  ↓
response
```

musi działać stabilnie.

---

## 13.4.2 Test

Należy sprawdzić:

* czy model się uruchamia,
* ile zużywa VRAM,
* jak szybko generuje tokeny,
* jak zachowuje się przy dłuższym kontekście,
* czy odpowiada poprawnie po polsku,
* jak radzi sobie z kodem,
* czy stabilnie działa przez dłuższy czas.

---

# 13.5 ETAP 2 — Odysseus

Dopiero kiedy backend modelu działa poprawnie, instalujemy Odysseus.

Architektura:

```text
                 Odysseus
                    │
                    ▼
                 Ollama
                    │
                    ▼
                  LLM
```

Odysseus staje się warstwą:

```text
UI
+
conversation
+
memory
+
tools
+
agent
```

---

# 13.6 Cel etapu

Chcemy uzyskać:

```text
USER
 ↓
Odysseus
 ↓
Ollama
 ↓
LOCAL MODEL
```

bez RAG.

Najpierw musimy upewnić się, że sam agent działa stabilnie.

---

# 13.7 ETAP 3 — Narzędzia

Teraz AI otrzymuje dostęp do narzędzi.

Najważniejsze:

```text
Filesystem
Git
Terminal
Web
```

Docelowo:

```text
                   AI
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
    Filesystem      Git        Terminal
                                  │
                                  ▼
                                 Web
```

---

# 13.8 Zasada bezpieczeństwa

Na tym etapie **nie dajemy AI nieograniczonego dostępu do komputera**.

Najpierw:

```text
read-only
```

Potem:

```text
controlled write
```

Dopiero później:

```text
automated execution
```

To szczególnie ważne przy narzędziach typu:

```text
shell
filesystem
git
```

---

# 13.9 Pierwszy prawdziwy workflow

Po tym etapie AI powinno móc zrobić coś takiego:

> „Sprawdź aktualny stan projektu.”

Agent:

```text
Git status
     ↓
Git log
     ↓
Directory structure
     ↓
README
     ↓
Relevant files
     ↓
Analysis
```

To jest dokładnie jeden z głównych celów naszego systemu.

---

# 13.10 ETAP 4 — Git jako źródło prawdy

Git powinien stać się fundamentalnym elementem LAEW.

Projekt:

```text
Project/
│
├── .git/
├── src/
├── docs/
├── tests/
└── README.md
```

AI nie powinno polegać wyłącznie na swojej pamięci.

Powinno móc sprawdzić:

```text
git status
git log
git diff
git branch
```

---

# 13.11 Zasada „current state”

Należy rozdzielić:

```text
MEMORY
```

od:

```text
CURRENT STATE
```

Pamięć może mówić:

> „Ostatnio pracowaliśmy nad modułem UART.”

Git może powiedzieć:

> „W międzyczasie zmieniono 14 plików.”

**Aktualny stan projektu zawsze powinien być weryfikowany z rzeczywistych danych.**

---

# 13.12 ETAP 5 — Obsidian

Dopiero teraz tworzymy Second Brain.

Struktura:

```text
SecondBrain/
│
├── Projects/
├── Knowledge/
├── Research/
├── University/
├── Programming/
├── Robotics/
├── AI/
└── Archive/
```

Obsidian nie powinien być traktowany jako zwykły notatnik.

Jest:

> **warstwą wiedzy długoterminowej.**

---

# 13.13 Co zapisujemy w Obsidian?

Przede wszystkim informacje, które mają wartość w przyszłości.

Na przykład:

```text
Architecture Decision
Research
Lessons Learned
Project Documentation
Experiment
Debugging Note
```

Nie trzeba zapisywać każdej rozmowy z AI.

---

# 13.14 ETAP 6 — RAG

Dopiero kiedy mamy:

```text
Projects
+
Knowledge
+
Obsidian
```

uruchamiamy RAG.

Architektura:

```text
Obsidian
   │
   ▼
Document Loader
   │
   ▼
Chunking
   │
   ▼
Embeddings
   │
   ▼
Vector DB
```

Następnie:

```text
User Query
    │
    ▼
Retriever
    │
    ▼
Relevant Documents
    │
    ▼
LLM
```

---

# 13.15 Nie indeksujemy wszystkiego

Na początku indeksujemy tylko:

```text
README
docs/
important notes
architecture
ADR
selected source files
```

Nie:

```text
.git/
node_modules/
build/
venv/
cache/
binary files
```

---

# 13.16 ETAP 7 — Integracja RAG + Odysseus

Teraz system zaczyna przypominać docelową architekturę:

```text
                     USER
                       │
                       ▼
                  ODYSSEUS
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
         Git          RAG          Tools
          │            │            │
          └────────────┼────────────┘
                       ▼
                      LLM
```

AI może teraz:

1. sprawdzić aktualny projekt,
2. znaleźć dokumentację,
3. odnaleźć wcześniejsze decyzje,
4. przeanalizować kod,
5. połączyć te informacje.

---

# 13.17 ETAP 8 — Second Brain + projekty

Teraz tworzymy relacje:

```text
Project
   │
   ├── Git
   ├── Documentation
   ├── RAG
   └── Obsidian
```

Przykładowo:

```text
Projects/
└── STM32-Robot/
    ├── repository
    ├── docs
    └── knowledge
```

AI wie wtedy:

> „Ta wiedza należy do tego projektu.”

---

# 13.18 ETAP 9 — Automatyzacja

Dopiero teraz automatyzujemy system.

Przykład:

```text
git commit
    ↓
hook
    ↓
changed files
    ↓
RAG update
```

lub:

```text
new Obsidian note
       ↓
embedding
       ↓
vector DB
```

---

# 13.19 Automatyzacja nie może być obowiązkowa

Każda automatyzacja powinna mieć możliwość:

```text
automatic
manual
disabled
```

Dzięki temu można łatwo diagnozować problemy.

---

# 13.20 ETAP 10 — Monitoring

System powinien zacząć monitorować samego siebie.

Przykładowe informacje:

```text
Model:
VRAM:
RAM:
tokens/s:
context:

RAG:
documents:
chunks:
index size:

Tools:
calls:
errors:
latency:
```

---

# 13.21 Logowanie

Każde narzędzie powinno mieć log:

```text
timestamp
tool
arguments
result
duration
status
```

Przykład:

```text
14:32:11
git_status
project=robot-controller
SUCCESS
42ms
```

To bardzo pomaga przy problemach z tool calling.

---

# 13.22 ETAP 11 — Evaluation

Następnie tworzymy testy.

Przykładowe pytania:

```text
Jaki jest aktualny branch?

Dlaczego używamy DMA?

Które pliki zostały ostatnio zmienione?

Jakie problemy pozostały w projekcie?

Jaka była ostatnia decyzja architektoniczna?
```

AI musi odpowiadać na podstawie rzeczywistych danych.

---

# 13.23 Test narzędzi

Osobno testujemy:

```text
Filesystem
✓

Git
✓

RAG
✓

Web
✓

Memory
✓
```

Jeżeli AI zaczyna zapominać sposób wywoływania narzędzi, możemy sprawdzić:

```text
prompt
tool schema
model
context
logs
```

zamiast zgadywać.

---

# 13.24 ETAP 12 — Optymalizacja

Dopiero teraz optymalizujemy:

```text
model
quantization
context
RAG
chunking
embedding
reranking
prompts
```

Nie wcześniej.

Najpierw:

> **działa**

potem:

> **działa dobrze**

na końcu:

> **działa szybko i efektywnie**

---

# 13.25 ETAP 13 — Model switching

Kiedy infrastruktura jest stabilna, możemy testować kolejne modele:

```text
Model A
Model B
Model C
```

bez zmiany reszty systemu.

To jest jeden z powodów, dla których wcześniej zdecydowaliśmy się na architekturę:

```text
Odysseus
    ↓
Provider
    ↓
Ollama
    ↓
Model
```

---

# 13.26 ETAP 14 — Multi-model

Dopiero na tym etapie warto rozważyć:

```text
Coder
Reasoning
General
Small
Embedding
Reranker
```

Przykładowo:

```text
                     Router
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
      Coder        Reasoning       General
```

---

# 13.27 ETAP 15 — Multi-agent

Multi-agent pozostaje opcjonalnym rozszerzeniem.

Dopiero gdy single-agent będzie stabilny:

```text
Single Agent
      ↓
Multi Agent
```

Przykład:

```text
                Planner
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
    Research      Code        Docs
```

---

# 13.28 Czego NIE instalować na początku?

Na początku nie potrzebujemy:

```text
Kubernetes
Kafka
Redis Cluster
Elasticsearch
10 modeli
10 agentów
skomplikowanego orchestration
```

To byłoby przerostem formy nad treścią.

---

# 13.29 Minimalny system produkcyjny

Pierwsza docelowo użyteczna wersja powinna wyglądać mniej więcej tak:

```text
┌─────────────────────────────────┐
│            USER                 │
└───────────────┬─────────────────┘
                │
                ▼
        ┌───────────────┐
        │   Odysseus    │
        └───────┬───────┘
                │
        ┌───────┼────────┐
        ▼       ▼        ▼
       Git     RAG      Tools
        │       │        │
        └───────┼────────┘
                ▼
             Ollama
                │
                ▼
             Local LLM
                │
                ▼
             Response
```

Do tego:

```text
Obsidian
   │
   ▼
Knowledge Base
   │
   ▼
RAG
```

To jest **wersja 1.0**.

---

# 13.30 Wersja 1.0 — Definition of Done

Możemy uznać system za gotowy do codziennego użytkowania, gdy spełnia następujące warunki:

### Model

* [ ] działa lokalnie,
* [ ] stabilnie wykorzystuje GPU,
* [ ] ma odpowiednią jakość odpowiedzi.

### Odysseus

* [ ] stabilnie komunikuje się z modelem,
* [ ] zachowuje historię rozmowy,
* [ ] poprawnie wywołuje narzędzia.

### Tools

* [ ] filesystem działa,
* [ ] Git działa,
* [ ] terminal działa w kontrolowany sposób,
* [ ] web działa, jeśli jest potrzebny.

### RAG

* [ ] indeksowanie działa,
* [ ] retrieval działa,
* [ ] dokumenty mają metadata,
* [ ] projekty są izolowane.

### Second Brain

* [ ] istnieje ustalona struktura,
* [ ] wiadomo gdzie zapisywać wiedzę,
* [ ] istnieją szablony dokumentów.

### Automatyzacja

* [ ] aktualizacja RAG działa,
* [ ] backup działa,
* [ ] logowanie działa.

---

# 13.31 Wersja 1.1

Po kilku tygodniach używania możemy ocenić:

```text
Co działa dobrze?
Co działa źle?
Czego brakuje?
Co jest niepotrzebne?
```

Dopiero wtedy:

```text
v1.0
 ↓
feedback
 ↓
v1.1
```

---

# 13.32 Wersja 2.0

Może zawierać:

```text
Multi-model
+
Model Router
+
Reranker
+
Advanced RAG
+
Evaluation
+
Multiple agents
```

---

# 13.33 Wersja 3.0

Docelowo system może stać się:

```text
                   LAEW
                    │
             ┌──────┴──────┐
             ▼             ▼
         Knowledge      Projects
             │             │
             └──────┬──────┘
                    ▼
               Orchestrator
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
   Research       Coding      Planning
     Agent         Agent         Agent
       │            │            │
       └────────────┼────────────┘
                    ▼
                Model Router
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
        Local     Local      API
         LLM       LLM
```

Jednak **nie jest to punkt, od którego zaczynamy**.

---

# 13.34 Priorytety

Kolejność inwestowania czasu powinna wyglądać tak:

```text
1. Stabilność
       ↓
2. Tool calling
       ↓
3. Aktualny stan projektów
       ↓
4. RAG
       ↓
5. Second Brain
       ↓
6. Automatyzacja
       ↓
7. Evaluation
       ↓
8. Optymalizacja
       ↓
9. Multi-model
       ↓
10. Multi-agent
```

To jest istotne, ponieważ **jakość infrastruktury jest ważniejsza od liczby funkcji**.

---

# 13.35 Finalna wizja

Ostatecznym celem nie jest stworzenie:

> „najbardziej zaawansowanego lokalnego chatbota”.

Celem jest stworzenie **osobistej warstwy AI nad własnym środowiskiem pracy**.

```text
                    TY
                     │
                     ▼
              ┌────────────┐
              │  LAEW AI   │
              └─────┬──────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
    PROJECTS     KNOWLEDGE     TOOLS
       │            │            │
       ▼            ▼            ▼
      Git         Obsidian     System
       │            │            │
       └────────────┼────────────┘
                    ▼
                   RAG
                    │
                    ▼
                  MODEL
```

AI nie jest tutaj właścicielem projektu.

**Ty nim jesteś.**

AI ma natomiast możliwość:

```text
zobaczyć
↓
zrozumieć
↓
wyszukać
↓
połączyć informacje
↓
przeanalizować
↓
wyjaśnić
↓
pomóc podjąć decyzję
```

a dopiero w razie potrzeby — wykonać konkretną operację.

---

# 13.36 Ostateczna architektura projektu

Po połączeniu wszystkich wcześniejszych rozdziałów otrzymujemy:

```text
                         ┌─────────────┐
                         │    USER     │
                         └──────┬──────┘
                                │
                                ▼
                    ┌────────────────────┐
                    │     ODYSSEUS AI    │
                    │                    │
                    │ Agent / Memory     │
                    │ Tool orchestration │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
            TOOLS            RAG            MEMORY
              │               │                │
       ┌──────┼──────┐        │           ┌────┴─────┐
       ▼      ▼      ▼        ▼           ▼          ▼
      Git   Files   Web   Vector DB    Session    Obsidian
              │               │
              └───────┬───────┘
                      ▼
                 CONTEXT
                      │
                      ▼
                MODEL ROUTER
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
        LOCAL       LOCAL       CLOUD
         LLM         LLM          API
```

A wszystko otoczone przez:

```text
Security
Monitoring
Backup
Automation
Evaluation
Version Control
```

---

# 13.37 Zakończenie dokumentacji

Tym rozdziałem kończymy **projekt architektury LAEW w wersji 1.0**.

Dokument przeszedł od:

```text
„Chcę lokalne AI”
```

do kompletnego projektu:

```text
Local AI Engineering Workspace
```

obejmującego:

```text
✓ architekturę
✓ modele
✓ Odysseus
✓ Ollama
✓ narzędzia
✓ Git
✓ RAG
✓ Obsidian
✓ Second Brain
✓ prompt engineering
✓ workflow
✓ automatyzację
✓ skalowanie
✓ roadmapę
```

Najważniejszą konsekwencją całej dokumentacji jest jednak to, że **nie musisz budować całego systemu od razu**.

Pierwszym realnym celem powinno być:

```text
                    ┌──────────────┐
                    │    Odysseus  │
                    └──────┬───────┘
                           │
                       Ollama
                           │
                      Local LLM
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
             Git         Files        Web
```

A następnie stopniowo:

```text
Git
 ↓
RAG
 ↓
Obsidian
 ↓
Second Brain
 ↓
Automation
 ↓
Evaluation
 ↓
Optimization
```

**To jest właściwa kolejność wdrażania naszego systemu.**

I co najważniejsze — architektura została zaprojektowana tak, aby jeśli za rok zmienisz model, Odysseusa, bazę wektorową albo nawet część infrastruktury, **nie trzeba było zaczynać projektu od zera**.