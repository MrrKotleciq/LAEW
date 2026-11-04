# MemoryTool — walidacja kategorii, 2026-11-03

Naprawiono kontrakt kategorii bez zmiany architektury SQLite + ChromaDB,
ustawień Long-Term Memory, gałęzi i danych produkcyjnych. Nie wykonano commitów
ani push. Wcześniejsze, niezacommitowane zmiany projektu zostały zachowane.

## Potwierdzona przyczyna

Sprawdzono dopasowany fragment istniejącej sesji
`runtime/sessions/conversation-6ed21b2a-4fdb-4624-9637-ede96e3f096d.json`.
Zdarzenia wywołań 39, 42 i 45 zawierają kolejno kategorie:

1. `preferencje i plany podróżnicze`
2. `preferences`
3. `personal`

Wszystkie były natywnymi wywołaniami `MemoryTool__propose`, z nowymi identyfikatorami
wywołań. Każde otrzymało `ERR_INVALID_INPUT` i samo `Invalid memory category.`.
Nie znaleziono w tym incydencie kategorii `travel` ani `travel_goal`.
Nie przeprowadzano ekstrakcji ani masowej analizy istniejących rozmów.

Backend prawidłowo odrzucał wartości spoza zbioru, lecz MemoryTool ogłaszał
`category` wyłącznie jako `string`, bez `enum` i opisu dopuszczalnych wartości.
Lokalny opis operacji podawał jedynie nazwy argumentów. Ekstraktor miał właściwy,
ale osobno wpisany zestaw kategorii w instrukcjach i schemacie. Błąd nie wyjaśniał,
jak poprawić argumenty. Chief ponawiał wywołania zgodnie z istniejącymi limitami,
lecz nadal zgadywał kategorie. `preferences` było jednoznacznym odpowiednikiem
`preference`, którego poprzedni walidator nie normalizował.

Nie stwierdzono przestawienia argumentów przez adaptery: OpenAI przekazuje
parametry funkcji Responses, Gemini zachowuje je w narzędziu Chat Completions,
a Local korzysta z tekstowego protokołu `tool_call`. Testy sprawdzają rzeczywiste
adaptery z kontrolowanym transportem, łącznie z przekazaniem błędu do następnego
żądania. Sam zapisany fragment incydentu nie identyfikuje jednoznacznie dostawcy.

## Taksonomia i decyzja

Zachowano wszystkie dotychczasowe wartości:

| Kategoria | Rodzaj informacji |
| --- | --- |
| `preference` | Upodobania, preferowane sposoby działania, styl wycieczek |
| `education` | Edukacja, kwalifikacje i formalna nauka |
| `interest` | Zainteresowania, bez wnioskowania o umiejętnościach |
| `skill` | Umiejętności i biegłość |
| `goal` | Przyszłe zamiary, cele podróżnicze i zawodowe |
| `decision` | Potwierdzone wybory, w tym decyzje projektowe |
| `constraint` | Trwałe wymagania, ograniczenia i granice |
| `fact` | Pozostałe trwałe fakty, również doświadczenie i osiągnięcia |

Nie brakuje typu niezbędnego do wskazanych przypadków. Osobna kategoria
`experience` mogłaby kiedyś ułatwić filtrowanie doświadczenia, ale obecnie `fact`
wystarcza. Nie dodano kategorii podróżniczej, tagów ani migracji: nie rozwiązują
potwierdzonej przyczyny, a istniejące rekordy zachowują znaczenie i wartości.
Kategoria pozostaje wymagana w MemoryTool; `fact` jest jawnym wyborem ogólnym,
a nie cichym zamiennikiem niepoprawnego argumentu.

## Zmiany

- `laew/memory/categories.py` stanowi wspólny kontrakt wartości, opisów,
  schematu, normalizacji i błędu kategorii.
- MemoryTool ma `enum` i instrukcję wyboru rodzaju informacji. Ten sam opis trafia
  do modeli Local przez metadane narzędzia, bez edycji głównych promptów.
- Schemat natywnej ekstrakcji oraz instrukcje ekstrakcji korzystają z kontraktu.
  OpenAI zachowuje enum w Responses; Gemini zachowuje go w parametrach funkcji
  interfejsu zgodności. Lokalny protokół pozostaje tekstowy.
- MemoryStore, MemoryService, zatwierdzanie Review i Auto walidują ten sam
  kontrakt. API i CLI przechodzą przez te granice. Settings pobiera kategorie
  i opisy z `/api/memory/state`, zamiast utrzymywać kopię listy w JavaScript.
- Bezpieczna normalizacja obejmuje wielkość liter, zewnętrzne spacje oraz tylko
  jawne aliasy: `preferences`, `interests`, `skills`, `goals`, `decisions`,
  `constraints`, `facts`. Zapisywane są wartości kanoniczne. Tematy i nieznane
  etykiety, w tym `personal`, nie są zgadywane ani zamieniane na `fact`.
- Niepoprawna kategoria zwraca `ERR_INVALID_INPUT`, `field=category`,
  `accepted_categories`, `retryable=true` i instrukcję korekty. Szczegóły są
  zachowane także przy walidacji przed wykonaniem przez Chiefa i brokera.
  Poprawione wywołania podlegają dotychczasowym limitom; natywne wywołanie musi
  mieć nowy call ID. Nie zmieniono limitów iteracji ani reguł aprobaty.
- Pusty argument kategorii podczas edycji jest odrzucany; tylko pominięcie
  kategorii zachowuje dotychczasową wartość.

## Weryfikacja

Końcowy zestaw regresyjny: **413 passed** w 35,74 s. Obejmuje testy pamięci,
Chiefa, walidacji wywołań, logowania, brokera, Web/API, CLI oraz narzędzi
filesystem/git/terminal/web, adaptera llama.cpp i integracji chmurowych.
Testy Settings: **2 passed**. `git diff --check` bez błędów.

Dodane przypadki obejmują wszystkie kategorie i ich zgodność ze schematami,
walidację Review, aliasy, wartości niepoprawne (również listę i obiekt),
ustrukturyzowany błąd, brak zapisów ubocznych, brak nieuprawnionego zapisu
projektowego, awarię magazynu, deduplikację i ponowne otwarcie starszych rekordów
z dotychczasowymi kategoriami. Zweryfikowano cel podróżniczy Edynburg,
preferencje wycieczek, zainteresowania, umiejętności, cel zawodowy i decyzję
projektową. Korekta błędnego wywołania działa przez adaptery OpenAI API,
ChatGPT, Gemini, Ollama i llama.cpp; alias `goals` zapisuje `goal`.

Integracja używa odizolowanych SQLite, SessionStore i nowego procesu ChromaDB
na losowym porcie loopback. Sprawdza:

`User → Chief → MemoryTool → broker → MemoryService → SQLite → Review → ChromaDB → recall`

oraz ekstrakcję z dowodem użytkownika przez Review i Auto do SQLite/outbox/ChromaDB.
Przed akceptacją jawna propozycja nie trafia do aktywnych rekordów ani indeksu,
także w Auto. Pozostały istniejące testy interwału pięciu zakończonych tur,
checkpointów, konfliktów, separacji projektów i odtwarzania indeksu.

Pierwszy przebieg zatrzymało niedostępne domyślne temp pytest; kolejne używały
osobnych katalogów pod `runtime/`. Sandbox blokował połączenia loopback
(`WinError 10013`), więc testy rzeczywistego serwera uruchomiono z eskalacją.
Testowa blokada usług produkcyjnych pozostała aktywna. Nie zmieniono testów,
aby pomijały tę blokadę.

## Ograniczenia

Nie wykonywano płatnych ani produkcyjnych wywołań modeli: transporty modeli są
kontrolowane, natomiast SQLite, SessionStore i ChromaDB są rzeczywiste.
Poprawność interpretacji znaczenia wypowiedzi nadal zależy od modelu; backend
gwarantuje dopuszczalną kategorię, zakres i zasady zapisu, a nie doskonałą
klasyfikację semantyczną. Natywny enum wspomaga model, ale nie zastępuje
walidatora backendu. Local otrzymuje opis wartości w istniejącym protokole
tekstowym, bez dodawania natywnego function calling.

ChromaDB zgłosiła 38 ostrzeżeń deprecacyjnych o `asyncio.iscoroutinefunction`.
Nie wpływały na wynik testów i nie są częścią naprawy kategorii.
