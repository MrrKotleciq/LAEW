# Rozdział 5 — Second Brain

> **To jest rozdział, który zamienia AI z "chatbota" w prawdziwego partnera inżynierskiego.**

Po poprzednim rozdziale wiemy już **gdzie przechowywać wiedzę**.

Teraz odpowiemy na pytanie:

> **Jak tę wiedzę organizować, aby AI rzeczywiście potrafiło z niej korzystać?**

---

# 5.1 Czym jest Second Brain?

Większość ludzi uważa, że Second Brain oznacza:

> "dużo notatek."

To błędne założenie.

Second Brain nie jest magazynem.

Jest **zewnętrzną pamięcią długoterminową**.

Jego zadaniem jest:

* zapamiętywanie,
* łączenie informacji,
* przypominanie wiedzy,
* wspieranie podejmowania decyzji.

Obsidian został zaprojektowany właśnie jako lokalna baza wiedzy oparta o pliki Markdown i sieć powiązań między notatkami, a nie wyłącznie jako edytor tekstu. ([Obsidian][1])

---

# 5.2 Nasza filozofia

Nie kopiujemy popularnych systemów typu PARA czy Zettelkasten w całości.

Zamiast tego stworzymy system dopasowany do pracy inżyniera.

Nazwijmy go:

```text
Engineering Knowledge System (EKS)
```

Będzie on łączył:

* dokumentację projektową,
* wiedzę techniczną,
* notatki ze studiów,
* dokumentację sprzętu,
* decyzje projektowe,
* pomysły,
* eksperymenty.

---

# 5.3 Główna zasada

Jedna notatka = jedno zagadnienie.

Nigdy:

```text
Python.md
```

zawierający 5000 linii.

Zawsze:

```text
Python Decorators.md

Python Generators.md

Python Asyncio.md

Python Dataclasses.md
```

Takie podejście (tzw. atomic notes) jest jedną z podstaw skutecznych systemów wiedzy opartych na Zettelkasten. ([Obsidian Forum][2])

---

# 5.4 Struktura Vaulta

Proponuję następujący układ.

```text
Vault/

├── 00 Inbox/

├── 01 Projects/

├── 02 Knowledge/

├── 03 University/

├── 04 Research/

├── 05 Hardware/

├── 06 Books/

├── 07 Decisions/

├── 08 Templates/

├── 09 Archive/

└── Attachments/
```

---

# 5.5 Dlaczego numerowane katalogi?

Nie chodzi o estetykę.

Chodzi o przewidywalność.

Po roku zawsze wiesz:

```text
02 Knowledge
```

to wiedza.

Nigdy projekty.

Nigdy PDF.

---

# 5.6 Inbox

Najbardziej niedoceniany folder.

Tutaj trafia wszystko.

Przykład.

Podczas jazdy wpadłeś na pomysł.

Nie zastanawiasz się:

> "gdzie to zapisać?"

Po prostu tworzysz notatkę.

```text
00 Inbox/

Pomysł na sterownik BLDC.md
```

Wieczorem zostanie przeniesiona.

---

# 5.7 Projects

Tutaj nie przechowujemy kodu.

Przechowujemy wiedzę o projekcie.

Przykład.

```text
Projects/

STM32 Robot/

Python Trading/

Portfolio/
```

Każdy projekt posiada własny folder.

---

# 5.8 Knowledge

To największa część systemu.

```text
Knowledge/

Programming/

AI/

Linux/

Docker/

STM32/

Embedded/

Electronics/

Networking/

Mathematics/
```

Każda notatka opisuje jedno pojęcie.

---

# 5.9 University

Nie mieszamy studiów z projektami.

```text
University/

Semestr 5/

Automatyka/

Robotyka/

Sterowanie/

Elektronika/
```

Po ukończeniu studiów całość nadal będzie uporządkowana.

---

# 5.10 Research

Tutaj trafiają:

* artykuły,
* eksperymenty,
* benchmarki,
* testy modeli,
* własne obserwacje.

Przykład.

```text
Research/

Gemma vs Qwen.md

Embedding Models.md

RAG Benchmarks.md
```

---

# 5.11 Hardware

Osobny dział.

```text
Hardware/

RTX4060.md

STM32F407.md

ESP32.md

Raspberry Pi.md

Skoda Octavia II.md
```

Tak.

Samochód również może mieć własną dokumentację.

---

# 5.12 Books

Nie robimy notatki:

```text
Clean Architecture.md
```

Tworzymy:

```text
Books/

Clean Architecture/

Chapter 1/

Chapter 2/

Najważniejsze idee/

Cytaty/

Moje wnioski/
```

---

# 5.13 Decisions

Jedno z najlepszych miejsc.

Tutaj zapisujemy:

> dlaczego zmieniliśmy zdanie.

Przykład.

```text
2026-08-05

Przechodzimy z Gemmy na Qwen.

Powód:

lepsze Tool Calling.

Konsekwencje:

większe wymagania VRAM.
```

Za pół roku AI nie będzie zgadywać.

---

# 5.14 Templates

Każda notatka powinna powstawać z szablonu.

Na przykład.

Nowa technologia.

```text
Opis

Do czego służy

Zalety

Wady

Alternatywy

Powiązane notatki

Przykłady

Źródła
```

Szablony oraz spójny format notatek znacząco ułatwiają późniejsze wyszukiwanie i rozwijanie bazy wiedzy. ([Obsidian Forum][2])

---

# 5.15 Łączenie notatek

To najważniejszy element Obsidiana.

Nie używamy tylko folderów.

Używamy linków.

Przykład.

```text
STM32 DMA

↓

[[UART]]

↓

[[FreeRTOS]]

↓

[[Interrupt]]

↓

[[Circular Buffer]]
```

Powstaje graf wiedzy.

Nie lista plików.

Obsidian traktuje wewnętrzne linki jako podstawowy mechanizm budowania sieci wiedzy i automatycznie aktualizuje je przy zmianie nazw plików. ([Obsidian][3])

---

# 5.16 Jak AI powinno korzystać z Obsidiana?

To bardzo ważne.

AI nie powinno:

* przepisywać notatek,
* zmieniać ich bez pytania,
* tworzyć setek nowych plików.

Powinno:

✅ proponować nowe linki,

✅ sugerować brakujące informacje,

✅ wskazywać duplikaty,

✅ proponować podsumowania,

✅ wykrywać sprzeczności.

---

# 5.17 Cykl życia wiedzy

Każda informacja przechodzi przez pięć etapów.

```text
Pomysł

↓

Inbox

↓

Knowledge

↓

Projekt

↓

Archive
```

Nie ma chaosu.

---

# 5.18 Jak AI może automatyzować Second Brain?

Docelowo chcemy, aby po zakończeniu sesji pracy AI potrafiło zaproponować:

```text
Dzisiaj:

• dodano UART DMA

• rozwiązano problem z watchdogiem

• powstały 2 nowe decyzje projektowe

• warto utworzyć notatkę:
"Circular DMA Buffer"

• warto połączyć ją z:
[[UART]]
[[DMA]]
[[Interrupt]]
```

To jest ogromna oszczędność czasu.

---

# 5.19 Czego NIE robić?

Nie twórz notatek typu:

```text
Notatki.md

Python2.md

Nowe.md

Różne.md
```

Nie twórz folderu:

```text
Inne/
```

Nie kopiuj tej samej informacji do pięciu miejsc.

Nie organizuj wszystkiego wyłącznie tagami.

---

# 5.20 Architektura wiedzy

Docelowy przepływ wygląda następująco.

```text
                 Ty

                  │

                  ▼

             00 Inbox

                  │

                  ▼

          Klasyfikacja wiedzy

                  │

      ┌───────────┼────────────┐

      ▼           ▼            ▼

 Projects    Knowledge    University

      │           │            │

      └───────────┼────────────┘

                  ▼

            Obsidian Vault

                  ▼

           Linki + Metadata

                  ▼

              ChromaDB

                  ▼

               Odysseus

                  ▼

                  LLM
```

---

# ADR

### ADR-012

Każda notatka opisuje jedno zagadnienie.

---

### ADR-013

Folder `Inbox` jest obowiązkowy.

---

### ADR-014

Obsidian przechowuje wiedzę, a nie kod źródłowy.

---

### ADR-015

Każda ważniejsza notatka powinna zawierać sekcję:

```text
Powiązane notatki
```

---

# Podsumowanie rozdziału

Po tym rozdziale mamy zaprojektowany **Second Brain**, który będzie współpracował z AI zamiast być zwykłym zbiorem notatek.

Najważniejsza zasada brzmi:

> **Notatki nie są celem. Celem jest sieć powiązań między wiedzą.**

To właśnie ta sieć pozwoli AI znajdować kontekst i łączyć informacje z różnych projektów, studiów i dokumentacji.

---

## Zapowiedź Rozdziału 6

To będzie jeden z najbardziej technicznych rozdziałów całego dokumentu.

Przejdziemy do **RAG (Retrieval-Augmented Generation)**. Nie ograniczymy się do teorii — zaprojektujemy kompletny pipeline dla Twojego środowiska: indeksowanie repozytoriów, wybór modeli embeddingów, chunking dla kodu i dokumentacji, strategię aktualizacji indeksów oraz sposób współpracy RAG z pamięcią Odysseusa. Dzięki temu AI będzie wiedziało **co**, **kiedy** i **skąd** pobierać, zamiast polegać wyłącznie na pamięci modelu.

[1]: https://obsidian.md/help/obsidian?utm_source=chatgpt.com "About Obsidian - Obsidian Help"
[2]: https://forum.obsidian.md/t/12-principles-for-using-zettelkasten/51679?utm_source=chatgpt.com "12 Principles for using Zettelkasten - Knowledge management - Obsidian Forum"
[3]: https://obsidian.md/help/links?utm_source=chatgpt.com "Internal links - Obsidian Help"
