**Rozdział 3 — Architektura fizyczna i infrastruktura**

---

> **Cel rozdziału**
>
> W poprzednim rozdziale zaprojektowaliśmy architekturę logiczną.
>
> Teraz zaprojektujemy **rzeczywisty system**, który będzie działał na Twoim komputerze.

---

# 3.1 Założenia infrastruktury

Projekt powstaje z myślą o jednym użytkowniku.

Aktualna konfiguracja sprzętowa:

* CPU: Ryzen 7 3700X
* GPU: RTX 4060 8 GB
* RAM: 16 GB
* SSD NVMe
* Windows 11

System powinien działać:

* całkowicie lokalnie,
* bez wysyłania kodu do chmury,
* 24/7 (jeżeli komputer jest włączony),
* z możliwością łatwej rozbudowy.

---

# 3.2 Dlaczego Docker?

Można uruchamiać wszystko ręcznie.

Nie będziemy.

Docker daje trzy ogromne zalety.

## Izolację

Każdy komponent działa osobno.

Awaria jednego nie psuje reszty.

---

## Powtarzalność

Jeżeli za rok zmienisz komputer:

```text
git clone

docker compose up
```

i system wraca praktycznie do identycznego stanu.

---

## Łatwy backup

Cały system można odtworzyć kopiując katalog projektu.

---

# 3.3 Architektura fizyczna

Docelowo system będzie wyglądał następująco.

```text
                           Windows 11
────────────────────────────────────────────────────────

                Docker Desktop

────────────────────────────────────────────────────────

          ┌────────────────────────────┐
          │         Odysseus           │
          └─────────────┬──────────────┘
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
    ChromaDB        SearXNG           ntfy

────────────────────────────────────────────

              Ollama (Host)

────────────────────────────────────────────

           Qwen / Gemma / DeepSeek

────────────────────────────────────────────

             SSD (projekty)

        Git
        Obsidian
        Dokumentacja
```

Odysseus domyślnie uruchamia w Dockerze własne usługi (m.in. ChromaDB, SearXNG i ntfy), natomiast Ollama zwykle działa jako osobny proces na hoście i jest podłączana przez endpoint HTTP. ([GitHub][1])

---

# 3.4 Dlaczego Ollama nie znajduje się w Dockerze?

To jedna z najważniejszych decyzji projektu.

Można uruchomić Ollamę w kontenerze.

Nie będziemy tego robić.

Powód:

GPU.

Ollama działa stabilniej jako natywna aplikacja Windows.

Odysseus łączy się z nią przez API.

```
Odysseus

↓

http://localhost:11434

↓

Ollama

↓

GPU
```

Dokumentacja Odysseusa również rekomenduje podłączenie istniejącej instancji Ollamy przez endpoint `localhost` (lub `host.docker.internal` w przypadku Dockera). ([GitHub][1])

---

# 3.5 Struktura katalogów

Nie chcemy bałaganu.

Na dysku powstanie jeden główny katalog.

```
D:\LAEW
```

Cała infrastruktura będzie znajdowała się tutaj.

---

Proponowana struktura:

```text
LAEW

├── docker/

├── odysseus/

├── projects/

├── knowledge/

├── obsidian/

├── backups/

├── models/

├── scripts/

├── logs/

└── temp/
```

---

# 3.6 Opis katalogów

## docker/

Przechowuje:

* docker-compose.yml
* konfigurację kontenerów
* pliki ENV

---

## odysseus/

Kod aplikacji.

Nie dodajemy tutaj własnych projektów.

---

## projects/

Najważniejszy katalog.

Każdy projekt ma własny folder.

Przykład:

```text
projects/

    STM32_Robot/

    AI_HedgeFund/

    Portfolio/

    PythonTools/
```

---

## knowledge/

Tutaj znajduje się wiedza.

Nie kod.

Przykład:

```text
knowledge/

Programming/

Electronics/

STM32/

Robotics/

Python/

AI/

Linux/
```

---

## obsidian/

Vault Obsidiana.

Nie mieszamy go z projektami.

---

## backups/

Automatyczne kopie.

---

## models/

Opcjonalny katalog.

Jeżeli kiedyś będziemy korzystać z modeli poza Ollamą.

---

## scripts/

Automatyzacja.

Na przykład:

```
backup.ps1

sync.ps1

update_index.py

cleanup.py
```

---

## logs/

Logi.

Nigdy nie trzymamy ich w katalogach projektów.

---

# 3.7 Zasada "Single Source of Truth"

Każdy element istnieje tylko raz.

Przykład.

Kod:

```
projects/

STM32_Robot/
```

Dokumentacja:

```
obsidian/
```

README:

```
projects/

STM32_Robot/

README.md
```

Nie kopiujemy README do Obsidiana.

Tworzymy jedynie link.

---

# 3.8 Połączenia między komponentami

System komunikuje się wyłącznie przez API.

```
Odysseus

↓

HTTP

↓

Ollama
```

```
Odysseus

↓

HTTP

↓

ChromaDB
```

```
Odysseus

↓

Filesystem

↓

Projekty
```

To bardzo ważne.

Komponenty nie powinny znać swojej wewnętrznej implementacji.

---

# 3.9 Przepływ zapytania

Załóżmy, że pytasz:

> "Jak działa scheduler?"

Przepływ wygląda następująco.

```
Ty

↓

Odysseus

↓

Agent

↓

Czy potrzebna dokumentacja?

↓

Tak

↓

Memory

↓

ChromaDB

↓

Repozytorium

↓

LLM

↓

Odpowiedź
```

Model otrzymuje już przygotowany kontekst.

Nie przeszukuje sam całego dysku.

---

# 3.10 Plan wykorzystania pamięci

Nie wszystkie dane są równie ważne.

Dlatego dzielimy pamięć.

## Poziom 1

RAM

Tylko:

* aktywna rozmowa
* aktualne pliki

---

## Poziom 2

ChromaDB

Tutaj trafiają:

* embeddingi
* indeks dokumentów
* pamięć semantyczna

Odysseus używa ChromaDB jako lokalnego magazynu pamięci wektorowej. ([GitHub][1])

---

## Poziom 3

SSD

Tutaj znajdują się:

* projekty
* dokumentacja
* PDF
* obrazy

---

# 3.11 Backup

Backup nie może obejmować wszystkiego.

Nie kopiujemy:

```
models/
```

Modele można ponownie pobrać.

Backup obejmuje:

```
projects/

knowledge/

obsidian/

docker/

.env
```

Oraz katalog danych Odysseusa.

Odysseus przechowuje bazę SQLite, pamięć, ChromaDB, ustawienia i przesłane pliki w katalogu `data/`, dlatego to właśnie ten katalog powinien być objęty regularnym backupem. ([GitHub][1])

---

# 3.12 Projekt na przyszłość

Już teraz projektujemy miejsce na rozbudowę.

Za dwa lata możesz dodać:

```
Whisper

TTS

Home Assistant

Nextcloud

Grafana

Prometheus
```

Architektura nie będzie wymagała przebudowy.

---

# 3.13 ADR (Architecture Decision Records)

### ADR-004

**Docker odpowiada wyłącznie za usługi infrastrukturalne.**

**Powód**

Łatwiejsze aktualizacje.

---

### ADR-005

**Ollama działa natywnie na hoście.**

**Powód**

Lepsza obsługa GPU.

Zgodność z dokumentacją Odysseusa.

---

### ADR-006

**Każdy projekt posiada własny katalog.**

Nigdy nie tworzymy wspólnego folderu "Kod".

---

### ADR-007

**Obsidian jest oddzielony od projektów.**

Nie mieszamy notatek z kodem.

---

# 3.14 Wnioski

Po trzech rozdziałach mamy już:

✅ zdefiniowany cel systemu,

✅ architekturę logiczną,

✅ architekturę fizyczną.

Od tego momentu możemy przejść do projektowania tego, co będzie miało **największy wpływ na jakość odpowiedzi AI**.

Nie będzie to model.

Będzie to **warstwa wiedzy**.

---

# Zapowiedź Rozdziału 4

Rozdział 4 będzie jednym z najważniejszych w całym dokumencie.

Zaprojektujemy **Knowledge Layer** — czyli sposób przechowywania wiedzy, dokumentacji, decyzji projektowych i repozytoriów tak, aby AI nie "zgadywało", lecz odpowiadało na podstawie rzeczywistych danych. Zdefiniujemy również standard dokumentacji dla każdego projektu (README, ADR, changelog, decyzje architektoniczne), aby zarówno Ty, jak i AI zawsze mieli jedno, spójne źródło informacji.

[1]: https://github.com/odysseus-dev/odysseus/blob/dev/docs/setup.md?utm_source=chatgpt.com "odysseus/docs/setup.md at dev · odysseus-dev/odysseus · GitHub"