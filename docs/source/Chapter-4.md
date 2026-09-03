**Rozdział 4 — Knowledge Layer (Warstwa wiedzy)**

> **To jest najważniejszy rozdział całego projektu.**

Jeżeli miałbym wskazać jedną rzecz, która najbardziej wpływa na jakość odpowiedzi AI, to nie byłby to model.

Byłaby to właśnie **warstwa wiedzy**.

---

# 4.1 Dlaczego Knowledge Layer jest ważniejszy od modelu?

Wyobraź sobie dwa komputery.

### Komputer A

* GPT-5
* Claude
* najlepszy model na świecie

Ale nie ma dostępu do:

* kodu,
* dokumentacji,
* decyzji projektowych,
* notatek.

Odpowiedzi będą często zgadywaniem.

---

### Komputer B

* lokalny model 14B

Ale posiada:

* pełne repozytorium,
* dokumentację,
* historię projektu,
* ADR,
* notatki,
* RAG,
* pamięć.

W praktyce drugi komputer bardzo często odpowie lepiej.

To właśnie dlatego Odysseus i podobne narzędzia budują pamięć oraz warstwę wiedzy wokół modelu, zamiast polegać wyłącznie na samym LLM. ([GitHub][1])

---

# 4.2 Definicja Knowledge Layer

Knowledge Layer jest jedynym miejscem, z którego AI powinno pobierać wiedzę.

Nie jest to jedna baza danych.

To logiczna warstwa składająca się z wielu źródeł.

```text
Knowledge Layer

├── Git Repository
├── Documentation
├── Architecture Decisions
├── Obsidian Vault
├── API Documentation
├── University Notes
├── Books
├── Standards
├── Hardware Documentation
└── Personal Knowledge
```

---

# 4.3 Zasada "Single Source of Truth"

Najważniejsza zasada całego systemu.

Każda informacja istnieje tylko raz.

Przykład.

Źle:

```text
README.md

README_NEW.md

README_final.md

README_v3.md
```

Dobrze:

```text
README.md
```

Jeżeli Obsidian ma odwoływać się do README,

to nie kopiujemy jego treści.

Tworzymy link.

---

# 4.4 Kategorie wiedzy

Nie każda wiedza jest taka sama.

Dlatego dzielimy ją.

## Typ A

### Wiedza projektowa

Dotyczy konkretnego projektu.

Przykład:

```text
STM32 Robot

↓

Schemat

↓

Kod

↓

Dokumentacja

↓

ADR
```

---

## Typ B

### Wiedza techniczna

Nie jest związana z projektem.

Przykład.

```text
Python

C

STM32

UART

Docker

Git

Linux
```

---

## Typ C

### Wiedza osobista

To bardzo ważna część.

Przykład.

Nie:

> użytkownik lubi kolor niebieski

Tylko:

```text
Najczęściej stosuję Clean Architecture.

Nie używam Singletonów.

Preferuję Python.

Dokumentuję decyzje.

Każdy projekt posiada README.
```

To są preferencje inżynierskie.

---

## Typ D

### Wiedza referencyjna

Czyli:

PDF

Datasheet

Normy

Manuale

Specyfikacje

---

# 4.5 Struktura katalogów

Proponuję następującą strukturę.

```text
Knowledge/

├── Programming/

├── Electronics/

├── Robotics/

├── AI/

├── Linux/

├── University/

├── Books/

├── Hardware/

├── Standards/

└── Archive/
```

---

# 4.6 Projekty

Każdy projekt posiada własną dokumentację.

Nigdy nie tworzymy projektu bez niej.

Minimalna struktura:

```text
STM32_Robot/

├── README.md

├── docs/

├── src/

├── include/

├── tests/

├── assets/

└── .git
```

---

# 4.7 Folder docs

To będzie najważniejszy folder projektu.

```text
docs/

├── Architecture.md

├── Decisions.md

├── Changelog.md

├── API.md

├── Hardware.md

├── Testing.md

├── TODO.md

└── Bugs.md
```

Nie jest to przypadkowy zestaw nazw.

Każdy plik ma jedno zadanie.

---

# 4.8 README

README nie jest reklamą projektu.

README jest instrukcją dla:

* Ciebie za pół roku,
* AI,
* przyszłych współpracowników.

Powinien odpowiadać na pytania:

* Co to jest?
* Jak uruchomić?
* Jak wygląda struktura?
* Jakie są zależności?
* Jakie są główne moduły?

---

# 4.9 Architecture.md

To dokument,

który AI będzie czytać bardzo często.

Powinien zawierać:

```text
Warstwy systemu

Diagramy

Opis modułów

Zależności

Flow danych
```

Nie opisujemy implementacji.

Opisujemy architekturę.

---

# 4.10 Decisions.md

Jeden z najważniejszych dokumentów.

Tutaj zapisujemy:

**dlaczego**

podjęliśmy daną decyzję.

Przykład.

```text
2026-08-10

Wybrano UART.

Powód:

- prostsza diagnostyka

- wystarczająca przepustowość

- mniej przewodów

Alternatywy:

SPI

CAN

Odrzucone z powodu...
```

Po roku AI nie będzie zgadywać.

Przeczyta dokument.

---

# 4.11 Bugs.md

Nigdy nie kasujemy historii błędów.

Przykład.

```text
Problem:

UART zawieszał się.

Przyczyna:

DMA nie było restartowane.

Rozwiązanie:

HAL_UART_DMAStop()

Status:

Naprawione.
```

Po roku AI może powiedzieć:

> "To wygląda podobnie do błędu z listopada."

---

# 4.12 Changelog

Nie opisujemy commitów.

Opisujemy zmiany.

```text
v0.3

Dodano:

obsługę DMA

Naprawiono:

scheduler

Usunięto:

stary driver PWM
```

---

# 4.13 ADR (Architecture Decision Records)

To będzie jeden z filarów projektu.

Każda ważna decyzja dostaje własny dokument.

Przykład.

```text
docs/ADR/

ADR-001-UART.md

ADR-002-FreeRTOS.md

ADR-003-PWM.md
```

Przykład.

```text
Status:

Accepted

Decision:

Używamy FreeRTOS.

Reason:

Projekt będzie wielowątkowy.

Consequences:

Większa złożoność.

Lepsza skalowalność.
```

Jest to uznana praktyka dokumentowania architektury oprogramowania i bardzo dobrze współpracuje z AI, ponieważ decyzje są zapisane w ustrukturyzowany sposób.

---

# 4.14 Obsidian

Obsidian nie przechowuje kodu.

Obsidian przechowuje wiedzę.

Przykład.

```text
Robotics/

STM32/

Python/

Docker/

Linux/

Algorithms/

Ideas/

Research/
```

Każda notatka powinna odpowiadać jednemu zagadnieniu.

Nie tworzymy notatek typu:

```text
Nowe notatki.txt
```

---

# 4.15 Zależności

Knowledge Layer wygląda następująco.

```text
                 Knowledge

         ┌─────────┼─────────┐
         │         │         │
         ▼         ▼         ▼

    Projekty   Dokumentacja  Obsidian

         │         │         │

         └─────────┼─────────┘

                   ▼

               ChromaDB

                   ▼

               Embeddings

                   ▼

                 Odysseus

                   ▼

                   LLM
```

Odysseus wykorzystuje ChromaDB do przechowywania pamięci wektorowej oraz indeksowania wiedzy, dzięki czemu model otrzymuje tylko najbardziej trafne fragmenty dokumentacji zamiast całych plików. ([GitHub][1])

---

# 4.16 Czego AI NIE powinno indeksować?

To bardzo ważne.

Nie wszystko powinno trafić do RAG.

Nie indeksujemy:

```text
node_modules/

build/

dist/

bin/

obj/

Debug/

Release/

.venv/

__pycache__/

.git/

.cache/
```

Nie mają wartości poznawczej.

---

# 4.17 Co AI powinno indeksować?

Priorytet:

⭐⭐⭐⭐⭐

```text
README.md

docs/

ADR/

Architecture.md

Decision.md
```

⭐⭐⭐⭐

```text
src/

include/
```

⭐⭐⭐

```text
tests/
```

⭐⭐

```text
images/

assets/
```

⭐

```text
logs/
```

---

# 4.18 ADR

### ADR-008

**Każdy projekt posiada folder docs.**

---

### ADR-009

**Każda decyzja architektoniczna posiada własny ADR.**

---

### ADR-010

**README jest obowiązkowy.**

---

### ADR-011

**AI indeksuje dokumentację przed kodem.**

**Uzasadnienie**

Dokumentacja zawiera intencję autora.

Kod pokazuje implementację.

Najpierw AI powinno zrozumieć **dlaczego** coś istnieje, a dopiero potem **jak** zostało zaimplementowane.

---

# Podsumowanie rozdziału

Po tym rozdziale stworzyliśmy fundament całego systemu.

Najważniejszy wniosek brzmi:

> **AI nie powinno uczyć się Twojego projektu z kodu. Powinno uczyć się go przede wszystkim z dokumentacji, a kod wykorzystywać jako potwierdzenie implementacji.**

To jedna z największych różnic między przeciętnym lokalnym chatbotem a dobrze zaprojektowanym środowiskiem AI.

---

# Zapowiedź rozdziału 5

W następnym rozdziale zaprojektujemy **Second Brain** — nie jako zbiór notatek, ale jako **system zarządzania wiedzą inżynierską**. Zdefiniujemy strukturę całego vaulta Obsidiana, standardy tworzenia notatek, sposób ich łączenia z projektami oraz rolę AI w automatycznym utrzymywaniu i aktualizowaniu tej bazy wiedzy. Będzie to jeden z najbardziej praktycznych rozdziałów całego dokumentu.

[1]: https://github.com/odysseus-dev/odysseus/blob/dev/docs/setup.md?utm_source=chatgpt.com "odysseus/docs/setup.md at dev · odysseus-dev/odysseus · GitHub"
