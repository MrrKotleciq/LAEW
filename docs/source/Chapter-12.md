# Rozdział 12 — Skalowanie systemu

> **Cel tego rozdziału:** zaprojektować LAEW tak, aby rozpoczęcie od jednego projektu i jednego lokalnego modelu nie doprowadziło później do konieczności przebudowy całego systemu.

Do tej pory projektowaliśmy środowisko przede wszystkim z perspektywy pojedynczego użytkownika i pojedynczego komputera:

```text
1 użytkownik
1 PC
1 główny model
1 Odysseus
kilka projektów
```

To jest właściwy punkt startowy.

Nie chcemy jednak projektować systemu, który działa tylko przy:

```text
100 plikach
20 notatkach
1 repozytorium
1 modelu
```

Docelowo powinien bez problemu obsługiwać:

```text
10+ projektów
dziesiątki repozytoriów
tysiące notatek
duże dokumentacje
wiele modeli
wiele baz wiedzy
```

---

# 12.1 Najważniejsza zasada skalowania

Najważniejszą decyzją architektoniczną jest:

> **Skalujemy system przez dodawanie komponentów, a nie przez powiększanie jednego komponentu do absurdalnych rozmiarów.**

Nie chcemy:

```text
                ONE GIANT DATABASE
                       │
                EVERYTHING
                       │
                    AI
```

Chcemy:

```text
                 LAEW CORE
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
   Project A     Project B     Project C
       │             │             │
       ▼             ▼             ▼
      RAG           RAG           RAG
```

---

# 12.2 Skalowanie ma kilka wymiarów

Nie istnieje tylko jeden rodzaj skalowania.

Musimy uwzględnić:

1. skalowanie liczby projektów,
2. skalowanie liczby dokumentów,
3. skalowanie RAG,
4. skalowanie modeli,
5. skalowanie agentów,
6. skalowanie sprzętu,
7. skalowanie automatyzacji,
8. skalowanie Second Brain.

---

# 12.3 Etap pierwszy — jeden projekt

Początkowo:

```text
LAEW
│
└── Projects
    │
    └── RobotController
```

RAG:

```text
RobotController
      ↓
   ChromaDB
```

To jest idealny punkt startowy.

Nie ma potrzeby tworzenia skomplikowanej infrastruktury.

---

# 12.4 Etap drugi — kilka projektów

Pojawia się:

```text
Projects/
│
├── RobotController/
├── AI-Hedge-Fund/
├── STM32-Lab/
├── University/
└── Python-Tools/
```

Pojawia się wtedy pierwszy ważny problem:

> Czy wszystko powinno trafić do jednej bazy RAG?

**Nie.**

---

# 12.5 Izolacja projektów

Preferowana architektura:

```text
                    RAG
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Project A    Project B    Project C
        │            │            │
        ▼            ▼            ▼
     Index A      Index B      Index C
```

Dzięki temu pytanie:

> "Jak działa komunikacja SPI w RobotController?"

nie przeszukuje przypadkowo:

```text
AI-Hedge-Fund
University
Python Tools
```

---

# 12.6 Project Namespace

Każdy projekt powinien mieć własny namespace:

```text
project:robot-controller
project:ai-hedge-fund
project:stm32-lab
```

Wtedy RAG może wykonywać:

```text
search(
    query,
    namespace="robot-controller"
)
```

zamiast:

```text
search(
    query,
    everything=True
)
```

---

# 12.7 Global Knowledge

Nie wszystko powinno należeć do projektu.

Istnieją informacje wspólne:

```text
Knowledge/
│
├── Programming/
├── Python/
├── C/
├── STM32/
├── AI/
└── Robotics/
```

Mamy więc dwa poziomy:

```text
GLOBAL
   │
   ├── Programming
   ├── AI
   └── Robotics

PROJECT
   │
   └── RobotController
```

---

# 12.8 Hierarchiczny RAG

Docelowo możemy więc stworzyć:

```text
                  QUERY
                    │
                    ▼
             Query Classifier
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
      PROJECT RAG          GLOBAL RAG
          │                   │
          └─────────┬─────────┘
                    ▼
                 RERANK
                    │
                    ▼
                 CONTEXT
```

Przykład:

> "Dlaczego używamy DMA w moim sterowniku?"

Najpierw:

```text
RobotController RAG
```

następnie:

```text
Global STM32 Knowledge
```

---

# 12.9 Nie wrzucamy wszystkiego do kontekstu

To jedna z najważniejszych zasad skalowania.

Jeżeli mamy:

```text
10 000 dokumentów
```

nie oznacza to:

```text
10 000 dokumentów → LLM
```

RAG powinien wykonać:

```text
10 000 dokumentów
       ↓
retrieval
       ↓
50 wyników
       ↓
reranking
       ↓
5–15 fragmentów
       ↓
LLM
```

---

# 12.10 Context Budget

Model ma ograniczony kontekst.

Dlatego definiujemy:

```text
Context Budget
```

Przykładowo:

```text
System prompt      2k
Conversation        4k
RAG                8k
Tool results        4k
-----------------------
Total              18k
```

Pozostała przestrzeń musi pozostać dostępna na reasoning i odpowiedź.

Nie należy maksymalizować kontekstu tylko dlatego, że model technicznie go posiada.

---

# 12.11 Skalowanie dokumentów

Załóżmy:

```text
100 dokumentów
```

Nie ma problemu.

Potem:

```text
1 000
```

nadal jest dobrze.

Następnie:

```text
10 000
```

pojawiają się problemy:

* czas indeksowania,
* liczba embeddingów,
* rozmiar bazy,
* jakość retrieval,
* duplikaty.

---

# 12.12 Metadata filtering

Rozwiązaniem jest metadata.

Każdy dokument może posiadać:

```json
{
  "project": "robot-controller",
  "type": "architecture",
  "language": "c",
  "topic": "spi",
  "source": "obsidian"
}
```

Wtedy zapytanie:

> "Pokaż decyzje dotyczące SPI."

może ograniczyć wyszukiwanie do:

```text
topic = spi
type = decision
```

---

# 12.13 Typy dokumentów

Proponuję standaryzację:

```text
architecture
decision
research
code
documentation
manual
note
meeting
experiment
bug
```

Dzięki temu RAG może rozróżniać:

```text
kod
```

od:

```text
decyzji architektonicznej
```

---

# 12.14 Priorytety wiedzy

Nie wszystkie dokumenty mają taką samą wartość.

Przykładowo:

```text
ADR                 HIGH
Architecture        HIGH
README              HIGH
Research             MEDIUM
Notes                MEDIUM
Old experiments      LOW
Temporary notes      VERY LOW
```

Reranker może uwzględniać taki priorytet.

---

# 12.15 Aktualność wiedzy

Kolejnym wymiarem jest czas.

Dokument:

```text
Architecture v1
```

może być mniej istotny niż:

```text
Architecture v4
```

Dlatego metadata powinna zawierać:

```text
created_at
updated_at
version
status
```

Przykład:

```yaml
status: superseded
version: 2
```

AI powinno wiedzieć:

> Ta decyzja została zastąpiona.

---

# 12.16 Nie usuwamy starej wiedzy bez powodu

Stare ADR mogą być bardzo wartościowe.

Na przykład:

```text
ADR-003
Wybrano SPI.

ADR-014
Zmieniono SPI na I2C.

ADR-021
Powrócono do SPI.
```

Jeżeli usuniemy ADR-003 i ADR-014, AI nie będzie wiedziało:

> dlaczego ostatecznie wróciliśmy do SPI.

Historia decyzji jest częścią wiedzy.

---

# 12.17 Skalowanie modeli

Model powinien być wymiennym komponentem:

```text
                  Odysseus
                     │
                  Provider
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
     Ollama        API A         API B
       │
 ┌─────┼─────┐
 ▼     ▼     ▼
Model1 Model2 Model3
```

Dzięki temu nie przywiązujemy całego systemu do jednego modelu.

---

# 12.18 Model routing

Docelowo możemy stosować routing.

Przykład:

```text
QUERY
 │
 ├── proste pytanie → mały model
 │
 ├── analiza kodu → coder
 │
 ├── reasoning → reasoning model
 │
 ├── research → model + web
 │
 └── embedding → embedding model
```

---

# 12.19 Mały model jako router

Nie każda operacja wymaga dużego modelu.

Przykład:

> "Podsumuj ten dokument."

może zostać wykonane przez mniejszy model.

Natomiast:

> "Przeanalizuj konflikt między trzema modułami i zaproponuj architekturę."

wymaga mocniejszego modelu.

Docelowo:

```text
                 Router
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
      Small       Coder    Reasoning
```

---

# 12.20 RTX 4060 jako ograniczenie

W naszej konfiguracji sprzętowej musimy pamiętać, że lokalny GPU jest ograniczonym zasobem.

Dlatego nie projektujemy:

```text
5 dużych modeli
+
3 embedding models
+
2 rerankery
```

działających jednocześnie.

Zamiast tego:

```text
VRAM
 │
 └── aktywny model
```

a pozostałe komponenty mogą działać:

```text
CPU
RAM
Docker
```

zależnie od konkretnej konfiguracji.

---

# 12.21 Model lifecycle

Modele powinny mieć stany:

```text
AVAILABLE
LOADED
ACTIVE
UNLOADED
```

Przykład:

```text
Qwen
ACTIVE

Gemma
AVAILABLE

DeepSeek
AVAILABLE
```

Nie musimy trzymać wszystkich modeli w VRAM.

---

# 12.22 Skalowanie agentów

Na początku wystarczy:

```text
ONE AGENT
```

Z czasem możemy przejść do:

```text
                    ORCHESTRATOR
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       Research         Code         Documentation
        Agent           Agent            Agent
```

Ale nie powinniśmy robić tego zbyt wcześnie.

---

# 12.23 Dlaczego nie zaczynać od multi-agent?

Ponieważ:

```text
1 agent
```

jest łatwiejszy do:

* debugowania,
* monitorowania,
* kontrolowania,
* optymalizacji.

Jeżeli jeden agent nie działa stabilnie, pięciu agentów nie rozwiąże problemu.

Wręcz przeciwnie.

---

# 12.24 Kiedy multi-agent ma sens?

Dopiero kiedy pojawi się realna potrzeba.

Na przykład:

```text
User
 ↓
Planner
 ├── Research Agent
 ├── Code Analysis Agent
 ├── Documentation Agent
 └── Testing Agent
```

Planner zbiera wyniki:

```text
Research
+
Code
+
Tests
+
Docs
      ↓
Final synthesis
```

---

# 12.25 Skalowanie Second Brain

Second Brain również musi mieć hierarchię.

Docelowo:

```text
Knowledge/
│
├── Global/
│   ├── Programming/
│   ├── AI/
│   ├── Robotics/
│   └── Engineering/
│
├── Projects/
│   ├── RobotController/
│   ├── AI-Hedge-Fund/
│   └── STM32/
│
├── University/
│
├── Research/
│
└── Archive/
```

---

# 12.26 Archive

Nie usuwamy starych danych.

Przenosimy je do:

```text
Archive/
```

Dzięki temu:

```text
ACTIVE KNOWLEDGE
```

pozostaje małe, a:

```text
HISTORICAL KNOWLEDGE
```

jest nadal dostępne.

---

# 12.27 Skalowanie repozytoriów

Przy wielu projektach:

```text
Projects/
│
├── project-a/
├── project-b/
├── project-c/
├── project-d/
└── ...
```

nie powinno oznaczać:

```text
jeden gigantyczny indeks.
```

Każdy projekt otrzymuje:

```text
project_id
```

i własną przestrzeń logiczną.

---

# 12.28 Cross-project knowledge

Czasami AI musi jednak wiedzieć:

> "Jakie rozwiązanie zastosowałem w innym projekcie?"

Wtedy możemy zrobić:

```text
Project RAG
      ↓
Global Knowledge
      ↓
Cross-project search
```

Ale takie wyszukiwanie powinno być uruchamiane świadomie lub przez router.

---

# 12.29 Przykład cross-project

Projekt A:

```text
STM32 Robot
```

ma implementację:

```text
UART DMA
```

Projekt B:

```text
Sensor Hub
```

potrzebuje podobnego rozwiązania.

AI może znaleźć:

```text
Project A
↓
UART DMA implementation
↓
ADR
↓
lessons learned
```

i wykorzystać tę wiedzę przy projekcie B.

To jest jeden z największych potencjalnych benefitów Second Brain.

---

# 12.30 Skalowanie automatyzacji

Przy jednym projekcie:

```text
post-commit
```

wystarczy.

Przy 20 projektach potrzebujemy centralnego systemu:

```text
                    Automation Service
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
    Project A           Project B           Project C
       │                   │                   │
       ▼                   ▼                   ▼
      RAG                 RAG                 RAG
```

---

# 12.31 Event Bus

W dalszym etapie możemy zastosować prosty event bus.

Przykładowe wydarzenie:

```json
{
  "event": "project.changed",
  "project": "robot-controller",
  "commit": "a81d9f"
}
```

Subscriber:

```text
RAG Indexer
```

otrzymuje:

```text
project.changed
```

i uruchamia indeksowanie.

---

# 12.32 Nie potrzebujemy od razu Kafka

Przy naszym zastosowaniu byłoby to zdecydowanie przesadą.

Na początku wystarczy:

```text
Python
+
filesystem
+
Git hooks
+
queue
```

Dopiero przy naprawdę dużej skali można rozważyć cięższe rozwiązania.

---

# 12.33 Skalowanie storage

Dane możemy podzielić:

```text
FAST STORAGE
│
├── active projects
├── RAG database
└── caches

COLD STORAGE
│
├── archive
├── old projects
└── snapshots
```

Dzięki temu szybki SSD nie jest zapełniany wszystkim, co kiedykolwiek stworzyliśmy.

---

# 12.34 Model Storage

Modele mogą zajmować dużo miejsca.

Nie ma sensu przechowywać:

```text
10 wersji tego samego modelu
```

jeżeli korzystamy tylko z jednej.

Powinniśmy mieć:

```text
Models/
│
├── active/
└── archive/
```

oraz manifest:

```yaml
active_model: qwen-...
```

---

# 12.35 Skalowanie sprzętowe

Jeżeli w przyszłości pojawi się mocniejszy GPU:

```text
RTX 4060
   ↓
RTX XXXX
```

architektura nie powinna się zmienić.

Zmienia się:

```text
hardware profile
```

a nie:

```text
entire system architecture
```

---

# 12.36 Hardware Profiles

Możemy więc mieć:

```text
profiles/
├── rtx4060.yaml
├── high-end.yaml
└── laptop.yaml
```

Przykład:

```yaml
gpu_vram: 8GB

preferred_model:
  coder: small

max_context:
  local: ...
```

System dobiera konfigurację do sprzętu.

---

# 12.37 Skalowanie pionowe i poziome

W klasycznej architekturze mamy:

### Vertical scaling

Lepszy sprzęt:

```text
więcej RAM
więcej VRAM
szybszy SSD
```

### Horizontal scaling

Więcej komponentów:

```text
więcej agentów
więcej modeli
więcej usług
```

Nasze LAEW powinno przede wszystkim skalować się pionowo na początku.

Dopiero później poziomo.

---

# 12.38 Dlaczego?

Ponieważ jesteśmy systemem:

```text
single-user
local-first
```

Nie potrzebujemy:

```text
10 serwerów
```

Potrzebujemy:

```text
dobrze wykorzystanego PC.
```

---

# 12.39 Granica skalowania

W pewnym momencie lokalny komputer może przestać wystarczać.

Na przykład:

```text
100 000+ dokumentów
```

lub:

```text
bardzo duże modele
```

Wtedy możemy zastosować hybrydę:

```text
LOCAL
│
├── sensitive data
├── active projects
├── local LLM
└── private knowledge

CLOUD
│
├── massive reasoning
├── large context
└── heavy research
```

Ale lokalna architektura nadal pozostaje podstawą.

---

# 12.40 Provider abstraction

To właśnie dlatego wcześniej zaprojektowaliśmy:

```text
Odysseus
   │
Provider abstraction
   │
 ┌─┴──────────────┐
 ▼                ▼
Ollama          External API
```

Model nie może być fundamentem całej infrastruktury.

Jest **wymiennym silnikiem**.

---

# 12.41 Skalowanie bezpieczeństwa

Im więcej komponentów, tym większa powierzchnia ataku.

Dlatego:

```text
1 projekt
```

może mieć:

```text
minimalne permissions
```

a:

```text
20 projektów
```

wymaga:

```text
project isolation
permissions
sandboxing
secrets management
```

---

# 12.42 Least privilege

Agent powinien mieć dostęp tylko do tego, czego potrzebuje.

Przykład:

```text
Research Agent
→ Web
→ Knowledge
❌ Git write
❌ Shell
```

Natomiast:

```text
Development Agent
→ Project files
→ Git
→ Shell
```

ale nadal nie:

```text
❌ całe C:/
```

---

# 12.43 Skalowanie konfiguracji

Nie możemy mieć:

```text
config.json
```

z 5000 liniami.

Lepiej:

```text
config/
│
├── system.yaml
├── models.yaml
├── rag.yaml
├── projects.yaml
├── security.yaml
└── automation.yaml
```

Każda konfiguracja odpowiada jednej warstwie.

---

# 12.44 Skalowanie promptów

To samo dotyczy promptów:

```text
prompts/
│
├── system/
├── agents/
├── tools/
├── coding/
├── research/
└── debugging/
```

Nie jeden gigantyczny prompt.

---

# 12.45 Versioning promptów

Prompt również jest kodem.

Dlatego:

```text
prompt v1.0
prompt v1.1
prompt v1.2
```

powinien być przechowywany w Git.

Jeżeli jakość AI nagle spadnie, możemy sprawdzić:

> Co zmieniliśmy?

---

# 12.46 Skalowanie testów

Im bardziej system się rozrasta, tym ważniejsze stają się testy.

Powinniśmy testować:

```text
RAG retrieval
tool calling
prompt routing
model selection
sync
backup
permissions
```

Przykład:

```text
Question:
"Jak komunikujemy się z IMU?"

Expected:
SPI + DMA
```

Jeżeli po zmianie konfiguracji AI odpowiada:

> I2C

wiemy, że coś się zepsuło.

---

# 12.47 Evaluation Set

Docelowo stworzymy:

```text
eval/
```

z pytaniami testowymi.

Przykład:

```text
eval/
├── rag.yaml
├── tools.yaml
├── architecture.yaml
└── reasoning.yaml
```

To pozwoli porównywać:

```text
Model A
vs
Model B
```

bez polegania wyłącznie na subiektywnym odczuciu.

---

# 12.48 Skalowanie bez utraty prostoty

To jest najważniejsza zasada całego rozdziału:

> **Możliwość skalowania nie oznacza obowiązku używania skomplikowanej architektury od pierwszego dnia.**

Start:

```text
Odysseus
+
Ollama
+
1 model
+
1 RAG
+
Obsidian
+
Git
```

Docelowo:

```text
Odysseus
+
Model Router
+
Multiple Models
+
Multiple RAG namespaces
+
Second Brain
+
Automation
+
Multiple Agents
+
Evaluation
```

Ale przejście między nimi jest stopniowe.

---

# 12.49 Ewolucja systemu

### Level 1

```text
LLM
```

### Level 2

```text
LLM
+
Tools
```

### Level 3

```text
LLM
+
Tools
+
RAG
```

### Level 4

```text
LLM
+
Tools
+
RAG
+
Second Brain
```

### Level 5

```text
LLM
+
Tools
+
RAG
+
Second Brain
+
Automation
```

### Level 6

```text
Multi-model
+
Multi-agent
+
Routing
+
Evaluation
```

Nie przeskakujemy od razu do Level 6.

---

# 12.50 Docelowa architektura skalowalna

```text
                           USER
                            │
                            ▼
                      ┌───────────┐
                      │ ODYSSEUS  │
                      └─────┬─────┘
                            │
                       ORCHESTRATOR
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
       PROJECTS          KNOWLEDGE          TOOLS
          │                 │                 │
     ┌────┼────┐            │          ┌──────┼──────┐
     ▼    ▼    ▼            ▼          ▼      ▼      ▼
    RAG  RAG  RAG        GLOBAL RAG   Git   Files   Web
     │    │    │            │
     └────┴────┴────────────┘
                    │
                 RETRIEVAL
                    │
                 RERANKER
                    │
                 CONTEXT
                    │
              MODEL ROUTER
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
     LOCAL        CODER       REASONING
      LLM           LLM          LLM
```

---

# 12.51 Co pozostaje niezmienne?

Nawet przy bardzo dużej rozbudowie pozostają te same fundamentalne elementy:

```text
Git
Knowledge
Projects
RAG
Odysseus
Tools
Models
Human control
```

Zmienia się tylko ich skala.

---

# 12.52 ADR

### ADR-051

Każdy projekt otrzymuje własny logiczny namespace RAG.

### ADR-052

Global Knowledge jest oddzielone od wiedzy projektowej.

### ADR-053

Retrieval odbywa się przed przekazaniem danych do LLM.

### ADR-054

System wykorzystuje metadata filtering.

### ADR-055

Modele są wymiennymi komponentami.

### ADR-056

Multi-agent zostanie wdrożony dopiero po osiągnięciu stabilności single-agent.

### ADR-057

Second Brain wykorzystuje hierarchię Global → Project → Archive.

### ADR-058

System jest projektowany jako local-first, single-user.

### ADR-059

Skalowanie infrastruktury nie powinno wymagać zmiany podstawowego workflow użytkownika.

---

# 12.53 Podsumowanie

Po tym rozdziale mamy już zaprojektowaną architekturę, która może rozpocząć się bardzo prosto:

```text
RTX 4060
+
16 GB RAM
+
Ollama
+
Odysseus
+
jeden lokalny model
+
Obsidian
+
RAG
+
Git
```

ale może ewoluować do:

```text
                 LAEW
                  │
          ┌───────┴────────┐
          ▼                ▼
       Projects         Knowledge
          │                │
      Multi-RAG       Global RAG
          │                │
          └───────┬────────┘
                  ▼
             Orchestrator
                  │
          ┌───────┼────────┐
          ▼       ▼        ▼
       Research  Coding  Reasoning
        Agent    Agent    Agent
          │       │        │
          └───────┼────────┘
                  ▼
             Model Router
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
      Local     Local      API
       LLM       LLM
```

Najważniejsza rzecz jest jednak taka:

> **Nie projektujemy systemu na skalę, której dzisiaj nie potrzebujemy. Projektujemy go tak, aby jego późniejsze zwiększenie skali nie wymagało wyrzucenia tego, co zbudowaliśmy wcześniej.**

To właśnie dlatego **modularność** jest jednym z najważniejszych wymagań całego LAEW.

---

# Następny rozdział — Rozdział 13: Roadmapa wdrożenia

W kolejnym i ostatnim rozdziale przełożymy całą architekturę na **konkretny plan budowy systemu**:

```text
ETAP 0 → przygotowanie PC
ETAP 1 → Ollama + model
ETAP 2 → Odysseus
ETAP 3 → Git + Tools
ETAP 4 → Obsidian
ETAP 5 → RAG
ETAP 6 → Second Brain
ETAP 7 → automatyzacja
ETAP 8 → monitoring
ETAP 9 → ewaluacja
ETAP 10 → rozbudowa
```

Określimy również **co należy zrobić najpierw, czego na razie nie instalować, jakie elementy są opcjonalne oraz kiedy przechodzić do kolejnego poziomu**. To będzie praktyczne zamknięcie całej dokumentacji i punkt wyjścia do rzeczywistej implementacji LAEW.

