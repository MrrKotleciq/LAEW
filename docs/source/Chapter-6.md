# Rozdział 6 — RAG (Retrieval-Augmented Generation)

> **To jest rozdział, który sprawia, że AI przestaje zgadywać i zaczyna odpowiadać na podstawie faktów.**

---

# 6.1 Czym naprawdę jest RAG?

Najczęściej spotykana definicja brzmi:

> "RAG pozwala modelowi korzystać z dokumentów."

To prawda, ale jest zbyt uproszczona.

W naszym projekcie RAG będzie pełnił rolę **inteligentnej biblioteki**.

Wyobraź sobie bibliotekę zawierającą:

* cały Twój kod,
* dokumentację,
* datasheety,
* notatki,
* decyzje projektowe,
* historię projektu.

AI **nie czyta wszystkiego**.

Najpierw bibliotekarz wyszukuje odpowiednie strony.

Dopiero potem model otrzymuje ich treść.

Tak właśnie działa Retrieval-Augmented Generation – najpierw etap wyszukiwania (retrieval), a dopiero później generowanie odpowiedzi (generation). ([arXiv][1])

---

# 6.2 Dlaczego RAG jest potrzebny?

Model 14B ma ograniczoną pamięć kontekstową.

Repozytorium może zawierać:

```text
12 000 plików

250 000 linii kodu

400 PDF

1500 notatek
```

Nie da się wysłać wszystkiego do modelu.

Potrzebny jest filtr.

RAG jest właśnie takim filtrem.

---

# 6.3 Nasza filozofia RAG

Nie budujemy "chatbota z bazą wektorową".

Budujemy:

```text
Knowledge

↓

Retriever

↓

Ranking

↓

LLM
```

Model nie ma wyszukiwać.

Model ma analizować.

---

# 6.4 Warstwy RAG

Projekt będzie posiadał cztery warstwy.

```text
Documents

↓

Chunking

↓

Embeddings

↓

Vector Search

↓

Ranking

↓

LLM
```

Każda z nich ma osobne zadanie.

---

# 6.5 Dokumenty

Źródłami wiedzy będą:

```text
README

ADR

Markdown

Kod

PDF

Datasheet

Obsidian

Komentarze

API Documentation
```

Nie wszystkie dokumenty mają jednakowy priorytet.

---

# 6.6 Priorytety

Nasz system będzie oceniał dokumenty.

★★★★★

```text
ADR

Architecture.md

README
```

★★★★☆

```text
docs/

API.md

Hardware.md
```

★★★☆☆

```text
Kod źródłowy
```

★★☆☆☆

```text
Komentarze
```

★☆☆☆☆

```text
Logi
```

Dzięki temu AI najpierw zrozumie **intencję projektu**, a dopiero potem implementację.

---

# 6.7 Chunking

To jedna z najważniejszych decyzji.

Większość poradników pokazuje:

```text
1000 znaków

overlap 200
```

To zły pomysł.

Kod nie jest książką.

---

## Kod

Nie dzielimy kodu:

```c
void UART_Init(){

...
```

w połowie funkcji.

Chunk powinien kończyć się naturalnie.

Na przykład:

* funkcja,
* klasa,
* namespace,
* moduł.

---

## Dokumentacja

Markdown można dzielić według nagłówków.

```markdown
# UART

##

###
```

Nie po liczbie znaków.

---

## PDF

Rozdziały.

Nie strony.

---

# 6.8 Embeddings

Embedding to liczbowy opis znaczenia tekstu.

Przykład.

Zdania:

```text
UART transmit

UART send
```

będą blisko siebie.

Natomiast:

```text
Pizza

STM32
```

bardzo daleko.

Odysseus może korzystać z lokalnych embeddingów przez Ollamę (`/v1/embeddings`) lub z wbudowanego modelu FastEmbed jako rozwiązania awaryjnego. ([GitHub][2])

---

# 6.9 Jakie embeddingi?

Dla naszego projektu obowiązuje zasada:

Model odpowiedzi ≠ model embeddingów.

Przykład.

```text
Qwen

↓

odpowiedzi
```

```text
all-minilm

↓

embeddingi
```

Nie mieszamy tych ról.

---

# 6.10 ChromaDB

ChromaDB będzie pełnić rolę indeksu.

Nie przechowuje dokumentów.

Przechowuje ich reprezentacje wektorowe.

```text
README.md

↓

Embedding

↓

Vector

↓

ChromaDB
```

Odysseus wykorzystuje właśnie ChromaDB jako lokalny magazyn pamięci semantycznej i indeksów RAG. ([GitHub][3])

---

# 6.11 Aktualizacja indeksów

Nie chcemy przebudowywać całej bazy.

Workflow:

```text
Git Commit

↓

Sprawdź zmienione pliki

↓

Usuń stare embeddingi

↓

Dodaj nowe

↓

Koniec
```

To skraca czas aktualizacji z minut do sekund.

---

# 6.12 Co indeksujemy?

Tak.

```text
README

ADR

Markdown

Kod

PDF

Datasheet

Notatki
```

Nie.

```text
node_modules

build

dist

obj

Debug

Release

.git

cache
```

---

# 6.13 Metadane

Każdy fragment otrzymuje metadane.

Przykład.

```yaml
Project:
STM32 Robot

Language:
C

Module:
UART

Author:
Kornel

Type:
Documentation

Created:
2026-08-05
```

To umożliwia filtrowanie wyników.

---

# 6.14 Retrieval

Pytanie:

> "Dlaczego watchdog resetuje MCU?"

Retriever znajduje:

```text
README

ADR-004

watchdog.c

Hardware.md

Bug #12
```

Model otrzymuje wyłącznie te informacje.

---

# 6.15 Ranking

Nie każdy wynik jest dobry.

System powinien ocenić:

* trafność,
* świeżość,
* typ dokumentu.

Przykład.

```text
README

95%

watchdog.c

91%

bug.md

87%

old_notes.md

42%
```

Najpierw trafiają najlepsze wyniki.

W nowoczesnych systemach RAG często stosuje się dodatkowy etap rerankingu, który poprawia jakość końcowych odpowiedzi bez konieczności zwiększania rozmiaru modelu. ([Reddit][4])

---

# 6.16 Jak AI powinno odpowiadać?

Źle.

> "Myślę że..."

Dobrze.

> "Na podstawie README oraz ADR-005 wynika, że..."

Każda odpowiedź powinna być możliwa do zweryfikowania.

---

# 6.17 Integracja z Odysseusem

Tutaj warto wykorzystać to, co już oferuje Odysseus.

Odysseus posiada:

* ChromaDB,
* pamięć,
* embeddingi,
* mechanizmy RAG,
* wyszukiwanie narzędzi.

Nie będziemy ich zastępiać.

Najpierw wykorzystamy możliwości platformy.

Dopiero gdy okażą się niewystarczające, rozważymy własne rozszerzenia. Dokumentacja pokazuje, że Odysseus udostępnia konfigurowalne endpointy embeddingów oraz własną integrację z ChromaDB jako podstawę pamięci semantycznej. ([GitHub][5])

---

# 6.18 Kiedy NIE używać RAG?

Nie każde pytanie wymaga wyszukiwania.

Przykład.

> "Napisz pętlę for w Pythonie."

Nie ma sensu przeszukiwać dokumentacji.

Natomiast pytanie:

> "Dlaczego w projekcie wybraliśmy FreeRTOS?"

Powinno uruchomić pełny proces RAG.

---

# 6.19 Docelowy pipeline

```text
Użytkownik

↓

Odysseus

↓

Czy potrzebna wiedza?

↓

Nie

↓

LLM

↓

Odpowiedź


Tak

↓

Retriever

↓

ChromaDB

↓

Ranking

↓

Kontekst

↓

LLM

↓

Odpowiedź
```

---

# ADR

### ADR-016

RAG wyszukuje informacje.

LLM je analizuje.

---

### ADR-017

Kod jest dzielony logicznie, nie według liczby znaków.

---

### ADR-018

Dokumentacja ma wyższy priorytet niż kod.

---

### ADR-019

Embeddingi są oddzielone od modelu odpowiedzi.

---

### ADR-020

Najpierw wykorzystujemy wbudowany system RAG Odysseusa.

Dodatkowe komponenty wdrażamy tylko wtedy, gdy pojawi się rzeczywista potrzeba.

---

# Podsumowanie rozdziału

Po tym rozdziale mamy kompletny projekt warstwy RAG.

Najważniejszy wniosek jest prosty:

> **RAG nie jest bazą danych. Jest inteligentnym mechanizmem dostarczania modelowi właściwego kontekstu we właściwym momencie.**

To właśnie dzięki temu lokalny model 14B może odpowiadać trafniej niż znacznie większy model, który nie ma dostępu do wiedzy o Twoim projekcie.

## Zapowiedź Rozdziału 7

W następnym rozdziale zajmiemy się **modelami AI i ich rolami**. Nie będziemy wybierać "jednego najlepszego modelu". Zaprojektujemy architekturę, w której różne modele (Qwen, Gemma, DeepSeek i przyszłe modele) będą mogły pełnić różne funkcje: analizę kodu, planowanie, streszczanie czy embeddingi, pozostając całkowicie wymiennymi komponentami systemu.

[1]: https://arxiv.org/abs/2005.11401?utm_source=chatgpt.com "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
[2]: https://github.com/pewdiepie-archdaemon/odysseus/blob/main/.env.example?utm_source=chatgpt.com "odysseus/.env.example at main · pewdiepie-archdaemon/odysseus · GitHub"
[3]: https://github.com/pewdiepie-archdaemon/odysseus?utm_source=chatgpt.com "GitHub - pewdiepie-archdaemon/odysseus: Self-hosted AI workspace. · GitHub"
[4]: https://www.reddit.com/r/Rag/comments/1valvk6/15_months_building_a_rag_system_in_retirement/?utm_source=chatgpt.com "15 Months Building a RAG System in Retirement: Lessons Learned and What Actually Worked"
[5]: https://github.com/odysseus-dev/odysseus/blob/dev/docs/setup.md?utm_source=chatgpt.com "odysseus/docs/setup.md at dev · odysseus-dev/odysseus · GitHub"
