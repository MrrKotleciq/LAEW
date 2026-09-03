# Rozdział 1

# Wprowadzenie i analiza wymagań

---

# 1.1 Cel projektu

Celem projektu jest zaprojektowanie **lokalnego środowiska AI**, które stanie się długoterminowym partnerem podczas pracy nad projektami programistycznymi, elektronicznymi oraz inżynierskimi.

Projekt nie ma na celu zastąpienia programisty.

System ma pełnić rolę:

* starszego inżyniera,
* konsultanta technicznego,
* analityka projektu,
* lokalnej bazy wiedzy,
* pamięci długoterminowej.

AI powinno pomagać użytkownikowi podejmować decyzje, analizować istniejący kod oraz dokumentację i przypominać wcześniejsze ustalenia.

---

# 1.2 Wizja systemu

System powinien zachowywać się podobnie do doświadczonego współpracownika.

Przykład:

Zamiast odpowiedzi:

> "Nie wiem, pokaż kod."

powinien odpowiedzieć:

> "Przeszukałem projekt. Funkcja odpowiedzialna za UART znajduje się w `communication/uart.c`. Z dokumentacji wynika, że zdecydowaliśmy się na UART zamiast SPI ze względu na prostszą diagnostykę. Widzę również, że sterownik DMA został dodany tydzień później."

Oznacza to, że AI:

* zna projekt,
* zna historię decyzji,
* zna dokumentację,
* zna strukturę katalogów,
* rozumie zależności między modułami.

---

# 1.3 Założenia

Projekt opiera się na następujących założeniach.

## Lokalność

Całość powinna działać lokalnie.

Kod projektu nie powinien opuszczać komputera użytkownika, chyba że użytkownik świadomie skonfiguruje zewnętrzne API.

---

## Modułowość

Każdy element systemu powinien być wymienialny.

Przykład:

```text
Odysseus
      │
      ▼
 Ollama
      │
      ├── Qwen
      ├── Gemma
      ├── DeepSeek
      └── przyszłe modele
```

Zmiana modelu AI nie może wymagać przebudowy całego środowiska.

To ważna zasada projektowa.

---

## Długowieczność

Projekt powinien być użyteczny przez minimum kilka lat.

Oznacza to:

* brak uzależnienia od jednego modelu,
* brak uzależnienia od jednej firmy,
* brak zależności od jednego API.

---

## Skalowalność

System powinien dobrze działać zarówno dla:

* jednego projektu STM32,

jak i:

* kilkunastu repozytoriów Git,
* kilku tysięcy notatek,
* wielu języków programowania.

---

# 1.4 Problemy, które system ma rozwiązać

Dzisiejsze chatboty mają kilka ograniczeń.

## Problem 1

AI nie zna projektu.

Przykład.

Ty pytasz:

> "Dlaczego ten sterownik działa wolno?"

Model odpowiada:

> "Pokaż kod."

Ponieważ nie ma dostępu do repozytorium.

---

## Problem 2

AI zapomina.

Po kilku godzinach pracy:

* gubi wcześniejsze ustalenia,
* zapomina strukturę projektu,
* ponownie zadaje te same pytania.

---

## Problem 3

Brak pamięci długoterminowej.

Przykład.

Dzisiaj zapisujesz:

> UART został wybrany zamiast SPI.

Za miesiąc AI już tego nie pamięta.

---

## Problem 4

Brak dokumentacji decyzji.

Większość projektów posiada:

```text
README.md
```

i tyle.

Po kilku miesiącach nikt nie pamięta:

* dlaczego zastosowano dane rozwiązanie,
* dlaczego odrzucono alternatywę,
* jakie były kompromisy.

---

## Problem 5

Brak wspólnej wiedzy.

Kod znajduje się w Git.

Notatki znajdują się gdzie indziej.

PDF-y są w Downloads.

Dokumentacja jest na OneDrive.

AI nie ma jednego miejsca, z którego może korzystać.

---

# 1.5 Cele funkcjonalne

System powinien umożliwiać:

### Analizę projektu

AI powinno rozumieć:

* strukturę katalogów,
* zależności,
* moduły.

---

### Analizę kodu

AI powinno potrafić:

* wyjaśniać kod,
* znajdować błędy,
* proponować usprawnienia,
* odpowiadać na pytania dotyczące architektury.

---

### Analizę dokumentacji

AI powinno korzystać z:

* Markdown,
* PDF,
* README,
* dokumentacji technicznej.

---

### Analizę historii projektu

System powinien rozumieć:

* decyzje projektowe,
* historię zmian,
* roadmapę.

---

### Pamięć

AI powinno pamiętać:

* decyzje,
* ustalenia,
* architekturę.

Nie tylko podczas jednej rozmowy.

---

# 1.6 Cele niefunkcjonalne

System powinien być:

### szybki

Odpowiedź poniżej kilku sekund dla większości zapytań.

---

### stabilny

Zmiana modelu nie może powodować przebudowy systemu.

---

### bezpieczny

Domyślnie:

* brak wysyłania kodu do Internetu,
* wszystkie dane lokalnie.

---

### rozszerzalny

Powinno być możliwe dodanie:

* nowych modeli,
* nowych agentów,
* nowych baz wiedzy,
* nowych narzędzi.

---

# 1.7 Architektura logiczna

Na najwyższym poziomie system będzie wyglądał następująco:

```text
                 Użytkownik
                      │
                      ▼
              Odysseus AI
                      │
          ┌───────────┼───────────┐
          │           │           │
          ▼           ▼           ▼
       Agent      Memory       Tools
          │           │           │
          └───────────┼───────────┘
                      │
                      ▼
                  Ollama
                      │
                Lokalny model
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
      Projekty    Dokumentacja   Notatki
```

To jest architektura **logiczna**.

Architekturę fizyczną (procesy, Docker, katalogi, ChromaDB, Ollama, GPU) zaprojektujemy w kolejnych rozdziałach.

---

# 1.8 Dlaczego wybraliśmy Odysseusa?

Na etapie analizy rozważane były m.in.:

* Odysseus AI
* Open WebUI
* Claude Code
* Continue

Wybraliśmy **Odysseus AI**, ponieważ najlepiej odpowiada założeniom projektu:

* jest self-hosted,
* obsługuje lokalne modele,
* ma agentów,
* posiada pamięć opartą o ChromaDB,
* integruje narzędzia (MCP, shell, pliki),
* umożliwia późniejszą rozbudowę o kolejne komponenty. Oficjalna dokumentacja opisuje właśnie taki model działania: Odysseus jako centralny workspace współpracujący z Ollamą, ChromaDB, narzędziami i lokalnymi lub zdalnymi modelami. ([GitHub][1])

---

# Podsumowanie rozdziału

Po pierwszym rozdziale wiemy już **co** budujemy i **dlaczego**.

Najważniejszy wniosek:

> **Nie budujemy chatbota. Budujemy lokalne środowisko wiedzy wspierane przez AI.**

---

## Co będzie w Rozdziale 2?

Przejdziemy do **architektury systemu**. Zaprojektujemy wszystkie komponenty (Odysseus, Ollama, modele, pamięć, RAG, Obsidian, Git, repozytoria, MCP), ich zależności i przepływ danych. Powstanie pierwszy kompletny diagram architektury, który będzie fundamentem całego projektu.

[1]: https://github.com/odysseus-dev/odysseus?utm_source=chatgpt.com "GitHub - odysseus-dev/odysseus: Self-hosted AI workspace. · GitHub"