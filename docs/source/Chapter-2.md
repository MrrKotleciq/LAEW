**Rozdział 2 — Architektura systemu**

---

> **Cel rozdziału**
>
> W pierwszym rozdziale określiliśmy **co** budujemy.
>
> W tym rozdziale odpowiemy na pytanie:
>
> **Jak zbudować system, aby był łatwy do rozwijania przez kolejne lata?**

---

# 2.1 Dlaczego architektura jest ważniejsza od modelu?

To prawdopodobnie najważniejszy rozdział całego dokumentu.

Większość osób budujących lokalne AI zaczyna od pytania:

> "Jaki model pobrać?"

Jest to błędne podejście.

Model AI jest **jedynie jednym z komponentów** systemu.

W praktyce jakość pracy zależy od znacznie większej liczby elementów:

```text
                 100%

        10%  Model

        20%  RAG

        15%  Organizacja wiedzy

        20%  Narzędzia

        20%  Prompt Engineering

        15%  Workflow
```

Model można wymienić w ciągu pięciu minut.

Źle zaprojektowanego systemu nie.

---

# 2.2 Główne założenia architektoniczne

Projekt będzie oparty o pięć zasad.

---

## Zasada 1

### AI nie przechowuje wiedzy

Model ma odpowiadać.

Nie ma być bazą wiedzy.

Wiedza znajduje się w:

* repozytoriach Git,
* dokumentacji,
* Obsidianie,
* bazie RAG,
* pamięci Odysseusa.

---

## Zasada 2

### AI nie jest właścicielem projektu

Projekt należy do użytkownika.

AI jedynie go analizuje.

Nigdy odwrotnie.

---

## Zasada 3

### Wszystkie dane mają jedno źródło prawdy

Przykład.

Nie robimy:

```text
README

README_v2

README_new

README_final
```

Tylko:

```text
README.md
```

AI zawsze korzysta z tego samego dokumentu.

---

## Zasada 4

### Każdy komponent odpowiada za jedną rzecz

Nie chcemy programu, który robi wszystko.

Chcemy wiele małych komponentów.

---

## Zasada 5

### Wymienialność

Za dwa lata może pojawić się lepszy model.

Powinniśmy móc zrobić:

```text
Gemma

↓

Qwen

↓

DeepSeek

↓

kolejny model
```

bez zmiany reszty systemu.

---

# 2.3 Architektura logiczna

Cały system będzie wyglądał następująco.

```text
                           USER
                             │
                             │
                             ▼
                     ┌────────────────┐
                     │   Odysseus AI  │
                     └────────────────┘
                             │
      ┌──────────────────────┼──────────────────────┐
      │                      │                      │
      ▼                      ▼                      ▼
  Conversation          Agent Runtime          Memory
      │                      │                      │
      └──────────────┬───────┴──────────────┬──────┘
                     ▼                      ▼
                MCP Tools              Chroma Memory
                     │
                     ▼
                 Ollama API
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    LLM (Qwen/Gemma)       Embedding Model
         │                       │
         └───────────┬───────────┘
                     ▼
                Knowledge Layer
         ┌───────────┼────────────┐
         ▼           ▼            ▼
      Git Repo    Obsidian      Documents
```

To jest **architektura logiczna**, czyli pokazuje zależności między komponentami, a nie procesy systemowe.

---

# 2.4 Warstwy systemu

System będzie posiadał sześć warstw.

---

## Warstwa 1

### Presentation Layer

Odpowiada za kontakt z użytkownikiem.

Tutaj znajduje się:

* Odysseus AI

To jedyny element, z którym użytkownik pracuje na co dzień.

---

## Warstwa 2

### Agent Layer

Odpowiada za:

* planowanie,
* korzystanie z narzędzi,
* wykonywanie wielu kroków.

Tutaj działa agent Odysseusa wykorzystujący narzędzia, pamięć i MCP. ([GitHub][1])

---

## Warstwa 3

### LLM Layer

Tutaj znajduje się model.

Na przykład:

```text
Qwen

Gemma

DeepSeek

Llama
```

To jedyna warstwa, którą będziemy zmieniać najczęściej.

---

## Warstwa 4

### Knowledge Layer

Najważniejsza warstwa.

Tutaj znajduje się cała wiedza.

Nie model.

Nie agent.

Tylko wiedza.

Składa się z:

* repozytoriów Git,
* dokumentacji,
* notatek,
* pamięci.

---

## Warstwa 5

### Storage Layer

Odpowiada za trwałe dane.

Przykładowo:

```text
SQLite

ChromaDB

Markdown

Git
```

Odysseus domyślnie przechowuje dane użytkownika lokalnie (`data/`), w tym bazę SQLite, pamięć i ChromaDB. ([GitHub][2])

---

## Warstwa 6

### Infrastructure Layer

Najniższa warstwa.

Tutaj znajduje się:

* Docker
* GPU
* Windows
* dyski
* sieć

---

# 2.5 Główne komponenty

System będzie składał się z siedmiu głównych komponentów.

---

## Komponent A

### Odysseus

Odpowiedzialność:

* interfejs użytkownika,
* zarządzanie agentami,
* pamięć,
* sesje,
* narzędzia.

Nie odpowiada za generowanie tekstu.

To robi model.

---

## Komponent B

### Ollama

Odpowiedzialność:

* uruchamianie modeli,
* zarządzanie modelami,
* komunikacja z GPU.

Odysseus komunikuje się z Ollamą przez API. W przypadku Dockera zalecanym adresem jest np. `http://host.docker.internal:11434/v1`. ([GitHub][2])

---

## Komponent C

### LLM

Odpowiada wyłącznie za:

* analizę,
* rozumowanie,
* generowanie odpowiedzi.

Nie przechowuje wiedzy.

---

## Komponent D

### Memory

To nie to samo co RAG.

Memory przechowuje:

* preferencje użytkownika,
* wcześniejsze rozmowy,
* ustalenia.

Odysseus posiada własny system pamięci oparty na ChromaDB z wyszukiwaniem wektorowym i słowami kluczowymi. ([GitHub][3])

---

## Komponent E

### Knowledge Base

Tutaj znajdują się:

* dokumentacja,
* README,
* ADR (Architecture Decision Records),
* instrukcje,
* notatki.

To najcenniejsza część systemu.

---

## Komponent F

### Git

Git jest historią projektu.

AI może analizować:

* commity,
* branch'e,
* historię zmian.

Ale Git nie zastępuje dokumentacji.

---

## Komponent G

### Obsidian

Obsidian nie jest notatnikiem.

W tym projekcie będzie:

> **długoterminową pamięcią inżynierską.**

---

# 2.6 Przepływ informacji

Załóżmy, że użytkownik pyta:

> "Dlaczego sterownik silnika czasami się zawiesza?"

System wykonuje następujące kroki:

```text
1.
User

↓

2.
Odysseus

↓

3.
Agent

↓

4.
Czy potrzebna jest wiedza?

↓

TAK

↓

5.
Przeszukaj Memory

↓

6.
Przeszukaj dokumentację

↓

7.
Przeszukaj repo

↓

8.
Przekaż wyniki do LLM

↓

9.
LLM analizuje

↓

10.
Odpowiedź
```

To bardzo ważne.

Model **nie zgaduje**.

Najpierw szuka.

Potem odpowiada.

---

# 2.7 Dlaczego nie chcemy jednego ogromnego modelu?

Początkujący często zakładają:

> większy model = lepszy system

Nie.

Przykład.

Model 70B bez dostępu do projektu:

> "Pokaż kod."

Model 14B z dobrze skonfigurowanym RAG:

> "Przeszukałem pliki `motor.c`, `driver_pwm.c` i `README.md`. Problem prawdopodobnie wynika z…"

Dlatego **architektura wygrywa z rozmiarem modelu**.

Coraz więcej lokalnych projektów wykorzystuje właśnie taki wzorzec: lokalny model + ChromaDB + indeks kodu + MCP zamiast ciągłego przekazywania całego repozytorium do LLM. ([Reddit][4])

---

# 2.8 Decyzje architektoniczne (ADR)

Od tego rozdziału zaczynamy prowadzić rejestr decyzji.

### ADR-001

**Interfejsem systemu będzie Odysseus AI.**

**Powód**

* lokalny,
* rozwijany,
* posiada agentów,
* posiada pamięć,
* posiada MCP,
* współpracuje z Ollamą. ([GitHub][1])

---

### ADR-002

**Model AI jest komponentem wymiennym.**

Nigdy nie uzależniamy architektury od jednego modelu.

---

### ADR-003

**Wiedza znajduje się poza modelem.**

Model jest procesorem.

Nie magazynem wiedzy.

---

# Podsumowanie rozdziału

Po dwóch pierwszych rozdziałach mamy już zdefiniowany **cel** i **architekturę logiczną** systemu.

Najważniejszy wniosek brzmi:

> **Odysseus nie jest "AI". Jest orkiestratorem całego środowiska. AI jest tylko jednym z jego komponentów.**

## Zapowiedź rozdziału 3

W następnym rozdziale przejdziemy do **projektowania infrastruktury fizycznej**. Rozrysujemy rzeczywisty układ procesów, kontenerów Docker, katalogów na dysku, przepływów między Ollamą, ChromaDB i Odysseusem oraz zaprojektujemy strukturę katalogów tak, aby system był łatwy w utrzymaniu i rozbudowie przez kolejne lata.

[1]: https://github.com/odysseus-dev/odysseus?utm_source=chatgpt.com "GitHub - odysseus-dev/odysseus: Self-hosted AI workspace. · GitHub"
[2]: https://github.com/odysseus-dev/odysseus/blob/dev/docs/setup.md?utm_source=chatgpt.com "odysseus/docs/setup.md at dev · odysseus-dev/odysseus · GitHub"
[3]: https://github.com/pewdiepie-archdaemon/odysseus/blob/main/README.md?utm_source=chatgpt.com "odysseus/README.md at main · pewdiepie-archdaemon/odysseus · GitHub"
[4]: https://www.reddit.com/r/ollama/comments/1ucjl32/built_a_local_codebase_memory_for_agentic_ides/?utm_source=chatgpt.com "Built a local codebase memory for agentic IDEs using Ollama + ChromaDB; zero cloud required"
