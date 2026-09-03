# Rozdział 10 — Workflow pracy z systemem

> **Do tej pory zaprojektowaliśmy poszczególne elementy. Teraz łączymy je w jeden rzeczywisty proces pracy.**

Odysseus jest obecnie pozycjonowany jako self-hosted workspace obejmujący agentów, narzędzia, MCP, pliki, shell, skills, pamięć, dokumenty i lokalne modele. ([GitHub][1])

To oznacza, że możemy zaprojektować środowisko nie jako:

```text
ChatGPT → pytanie → odpowiedź
```

ale jako:

```text
Projekt
   ↓
Git
   ↓
Dokumentacja
   ↓
Knowledge Base
   ↓
RAG
   ↓
Odysseus
   ↓
Agent
   ↓
Narzędzia
   ↓
Aktualny stan projektu
```

---

# 10.1 Główna zasada workflow

Najważniejsza zasada naszego systemu brzmi:

> **AI powinno pracować na aktualnym stanie projektu, a nie na jego wyobrażeniu.**

Dlatego nie chcemy sytuacji:

```text
Ty:
"Sprawdź mój projekt."

AI:
"Z tego co pamiętam..."
```

Chcemy:

```text
Ty:
"Sprawdź mój projekt."

AI:
→ Git status
→ struktura projektu
→ dokumentacja
→ ostatnie zmiany
→ RAG
→ analiza
```

Dopiero wtedy powstaje odpowiedź.

---

# 10.2 Cykl życia projektu

Każdy projekt powinien przechodzić przez podobny proces:

```text
             NOWY PROJEKT
                  │
                  ▼
                 GIT
                  │
                  ▼
            DOKUMENTACJA
                  │
                  ▼
            INDEKSOWANIE
                  │
                  ▼
              ODYSSEUS
                  │
                  ▼
              PRACA AI
                  │
                  ▼
           ZMIANY W PROJEKCIE
                  │
                  ▼
              GIT COMMIT
                  │
                  ▼
        AKTUALIZACJA WIEDZY
                  │
                  └───────►
```

To jest podstawowa pętla naszego systemu.

---

# 10.3 Etap 1 — utworzenie projektu

Załóżmy, że rozpoczynasz projekt:

> Sterownik robota mobilnego na STM32.

Tworzysz repozytorium:

```text
robot-controller/
```

Struktura:

```text
robot-controller/
│
├── src/
├── include/
├── tests/
├── docs/
├── hardware/
├── scripts/
│
├── README.md
├── ARCHITECTURE.md
├── CHANGELOG.md
└── .gitignore
```

Od początku projekt posiada więc strukturę umożliwiającą AI zrozumienie jego organizacji.

---

# 10.4 Etap 2 — pierwszy opis projektu

Zanim agent zacznie analizować kod, powinien znać podstawy.

Tworzymy:

```text
README.md
```

Powinien zawierać:

* cel projektu,
* zastosowanie,
* główne komponenty,
* używane technologie,
* sposób budowania,
* sposób uruchamiania,
* ograniczenia.

Przykład:

```markdown
# Robot Controller

## Purpose

Sterownik robota mobilnego.

## Hardware

- STM32
- IMU
- enkodery
- sterowniki silników

## Software

- C
- STM32 HAL
- FreeRTOS

## Build

CMake + ARM GCC
```

---

# 10.5 Etap 3 — Architecture Document

Następnie:

```text
ARCHITECTURE.md
```

Tutaj opisujemy:

```text
MCU
 │
 ├── UART
 ├── SPI
 ├── I2C
 ├── DMA
 │
 └── FreeRTOS
       │
       ├── Motor Task
       ├── Sensor Task
       └── Communication Task
```

Ten dokument będzie jednym z najważniejszych źródeł dla AI.

---

# 10.6 Etap 4 — ADR

Każda ważniejsza decyzja architektoniczna może otrzymać własny ADR.

Przykład:

```text
docs/
└── adr/
    ├── ADR-001-mcu.md
    ├── ADR-002-rtos.md
    ├── ADR-003-uart-dma.md
    └── ADR-004-sensor-bus.md
```

Przykład:

```markdown
# ADR-003 — UART przez DMA

## Status

Accepted

## Decision

UART będzie korzystał z DMA.

## Reason

Zmniejszenie obciążenia CPU.

## Alternatives

- polling
- interrupts

## Consequences

Implementacja jest bardziej złożona.
```

Dla AI jest to niezwykle wartościowe.

Kod mówi:

> **co** system robi.

ADR mówi:

> **dlaczego** został tak zaprojektowany.

---

# 10.7 Etap 5 — pierwsze indeksowanie

Dopiero teraz uruchamiamy RAG.

System analizuje:

```text
README.md
ARCHITECTURE.md
docs/
src/
tests/
hardware/
```

Tworzy:

```text
Documents
    ↓
Chunks
    ↓
Embeddings
    ↓
Vector Database
```

Odysseus posiada własną warstwę RAG oraz pamięć wektorową, więc w pierwszym etapie projektu nie dokładamy kolejnych systemów bez potrzeby. ([GitHub][2])

---

# 10.8 Etap 6 — AI poznaje projekt

Pierwsza sesja powinna być czymś w rodzaju onboardingu.

Nie:

> "Hej, co potrafisz?"

Tylko:

> "Przeanalizuj aktualny stan projektu i przygotuj jego mapę."

Agent powinien:

```text
1. Sprawdzić strukturę repozytorium.

2. Przeczytać README.

3. Przeczytać ARCHITECTURE.md.

4. Przeanalizować ADR.

5. Przeanalizować najważniejsze moduły.

6. Sprawdzić Git.

7. Wyszukać powiązane informacje w RAG.

8. Przygotować raport.
```

---

# 10.9 Project Map

Wynikiem powinien być dokument:

```text
PROJECT_MAP.md
```

Na przykład:

```markdown
# Project Map

## Architecture

STM32
↓
FreeRTOS
↓
Drivers
↓
Application

## Main modules

- drivers/
- communication/
- sensors/
- control/

## Critical dependencies

UART → DMA
IMU → SPI
Motors → PWM

## Current state

Build: PASS

Tests: 18/18 PASS

Open issues: 3
```

To będzie swego rodzaju **mapa projektu dla AI**.

---

# 10.10 Etap 7 — codzienna praca

Od tego momentu rozpoczyna się właściwy workflow.

Przykład:

> "Wczoraj wszystko działało. Dzisiaj robot nie odczytuje IMU."

Nie zaczynamy od:

```text
"Przeczytaj cały projekt."
```

Agent powinien wykonać:

```text
Git status
     ↓
Git diff
     ↓
ostatnie commity
     ↓
moduł IMU
     ↓
logi
     ↓
RAG
```

---

# 10.11 Agent jako diagnostyk

Agent przygotowuje:

```text
OBSERVED

IMU nie odpowiada po inicjalizacji.

EVIDENCE

SPI initialization kończy się sukcesem.

WHO CHANGED

Commit 8a52f1 zmienił konfigurację SPI.

HYPOTHESIS

Zmiana preskalera może powodować problem.

CONFIDENCE

High

NEXT STEP

Zweryfikować konfigurację SPI przed i po commit.
```

To jest dokładnie typ pracy, do której chcemy wykorzystać AI.

---

# 10.12 Etap 8 — użytkownik podejmuje decyzję

AI nie zmienia kodu.

Ty otrzymujesz:

```text
Problem:
SPI configuration changed.

Possible fix:
Restore previous prescaler.

Risk:
Low.

Recommended test:
Run IMU initialization test.
```

Dopiero Ty decydujesz:

> "Wprowadź zmianę."

---

# 10.13 Etap 9 — wykonanie

Agent przełącza się:

```text
INVESTIGATE
```

na:

```text
EXECUTE
```

i wykonuje **konkretnie zatwierdzoną operację**.

Następnie:

```text
Build
 ↓
Tests
 ↓
Diagnostics
```

---

# 10.14 Etap 10 — Git

Jeżeli wszystko działa:

```text
git diff
```

Agent może przygotować podsumowanie:

```text
Modified:

src/spi.c

Reason:

Restore SPI prescaler.

Tests:

18/18 PASS
```

Ale commit nadal wykonujesz Ty albo zatwierdzasz jego wykonanie.

---

# 10.15 Etap 11 — Decision Log

Jeżeli zmiana ma znaczenie architektoniczne, powinna trafić do Second Brain.

Na przykład:

```text
Knowledge/
└── Projects/
    └── RobotController/
        └── Decisions/
            └── 2026-08-11-spi-prescaler.md
```

Treść:

```markdown
# SPI Prescaler Change

## Date

2026-08-11

## Problem

IMU communication failed after configuration change.

## Investigation

Git history revealed SPI prescaler modification.

## Decision

Restore previous prescaler.

## Result

IMU communication restored.

## Lesson

SPI configuration is hardware-dependent.
```

---

# 10.16 Dlaczego nie przechowywać wszystkiego w pamięci AI?

To bardzo ważne.

Nie chcemy:

```text
AI Memory = cały projekt
```

Pamięć powinna zawierać:

* preferencje,
* ważne decyzje,
* długoterminowe fakty,
* kontekst użytkownika,
* informacje o projektach.

Natomiast szczegóły kodu powinny pozostać w:

```text
Git
+
Project Files
+
RAG
```

---

# 10.17 Trzy źródła prawdy

W naszym systemie istnieją trzy główne źródła.

## Git

Źródło prawdy dotyczące:

```text
historii
zmian
wersji
```

---

## Projekt

Źródło prawdy dotyczące:

```text
aktualnego kodu
konfiguracji
struktury
```

---

## Second Brain

Źródło prawdy dotyczące:

```text
decyzji
wiedzy
wniosków
researchu
```

AI łączy te trzy światy.

---

# 10.18 Nie mieszamy ich

Nie chcemy:

```text
Git
 ↓
automatycznie
 ↓
10 000 notatek Obsidian
```

Ani:

```text
Każdy komentarz
 ↓
Memory
```

System musi być selektywny.

---

# 10.19 Koniec sesji

Po zakończeniu pracy agent może wykonać:

```text
1. Sprawdź Git status.

2. Podsumuj zmiany.

3. Wykryj ważne decyzje.

4. Wskaż nierozwiązane problemy.

5. Przygotuj propozycję wpisu do Decision Log.

6. Zaktualizuj indeks RAG.
```

Przykład:

```text
SESSION SUMMARY

Completed:
- Fixed SPI configuration.
- Added IMU test.

Pending:
- Calibration still required.

Decision:
- SPI prescaler restored.

Tests:
18/18 PASS
```

---

# 10.20 Workflow całego dnia

Docelowo wygląda to tak:

```text
                  START DAY
                      │
                      ▼
                Git status
                      │
                      ▼
             Project changes
                      │
                      ▼
              AI context sync
                      │
                      ▼
                  WORK
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
       Research                Debugging
          │                       │
          └───────────┬───────────┘
                      ▼
                   Changes
                      │
                      ▼
                    Tests
                      │
                      ▼
                    Git
                      │
                      ▼
              Decision Log
                      │
                      ▼
                RAG update
                      │
                      ▼
                   END DAY
```

---

# 10.21 Nowy projekt vs istniejący projekt

Workflow nie może być identyczny.

### Nowy projekt

```text
Create repo
↓
Documentation
↓
Architecture
↓
RAG
↓
AI onboarding
```

### Istniejący projekt

```text
Git
↓
Analyze existing structure
↓
Documentation audit
↓
RAG
↓
Project Map
```

---

# 10.22 Workflow researchu

Second Brain powinien również obsługiwać research.

Przykład:

> "Chcę wykorzystać nowy sensor w projekcie."

Workflow:

```text
Question
 ↓
Research Agent
 ↓
Official documentation
 ↓
Datasheet
 ↓
Technical papers
 ↓
Comparison
 ↓
Decision
 ↓
ADR
```

Wtedy research nie kończy się na rozmowie z AI.

Zostaje częścią projektu.

---

# 10.23 Research → Knowledge

Przykład:

```text
Research:
Czy użyć MPU6050 czy ICM42688?
```

AI przygotowuje:

```text
Comparison
```

Ty wybierasz:

```text
ICM42688
```

System tworzy:

```text
ADR-008-sensor-selection.md
```

Od tej chwili przyszły agent może znaleźć tę decyzję przez RAG.

---

# 10.24 Najważniejsza pętla

Właściwie cały system można sprowadzić do:

```text
OBSERVE
   ↓
UNDERSTAND
   ↓
DECIDE
   ↓
ACT
   ↓
VERIFY
   ↓
DOCUMENT
   ↓
REMEMBER
```

Czyli:

```text
Obserwuj
↓
Zrozum
↓
Podejmij decyzję
↓
Działaj
↓
Zweryfikuj
↓
Udokumentuj
↓
Zapamiętaj
```

To jest **fundamentalna pętla naszego LAEW**.

---

# 10.25 Dlaczego ten workflow jest lepszy niż "AI coding agent"?

Typowy coding agent:

```text
Prompt
 ↓
Kod
 ↓
Kod
 ↓
Kod
```

Nasz system:

```text
Problem
 ↓
Aktualny stan
 ↓
Wiedza
 ↓
Historia
 ↓
Analiza
 ↓
Decyzja
 ↓
Działanie
 ↓
Weryfikacja
 ↓
Dokumentacja
```

To ogromna różnica.

---

# 10.26 Kontrola człowieka

W systemie stosujemy zasadę:

> **Human in the loop.**

AI może:

```text
READ
ANALYZE
SEARCH
PLAN
TEST
REPORT
```

Człowiek zatwierdza:

```text
CHANGE
COMMIT
DELETE
DEPLOY
```

Dzięki temu AI pozostaje **asystentem inżyniera**, a nie autonomicznym właścicielem projektu.

---

# 10.27 Workflow w Odysseusie

Odysseus już obecnie łączy agentów z narzędziami, MCP, plikami, shellem, skills i pamięcią, więc nie musimy budować osobnego "agenta orkiestrującego" od zera. ([GitHub][1])

Jednocześnie projekt należy traktować jako system z uprzywilejowanymi możliwościami. Oficjalne zalecenia bezpieczeństwa Odysseusa wskazują m.in. na konieczność ochrony dostępu do shell, plików, MCP, pamięci i innych narzędzi oraz niewystawiania usług takich jak Ollama czy ChromaDB publicznie. ([GitHub][3])

Dlatego nasza konfiguracja będzie opierać się na:

```text
Odysseus
   │
   ├── Agent
   │
   ├── RAG
   │
   ├── Memory
   │
   ├── Skills
   │
   ├── MCP
   │
   └── Tools
         │
         ├── Files
         ├── Git
         ├── Shell
         └── Web
```

---

# 10.28 Docelowy workflow LAEW

Cały system można więc przedstawić jednym diagramem:

```text
                         USER
                           │
                           ▼
                     ┌───────────┐
                     │ ODYSSEUS  │
                     └─────┬─────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
                 MEMORY          RAG
                    │             │
                    └──────┬──────┘
                           ▼
                         AGENT
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
           FILES           GIT          WEB
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                       LOCAL LLM
                           │
                           ▼
                       ANALYSIS
                           │
                           ▼
                      HUMAN DECISION
                           │
                           ▼
                         ACTION
                           │
                           ▼
                         TEST
                           │
                           ▼
                          GIT
                           │
                           ▼
                    SECOND BRAIN
                           │
                           ▼
                       RAG UPDATE
```

---

# 10.29 ADR

### ADR-036

Aktualny stan projektu jest ważniejszy niż pamięć modelu.

---

### ADR-037

Git jest źródłem prawdy dla historii zmian.

---

### ADR-038

Second Brain przechowuje wiedzę długoterminową, decyzje i wnioski, a nie kopię całego kodu.

---

### ADR-039

AI działa według pętli:

```text
OBSERVE
UNDERSTAND
DECIDE
ACT
VERIFY
DOCUMENT
REMEMBER
```

---

### ADR-040

Zmiany w projekcie pozostają kontrolowane przez użytkownika.

---

### ADR-041

Każdy projekt powinien posiadać minimalny zestaw dokumentacji przed pełną integracją z RAG.

---

# 10.30 Podsumowanie rozdziału

W tym momencie wszystkie wcześniej zaprojektowane elementy zaczynają tworzyć jeden system.

Mamy:

```text
                LAEW

                 │
     ┌───────────┼───────────┐
     ▼           ▼           ▼
 Second Brain   Projects     Git
     │           │           │
     └───────────┼───────────┘
                 ▼
                RAG
                 │
                 ▼
             Odysseus
                 │
          ┌──────┴──────┐
          ▼             ▼
        Agent         Memory
          │
     ┌────┼────┐
     ▼    ▼    ▼
   Files Git  Web
          │
          ▼
         LLM
```

Najważniejsza zmiana nastąpiła jednak na poziomie filozofii:

> **AI nie jest już miejscem, do którego przychodzisz po odpowiedź. AI staje się warstwą znajdującą się nad Twoimi projektami, wiedzą, historią zmian i narzędziami.**

I dokładnie taki system chcemy zbudować.

---

# Zapowiedź Rozdziału 11

Następny rozdział poświęcimy **automatyzacji**.

Przejdziemy od ręcznego workflow:

```text
Ty
↓
AI
↓
RAG
↓
Git
```

do:

```text
Git commit
   ↓
Hook
   ↓
Zmiana wykryta
   ↓
RAG update
   ↓
Knowledge update
   ↓
AI context refreshed
```

Omówimy **Git hooks, automatyczne indeksowanie, synchronizację Second Brain, backup, snapshoty, harmonogramy oraz mechanizmy wykrywania zmian**. Dzięki temu system będzie wymagał coraz mniej ręcznej obsługi, ale nadal pozostanie pod Twoją kontrolą.

[1]: https://github.com/odysseus-dev/odysseus?utm_source=chatgpt.com "GitHub - odysseus-dev/odysseus: Self-hosted AI workspace. · GitHub"
[2]: https://github.com/odysseus-dev/odysseus/blob/dev/app.py?utm_source=chatgpt.com "odysseus/app.py at dev · odysseus-dev/odysseus · GitHub"
[3]: https://github.com/odysseus-dev/odysseus/security?utm_source=chatgpt.com "Overview · odysseus-dev/odysseus · GitHub"

