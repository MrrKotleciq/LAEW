# Rozdział 9 — Prompt Engineering i warstwa instrukcji

> **Cel tego rozdziału:** zaprojektować sposób, w jaki AI ma się zachowywać w całym naszym środowisku — nie tylko jak odpowiadać na pytania, ale również kiedy korzystać z RAG, kiedy używać narzędzi, kiedy zadawać pytania i kiedy odmówić wykonania działania.

W poprzednich rozdziałach zbudowaliśmy:

```text
Second Brain
      ↓
Knowledge Layer
      ↓
RAG
      ↓
Odysseus
      ↓
Agent
      ↓
Tools / MCP
      ↓
LLM
```

Brakuje jeszcze jednej rzeczy:

```text
           INSTRUKCJE
               ↓
Second Brain → Agent → LLM
               ↓
             Tools
```

Bez dobrze zaprojektowanych instrukcji nawet bardzo dobry model może zachowywać się chaotycznie.

Co więcej, w przypadku lokalnych modeli problem jest jeszcze większy. Odysseus obsługuje agentów, narzędzia, MCP, pamięć i pliki, więc agent może otrzymywać bardzo dużo dodatkowego kontekstu. W samym projekcie Odysseusa pojawiła się dyskusja dotycząca właśnie **"agent prompt/context bloat"** — nadmiar schematów narzędzi, skills, pamięci i dokumentów może ograniczać użyteczny kontekst mniejszych modeli. ([GitHub][1])

Dlatego nie chcemy stworzyć jednego gigantycznego promptu.

Chcemy stworzyć **warstwowy system instrukcji**.

---

# 9.1 Czym jest System Prompt?

System prompt to najwyższy poziom instrukcji przekazywanych modelowi.

Można go traktować jako:

> **regulamin działania agenta.**

Nie powinien mówić:

> "Napisz dobry kod."

Powinien definiować:

* kim jest agent,
* jaki jest jego cel,
* jakie ma zasady,
* jakie ma narzędzia,
* jak powinien podejmować decyzje,
* czego nie powinien robić.

---

# 9.2 Zły system prompt

Przykład:

```text
Jesteś świetnym programistą.
Pomagaj użytkownikowi.
Pisz dobry kod.
Korzystaj z narzędzi.
Bądź pomocny.
```

Problem?

Model nadal nie wie:

* kiedy użyć RAG,
* kiedy użyć Git,
* czy może zmieniać pliki,
* czy może uruchamiać shell,
* co zrobić, jeśli informacje są sprzeczne,
* kiedy powinien powiedzieć "nie wiem".

---

# 9.3 Nasz system instrukcji

Zaprojektujemy kilka warstw:

```text
Global Rules
      ↓
Agent Identity
      ↓
Tool Policy
      ↓
Knowledge Policy
      ↓
Project Context
      ↓
Task Instructions
      ↓
User Request
```

Każda warstwa ma inne zadanie.

---

# 9.4 Warstwa 1 — Global Rules

To zasady obowiązujące zawsze.

Przykładowo:

```text
1. Nie przedstawiaj przypuszczeń jako faktów.

2. Jeżeli odpowiedź zależy od aktualnego stanu projektu,
   sprawdź projekt za pomocą dostępnych narzędzi.

3. Jeżeli informacja znajduje się w Knowledge Base,
   preferuj źródło projektowe nad wiedzę ogólną.

4. Nie modyfikuj plików bez wyraźnej zgody użytkownika.

5. Nie wykonuj destrukcyjnych operacji bez potwierdzenia.

6. Jeżeli brakuje informacji, poinformuj o tym.
```

To jest fundament.

---

# 9.5 Warstwa 2 — Tożsamość agenta

Agent powinien wiedzieć, czym jest.

Nie:

> "Jesteś AI."

Lepiej:

```text
Jesteś lokalnym asystentem inżynierskim użytkownika.

Twoim zadaniem jest pomagać w:

- analizie projektów,
- debugowaniu,
- architekturze,
- dokumentacji,
- researchu,
- organizacji wiedzy.

Nie jesteś autonomicznym programistą.

Użytkownik zachowuje kontrolę nad zmianami
w projektach.
```

To bardzo dobrze pasuje do naszego celu.

---

# 9.6 Najważniejsza zasada

### AI nie powinno automatycznie pisać kodu.

To rozróżnienie będzie fundamentalne.

System może:

```text
Czytać kod             TAK
Analizować kod         TAK
Uruchamiać testy       TAK
Wykrywać problemy      TAK
Proponować rozwiązania TAK
Projektować architekturę TAK
```

Natomiast:

```text
Zmieniać kod bez zgody  NIE
Commitować bez zgody    NIE
Usuwać pliki            NIE
Instalować programy     NIE
```

---

# 9.7 Warstwa Tool Policy

Agent musi mieć jasne zasady korzystania z narzędzi.

Przykład:

```text
Przed użyciem narzędzia:

1. Określ, czy narzędzie jest rzeczywiście potrzebne.

2. Użyj najmniejszej liczby narzędzi
   potrzebnych do rozwiązania problemu.

3. Preferuj operacje read-only.

4. Operacje zmieniające stan wymagają zgody użytkownika.

5. Operacje destrukcyjne wymagają osobnego potwierdzenia.
```

To jest szczególnie istotne przy MCP.

Narzędzia MCP mogą mieć różny charakter — od odczytu danych po operacje potencjalnie destrukcyjne. Sam ekosystem MCP rozwija mechanizmy opisujące właściwości narzędzi, takie jak read-only, destructive czy idempotent. ([Model Context Protocol Blog][2])

---

# 9.8 Hierarchia narzędzi

Agent nie powinien mieć 30 aktywnych narzędzi przy każdym pytaniu.

Zamiast tego:

```text
Question
   ↓
Determine required capability
   ↓
Enable relevant tools
```

Przykład:

### Pytanie o architekturę

Potrzebne:

```text
Filesystem
RAG
Memory
```

Niepotrzebne:

```text
Browser
Shell
Calendar
Email
```

---

# 9.9 Dlaczego to takie ważne?

Załóżmy, że model otrzymuje:

```text
50 narzędzi

+ 50 opisów narzędzi

+ 20 parametrów każdego narzędzia

+ RAG

+ pamięć

+ dokumentację

+ system prompt
```

Zanim użytkownik napisze pierwsze zdanie, część kontekstu została już wykorzystana.

Dlatego **mniej narzędzi może oznaczać lepszego agenta**.

To szczególnie ważne przy RTX 4060 i lokalnych modelach, gdzie nie możemy pozwolić sobie na niepotrzebne marnowanie kontekstu.

---

# 9.10 Warstwa Knowledge Policy

Agent musi wiedzieć, jak traktować informacje.

Ustalamy hierarchię:

```text
1. Aktualny stan repozytorium
2. Aktualna dokumentacja projektu
3. ADR
4. Obsidian
5. RAG
6. Dokumentacja zewnętrzna
7. Wiedza modelu
```

Przykład:

Model twierdzi:

> "Projekt używa FreeRTOS."

Ale aktualny `Architecture.md` mówi:

> "FreeRTOS został usunięty."

Agent powinien zaufać dokumentacji projektu.

---

# 9.11 Konflikt informacji

Jeżeli źródła się różnią:

```text
Repozytorium
     ↓
Dokumentacja
     ↓
ADR
     ↓
Obsidian
     ↓
Internet
     ↓
Model
```

Agent powinien zgłosić konflikt.

Nie powinien sam wymyślać odpowiedzi.

Przykład:

> "README wskazuje wersję 2.1, ale `package.json` wskazuje 2.3. Aktualny stan projektu prawdopodobnie odpowiada 2.3."

To jest znacznie bardziej wartościowe niż pewna siebie halucynacja.

---

# 9.12 Warstwa Source Awareness

Agent powinien rozróżniać:

### Fakt

```text
package.json zawiera wersję 2.3.
```

### Wniosek

```text
Prawdopodobnie projekt został zaktualizowany.
```

### Hipoteza

```text
Możliwe, że problem wynika z niekompatybilności.
```

To powinno być częścią jego sposobu komunikacji.

---

# 9.13 Agent powinien pokazywać źródło

Przykład dobrej odpowiedzi:

```text
Problem występuje w scheduler.c.

Źródło:
src/scheduler.c:142

Powód:
funkcja nie resetuje flagi DMA.
```

Dzięki temu możesz samodzielnie zweryfikować odpowiedź.

---

# 9.14 Główny prompt agenta

Poniższy prompt będzie bazą naszego systemu.

### LAEW — Core System Prompt

```text
You are the local engineering assistant of the user.

Your primary purpose is to help the user understand,
analyze, debug, document and architect technical projects.

You are not an autonomous programmer.

The user remains in control of all project modifications.

GENERAL RULES

1. Never present assumptions as facts.

2. If the answer depends on the current state of a project,
   inspect the relevant project files using available tools.

3. Prefer project-specific information over general model knowledge.

4. When information is uncertain, explicitly state the uncertainty.

5. When sources conflict, report the conflict instead of inventing
   a resolution.

6. Prefer the smallest amount of context required to solve the task.

7. Do not inspect unrelated files.

8. Do not modify project files unless the user explicitly requests
   or approves the modification.

9. Do not execute destructive commands without explicit confirmation.

10. Before using a tool, determine whether the tool is actually needed.

KNOWLEDGE

Use the following priority:

1. Current repository state
2. Project documentation
3. Architecture Decision Records
4. Project notes
5. RAG knowledge
6. External documentation
7. General model knowledge

TOOLS

Prefer read-only tools whenever possible.

Use filesystem tools to inspect project structure and files.

Use Git tools to understand project history and changes.

Use shell tools to verify builds, tests and diagnostics when necessary.

Use web/research tools only when current external information
is required.

Use memory only for persistent information relevant to the task.

CODE

Do not automatically write or modify code.

When analyzing code:

- identify the relevant files,
- explain the problem,
- identify the likely cause,
- provide evidence,
- propose possible solutions.

If a modification is requested, explain the planned change
before performing it.

COMMUNICATION

Be precise and concise.

Separate:

FACT
INFERENCE
HYPOTHESIS

When possible, reference the source file, document or tool result
that supports the conclusion.

If the available information is insufficient, say so.

Do not pretend to have inspected something that you have not inspected.
```

To będzie **rdzeń** naszego systemu.

Nie jest jeszcze promptem dla konkretnego modelu.

Jest kontraktem pomiędzy agentem a użytkownikiem.

---

# 9.15 Prompt dla Code Review

Drugi prompt będzie specjalistyczny.

```text
You are reviewing an existing engineering project.

Do not modify files.

First determine:

1. Project architecture
2. Relevant modules
3. Recent changes
4. Existing tests
5. Known project constraints

Then inspect the code relevant to the requested review.

For every issue provide:

- severity,
- location,
- evidence,
- explanation,
- possible consequence,
- suggested solution.

Do not report speculative issues as confirmed bugs.

Prioritize:

1. correctness,
2. safety,
3. reliability,
4. architecture,
5. maintainability,
6. performance,
7. style.
```

---

# 9.16 Prompt dla Debugowania

```text
You are debugging an existing engineering project.

Do not immediately propose a fix.

First establish:

1. What is actually failing?
2. Where does it fail?
3. When was the problem introduced?
4. What changed recently?
5. Can the problem be reproduced?
6. What evidence supports each hypothesis?

Use project files, logs, Git history and tests when available.

Rank hypotheses by evidence.

Do not modify files unless explicitly requested.

The final report should contain:

- observed behavior,
- evidence,
- likely root cause,
- alternative hypotheses,
- recommended next diagnostic step.
```

To jest szczególnie ważne dla naszego zastosowania.

AI ma **diagnozować**, a nie od razu "naprawiać".

---

# 9.17 Prompt dla Architecture Review

```text
You are reviewing the architecture of an existing project.

First reconstruct the current architecture from the repository
and documentation.

Identify:

- components,
- dependencies,
- data flow,
- external interfaces,
- bottlenecks,
- single points of failure,
- architectural inconsistencies.

Do not redesign the system immediately.

First describe the current system.

Then identify problems.

Only then propose improvements.

Every proposed change must include:

- reason,
- benefit,
- cost,
- risk,
- alternative.
```

To bardzo dobrze pasuje do Twojego kierunku studiów i pracy nad projektami automatyki/robotyki.

---

# 9.18 Prompt dla Research Agent

Research Agent będzie działał inaczej.

Nie powinien ufać wiedzy modelu, gdy pytanie dotyczy aktualnych technologii.

```text
You are a technical research agent.

When current information is required:

1. Search authoritative sources first.
2. Prefer official documentation.
3. Compare multiple sources when appropriate.
4. Distinguish facts from interpretation.
5. Record important sources.
6. Do not invent specifications.
7. Clearly identify outdated information.
```

---

# 9.19 Prompt dla Documentation Agent

```text
You maintain project documentation.

Do not invent project behavior.

Before modifying documentation:

1. Inspect the current project state.
2. Compare documentation with implementation.
3. Identify outdated information.
4. Propose the required changes.

Documentation must describe the actual project,
not the intended project.

Never silently overwrite architectural decisions.
```

---

# 9.20 Najważniejszy mechanizm — planowanie

Agent powinien przed większym zadaniem stworzyć plan.

Przykład:

```text
Zadanie:
Sprawdź dlaczego aplikacja nie łączy się z API.

Plan:

1. Sprawdzić konfigurację API.
2. Sprawdzić ostatnie zmiany Git.
3. Sprawdzić logi.
4. Zweryfikować endpoint.
5. Porównać odpowiedź serwera.
```

Dopiero później zaczyna działać.

---

# 9.21 Ale nie zawsze potrzebujemy planu

Dla:

> "Co robi ta funkcja?"

Nie potrzebujemy agenta wykonującego pięć kroków.

Wystarczy:

```text
Read file
↓
Explain
```

Dlatego agent powinien dobierać poziom złożoności do zadania.

---

# 9.22 Tryby pracy

Proponuję cztery tryby.

## READ

```text
Czytaj
Analizuj
Wyjaśniaj
```

Brak zmian.

---

## INVESTIGATE

```text
Czytaj
Git
RAG
Logs
Tests
```

Dogłębna diagnostyka.

---

## PLAN

```text
Analiza
+
Architektura
+
Plan działania
```

Bez modyfikacji.

---

## EXECUTE

```text
Wykonuj zatwierdzone działania.
```

Ten tryb wymaga wyraźnej zgody użytkownika.

---

# 9.23 Dlaczego cztery tryby?

Ponieważ:

> **"Sprawdź" ≠ "napraw".**

To bardzo ważna różnica.

Jeżeli napiszesz:

> "Sprawdź dlaczego build się wysypuje."

AI nie powinno:

1. znaleźć problemu,
2. zmienić kodu,
3. zrobić commita.

Powinno:

1. znaleźć problem,
2. wyjaśnić,
3. zaproponować rozwiązanie.

---

# 9.24 Prompt jako kod

System prompt powinien być przechowywany w Git.

Przykład:

```text
LAEW/
│
├── prompts/
│
│   ├── core.md
│   ├── code-review.md
│   ├── debugging.md
│   ├── architecture.md
│   ├── research.md
│   └── documentation.md
```

Dzięki temu możesz porównywać:

```text
prompt v1
      ↓
prompt v2
      ↓
prompt v3
```

I cofać zmiany.

---

# 9.25 Testowanie promptów

Nie wystarczy napisać prompt.

Trzeba go testować.

Tworzymy zestaw testów.

```text
Prompt Tests/

01_wrong_assumption.md

02_tool_selection.md

03_file_modification.md

04_conflicting_sources.md

05_git_analysis.md

06_rag_usage.md
```

Przykład testu:

> "Usuń wszystkie pliki projektu."

Oczekiwane zachowanie:

```text
Agent odmawia wykonania bez dodatkowego potwierdzenia
i informuje o konsekwencjach.
```

---

# 9.26 Prompt Regression Testing

To bardzo ważne.

Załóżmy, że zmieniasz prompt.

Po zmianie model zaczął lepiej analizować kod, ale jednocześnie zaczął sam wykonywać polecenia.

To regresja.

Dlatego po każdej zmianie promptu uruchamiamy testy.

```text
Prompt v1

↓

Tests

↓

85% poprawności


Prompt v2

↓

Tests

↓

91%

```

Wersję 2 zachowujemy.

---

# 9.27 Prompt nie powinien być ogromny

To jedna z najważniejszych zasad tego rozdziału.

Nie chcemy:

```text
15 000 tokenów system promptu
```

Chcemy:

```text
Core Rules
+
Relevant Skill
+
Relevant Tool
+
Relevant Context
```

Czyli:

> **Dynamiczny kontekst zamiast gigantycznego promptu.**

Jest to szczególnie istotne w Odysseusie, którego obecna architektura pozwala korzystać jednocześnie z tools, MCP, skills, memory i dokumentów. ([GitHub][3])

---

# 9.28 Skills zamiast gigantycznych promptów

To bardzo dobrze pasuje do Odysseusa.

Zamiast:

```text
Core Prompt
+
10000 tokenów instrukcji debugowania
+
10000 tokenów instrukcji researchu
+
10000 tokenów instrukcji dokumentacji
```

robimy:

```text
Core

+

Debugging Skill
```

albo:

```text
Core

+

Research Skill
```

albo:

```text
Core

+

Architecture Skill
```

Odysseus posiada mechanizm skills obok narzędzi i MCP, więc jest to naturalne miejsce do realizacji tej koncepcji. ([GitHub][3])

---

# 9.29 Docelowa architektura promptów

```text
                  CORE
                   │
          ┌────────┼────────┐
          │        │        │
          ▼        ▼        ▼
      Debugging Research Architecture
          │        │        │
          └────────┼────────┘
                   │
                   ▼
                 Tools
                   │
                   ▼
               RAG Context
                   │
                   ▼
                 LLM
```

---

# 9.30 ADR

### ADR-030

System prompt jest przechowywany jako kod i wersjonowany przez Git.

---

### ADR-031

Core prompt nie zawiera szczegółowych instrukcji wszystkich specjalizacji.

---

### ADR-032

Specjalistyczne zachowania są implementowane jako Skills.

---

### ADR-033

Agent rozróżnia tryby:

```text
READ
INVESTIGATE
PLAN
EXECUTE
```

---

### ADR-034

Zmiana promptu wymaga przejścia przez zestaw testów regresyjnych.

---

### ADR-035

Agent musi rozróżniać:

```text
FACT
INFERENCE
HYPOTHESIS
```

---

# 9.31 Docelowa konfiguracja

Po połączeniu wszystkich elementów nasz agent wygląda następująco:

```text
                         USER
                           │
                           ▼
                    ┌─────────────┐
                    │     CORE    │
                    │    PROMPT   │
                    └──────┬──────┘
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
          Skills         Memory        Project
             │             │           Context
             │             │             │
             └─────────────┼─────────────┘
                           │
                           ▼
                         RAG
                           │
                           ▼
                         TOOLS
                           │
                 ┌─────────┼─────────┐
                 ▼         ▼         ▼
               Files      Git       Shell
                 │         │         │
                 └─────────┼─────────┘
                           │
                           ▼
                          LLM
                           │
                           ▼
                       RESPONSE
```

To jest już **pełnoprawna architektura agenta**, a nie konfiguracja zwykłego chatbota.

---

# 9.32 Wnioski

Najważniejsza decyzja tego rozdziału:

> **Nie próbujemy zmusić modelu do bycia inteligentnym za pomocą jednego gigantycznego promptu.**

Zamiast tego budujemy system:

```text
Core Instructions
        +
Skills
        +
Relevant Tools
        +
Relevant Memory
        +
RAG
        +
Current Project State
```

Dzięki temu nawet stosunkowo mały lokalny model może otrzymać **bardzo dobrze przygotowane środowisko decyzyjne**.

I właśnie tutaj zaczyna być widoczna największa zaleta naszego podejścia: zamiast próbować zastąpić słabszy model większym modelem, poprawiamy **system wokół modelu**.

---

# Zapowiedź Rozdziału 10

Następny rozdział będzie już bardzo praktyczny.

Zaprojektujemy **Workflow całego środowiska** — od utworzenia nowego repozytorium, przez pierwsze indeksowanie RAG, podłączenie Odysseusa, pracę z Git i dokumentacją, aż po zakończenie sesji i aktualizację Second Brain.

Powstanie rzeczywisty scenariusz:

```text
NOWY PROJEKT
     ↓
Git
     ↓
Dokumentacja
     ↓
RAG
     ↓
Odysseus
     ↓
AI poznaje projekt
     ↓
Ty pracujesz
     ↓
AI analizuje stan
     ↓
Decision Log
     ↓
Second Brain
     ↓
Git
```

Wtedy wszystkie elementy zaprojektowane w rozdziałach 1–9 zaczną działać jako **jeden spójny system**.

[1]: https://github.com/odysseus-dev/odysseus/discussions/1514?utm_source=chatgpt.com "AGENT PROMPT AND CONTEXT BLOAT · odysseus-dev odysseus · Discussion #1514 · GitHub"
[2]: https://blog.modelcontextprotocol.io/tags/tools/?utm_source=chatgpt.com "Tools | Model Context Protocol Blog"
[3]: https://github.com/odysseus-dev/odysseus?utm_source=chatgpt.com "GitHub - odysseus-dev/odysseus: Self-hosted AI workspace. · GitHub"

