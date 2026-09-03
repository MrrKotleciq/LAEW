# Rozdział 8 — Agenci, narzędzia i MCP (Model Context Protocol)

> **Ten rozdział jest momentem, w którym AI przestaje być tylko rozmówcą, a zaczyna działać jako prawdziwy asystent inżynierski.**

Do tej pory zaprojektowaliśmy:

* bazę wiedzy,
* Second Brain,
* RAG,
* warstwę modeli.

Jednak sam model językowy nadal ma ogromne ograniczenie:

> **Model sam z siebie niczego nie widzi i niczego nie wykonuje.**

Nie zna Twojego dysku.

Nie zna Twojego projektu.

Nie może uruchomić testów.

Nie może sprawdzić błędów kompilacji.

Nie może przeczytać aktualnego stanu repozytorium.

Do tego potrzebuje **narzędzi**.

---

# 8.1 Od chatbota do agenta

Klasyczny chatbot wygląda tak:

```text id="4p4o6n"
Użytkownik

↓

LLM

↓

Odpowiedź
```

Model tylko generuje tekst.

---

Agent wygląda inaczej:

```text id="h2r2yq"
Użytkownik

↓

Agent

↓

Planowanie

↓

Wybór narzędzia

↓

Wykonanie działania

↓

Analiza wyniku

↓

Kolejna decyzja

↓

Odpowiedź
```

Agent jest systemem wykonującym zadania, a nie tylko odpowiadającym.

---

# 8.2 Dlaczego agent jest potrzebny w naszym projekcie?

Przykład.

Pytanie:

> "Dlaczego mój projekt STM32 nie kompiluje się po ostatnich zmianach?"

Zwykły LLM odpowie:

> "Sprawdź błędy kompilacji."

Agent zrobi:

```
1. Otwórz repozytorium

2. Sprawdź ostatni commit

3. Uruchom build

4. Przeczytaj błędy

5. Znajdź powiązane pliki

6. Porównaj ze zmianami

7. Zaproponuj rozwiązanie
```

To jest różnica między wiedzą a działaniem.

---

# 8.3 Architektura agenta

W naszym systemie agent znajduje się pomiędzy użytkownikiem a narzędziami.

```text id="cx4a5t"
                 Użytkownik

                     │

                     ▼

               Odysseus Agent

                     │

        ┌────────────┼────────────┐

        ▼            ▼            ▼

      Files        Shell        Memory

        │            │            │

        ▼            ▼            ▼

    Projekty      Terminal    ChromaDB

                     │

                     ▼

                   LLM
```

Odysseus jest projektowany właśnie jako środowisko z agentami, narzędziami, MCP, pamięcią i pracą z lokalnymi modelami. ([GitHub][1])

---

# 8.4 Czym jest MCP?

MCP (Model Context Protocol) to standard komunikacji pomiędzy modelem AI a narzędziami.

Można go porównać do:

> USB dla AI.

Tak jak USB pozwala podłączyć:

* klawiaturę,
* mysz,
* dysk,

tak MCP pozwala AI podłączyć:

* system plików,
* Git,
* bazę danych,
* przeglądarkę,
* API.

---

# 8.5 Dlaczego MCP jest ważny?

Bez MCP każdy program robi własne integracje.

Przykład:

```
Chatbot A → własny system narzędzi

Chatbot B → inny system

Chatbot C → jeszcze inny
```

MCP tworzy wspólny standard.

---

# 8.6 Narzędzia naszego agenta

Nie dajemy AI wszystkiego.

To bardzo ważne.

Agent powinien mieć tylko potrzebne uprawnienia.

---

# Tool 1 — Filesystem

Cel:

Czytanie i analiza projektu.

Możliwości:

✅ odczyt plików

✅ wyszukiwanie

✅ analiza struktury

✅ porównywanie zmian

---

Przykład:

```
Pokaż wszystkie pliki odpowiedzialne za komunikację UART.
```

Agent:

```
src/

├── uart.c

├── uart.h

├── dma_uart.c
```

---

# Tool 2 — Git

Najważniejsze narzędzie programistyczne.

Agent powinien znać:

* historię zmian,
* branche,
* commity,
* różnice.

---

Przykład:

```
Co zmieniło się od ostatniego działającego buildu?
```

Agent:

```
Commit:
8a52f1

Zmodyfikowano:

uart.c

scheduler.c

config.h
```

---

# Tool 3 — Shell

Najbardziej potężne.

I najbardziej niebezpieczne.

Może:

* uruchomić kompilację,
* wykonać testy,
* sprawdzić środowisko.

---

Ale:

Nie powinien mieć pełnej kontroli.

---

Źle:

```
sudo rm -rf /
```

---

Dobrze:

```
make test

pytest

git status

cmake --build
```

---

# Tool 4 — Browser

Przydatny do:

* dokumentacji,
* datasheetów,
* API,
* researchu.

Odysseus posiada opcjonalne wsparcie MCP dla narzędzi przeglądarkowych, np. Playwright MCP. ([GitHub][2])

---

# Tool 5 — Memory

Agent musi pamiętać.

Nie wszystko.

Tylko ważne rzeczy.

Przykład:

Dobra pamięć:

```
Projekt używa STM32 HAL.

UART działa przez DMA.

Preferowany styl kodu:
modularny.
```

Zła pamięć:

```
Użytkownik zapytał dziś o LED.
```

---

# 8.7 System uprawnień

Najważniejsza zasada:

> Agent może wykonywać działania tylko w zakresie, który mu nadaliśmy.

---

Tworzymy poziomy.

---

## Level 0

Tylko rozmowa.

```
Chat
```

---

## Level 1

Czytanie.

```
Files
Memory
Git read
```

---

## Level 2

Analiza.

```
Search

Logs

Build output
```

---

## Level 3

Wykonywanie.

```
Run tests

Compile

Scripts
```

---

## Level 4

Zmiany.

```
Modify files

Create commits
```

---

Domyślnie zaczynamy od Level 1.

---

# 8.8 Agent nie powinien pisać kodu za Ciebie

To ważne w kontekście Twojego celu.

Nie budujemy:

> "AI programista."

Budujemy:

> "AI inżynier pomagający podejmować decyzje."

Agent powinien:

* znaleźć problem,
* wyjaśnić problem,
* wskazać rozwiązania,
* przygotować plan.

Ty decydujesz.

---

# 8.9 Role agentów

Docelowo nie jeden agent.

Kilka specjalistycznych.

---

## Main Engineer Agent

Najważniejszy.

Zna:

* projekty,
* historię,
* architekturę.

---

## Code Review Agent

Zadania:

* analiza jakości,
* wykrywanie błędów,
* bezpieczeństwo.

---

## Research Agent

Zadania:

* dokumentacja,
* artykuły,
* porównania.

---

## Documentation Agent

Zadania:

* aktualizacja README,
* ADR,
* changelog.

---

# 8.10 Przykładowy workflow

Nowy problem:

```
UART przestał działać.
```

Agent:

---

## Etap 1

Sprawdza pamięć:

```
Projekt używa DMA.
```

---

## Etap 2

Przeszukuje projekt:

```
uart.c
dma.c
interrupt.c
```

---

## Etap 3

Sprawdza Git:

```
Problem pojawił się po commit 34af.
```

---

## Etap 4

Uruchamia test.

---

## Etap 5

Tworzy raport:

```
Przyczyna:

DMA nie jest resetowane po błędzie.

Propozycja:

dodać restart kanału DMA.
```

---

# 8.11 Integracja z Odysseusem

Nasza konfiguracja:

```
Odysseus

+

Ollama

+

MCP Tools

+

RAG

+

Second Brain
```

Tworzy pełne środowisko.

Nie mamy:

```
AI → tekst
```

Mamy:

```
AI

↓

Wiedza

↓

Narzędzia

↓

Działanie

↓

Wynik
```

---

# 8.12 Bezpieczeństwo

Nigdy nie dajemy agentowi:

* całego dysku,
* haseł,
* dostępu administratora,
* prywatnych folderów.

---

Struktura:

```
AI_Workspace/

├── allowed_projects/

├── sandbox/

└── temp/
```

Agent pracuje tylko tutaj.

---

# ADR

### ADR-025

Agent jest warstwą wykonawczą, nie modelem.

---

### ADR-026

Narzędzia są przydzielane według potrzeb.

---

### ADR-027

Domyślnie agent ma dostęp tylko do odczytu.

---

### ADR-028

Zmiany w kodzie wymagają akceptacji użytkownika.

---

### ADR-029

MCP jest podstawowym sposobem rozszerzania możliwości agenta.

---

# Podsumowanie rozdziału

Po tym rozdziale system posiada już wszystkie główne elementy:

```
                 AI Workspace

                      │

        ┌─────────────┼─────────────┐

        ▼             ▼             ▼

    Knowledge       RAG          Agents

        │             │             │

        └─────────────┼─────────────┘

                      ▼

                   Odysseus

                      ▼

                    LLM
```

Najważniejszy wniosek:

> **Sam model AI nie jest najważniejszym elementem systemu. Największą wartość daje połączenie modelu, wiedzy i narzędzi.**

---

# Zapowiedź Rozdziału 9

W kolejnym rozdziale zaprojektujemy **Prompt Engineering dla całego systemu**.

Nie będzie to lista "100 najlepszych promptów".

Stworzymy profesjonalną warstwę instrukcji:

* główny System Prompt,
* zasady zachowania agenta,
* prompt architekta,
* prompt code review,
* prompt debugowania,
* prompt dokumentacji,
* prompt pracy z RAG.

Czyli dokładnie to, co sprawi, że Odysseus będzie działał jak Twój własny inżynier, a nie zwykły chatbot.

[1]: https://github.com/pewdiepie-archdaemon/odysseus/blob/main/README.md?utm_source=chatgpt.com "odysseus/README.md at main · pewdiepie-archdaemon/odysseus · GitHub"
[2]: https://github.com/odysseus-dev/odysseus/blob/dev/docs/setup.md?utm_source=chatgpt.com "odysseus/docs/setup.md at dev · odysseus-dev/odysseus · GitHub"