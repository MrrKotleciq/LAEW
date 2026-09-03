# Rozdział 7 — Warstwa modeli AI (LLM Layer)

> **To jest rozdział, który odpowiada na pytanie:**
>
> **Jak dobrać modele, aby system był użyteczny przez następne kilka lat?**

---

# 7.1 Największy błąd początkujących

Większość osób budujących lokalne AI szuka:

> "Najlepszego modelu."

To błędne podejście.

Nie istnieje model najlepszy do wszystkiego.

Tak samo jak nie istnieje jeden programista, który jednocześnie jest najlepszym:

* frontendowcem,
* backendowcem,
* administratorem,
* architektem,
* DevOpsem.

Modele AI również mają specjalizacje.

---

# 7.2 Nasza filozofia

W naszym systemie model jest **wymiennym komponentem**.

Nigdy nie projektujemy architektury pod konkretny model.

Wygląda to tak:

```text
Odysseus

↓

LLM Provider

↓

Qwen
Gemma
DeepSeek
Llama
Przyszłe modele
```

Za rok możesz zmienić model.

Nie zmieniasz całego systemu.

---

# 7.3 Role modeli

Projekt będzie rozróżniał kilka ról.

Nie modeli.

Ról.

---

## Rola 1

### Primary Model

To model używany podczas rozmowy.

Jego zadania:

* analiza projektu,
* reasoning,
* debugowanie,
* architektura,
* planowanie.

---

## Rola 2

### Embedding Model

Nigdy nie odpowiada użytkownikowi.

Tworzy embeddingi.

Przykładowe modele rekomendowane przez Ollamę to m.in.:

* embeddinggemma,
* qwen3-embedding,
* all-minilm. ([Ollama][1])

---

## Rola 3

### Future Specialist Models

Docelowo system może korzystać z wielu modeli.

Przykład.

```text
Kod

↓

Model A

Dokumentacja

↓

Model B

OCR

↓

Model C

Audio

↓

Model D
```

Na początku nie będziemy tego wdrażać.

Ale architektura będzie na to gotowa.

---

# 7.4 Jakie cechy powinien mieć główny model?

Dla tego projektu benchmarki nie są najważniejsze.

Priorytety są inne.

## 1.

Bardzo dobre Tool Calling.

---

## 2.

Dobre rozumowanie.

---

## 3.

Stabilność.

---

## 4.

Duży kontekst.

---

## 5.

Dobra współpraca z RAG.

---

## 6.

Mała liczba halucynacji.

---

## 7.

Dobra obsługa kodu.

---

# 7.5 Czego NIE potrzebujemy?

Nie zależy nam na modelu, który napisze 1000 linii kodu.

To nie jest Copilot.

System ma przede wszystkim:

* analizować,
* tłumaczyć,
* planować,
* wyszukiwać informacje,
* wskazywać zależności.

To zupełnie inne zadanie.

---

# 7.6 Architektura modeli

Docelowo wygląda to tak.

```text
                   Odysseus

                       │

                       ▼

             Model Provider

       ┌────────┼────────┐

       ▼        ▼        ▼

 Primary   Embedding   Future

    │          │

    ▼          ▼

 Qwen      embeddinggemma

```

Każdy komponent odpowiada za jedno zadanie.

---

# 7.7 Dlaczego nie jeden ogromny model?

Załóżmy.

Masz model 70B.

Pytanie.

> "Dlaczego wybraliśmy UART?"

Model bez RAG odpowie:

> "Prawdopodobnie..."

Model 14B z dokumentacją odpowie:

> "ADR-004 mówi, że UART został wybrany ze względu na prostszą diagnostykę."

Dlatego inwestujemy w **architekturę**, a nie wyłącznie w rozmiar modelu.

---

# 7.8 Jak wybierać modele?

Nie patrzymy wyłącznie na benchmarki.

Oceniamy:

```text
Reasoning

★★★★★

Tool Calling

★★★★★

Kod

★★★★☆

Szybkość

★★★★☆

Zużycie VRAM

★★★★★

Stabilność

★★★★★
```

---

# 7.9 Modele a sprzęt

Nasza architektura musi działać na:

```text
RTX 4060

8 GB VRAM
```

Oznacza to:

* modele muszą być kwantyzowane,
* nie wszystkie modele będą działać wyłącznie na GPU,
* czas odpowiedzi jest ważniejszy niż maksymalna liczba parametrów.

Odysseus zawiera nawet **Hardware Scanner** i **Model Cookbook**, które pomagają dobrać modele odpowiednie do posiadanego GPU i pamięci. ([Odysseus AI][2])

---

# 7.10 Dlaczego Ollama?

Nie dlatego, że jest najlepsza.

Dlatego, że spełnia nasze wymagania.

Zapewnia:

* prostą instalację,
* zarządzanie modelami,
* lokalne API,
* łatwą wymianę modeli,
* obsługę embeddingów.

Ollama udostępnia zarówno API generowania odpowiedzi, jak i osobny endpoint `/api/embed` do tworzenia embeddingów, co dobrze pasuje do naszej architektury. ([Ollama][3])

---

# 7.11 Model jako usługa

Nie myślimy:

```text
Model.exe
```

Myślimy:

```text
Odysseus

↓

HTTP

↓

Ollama

↓

Model
```

Model jest usługą.

Nie aplikacją.

Dzięki temu możemy go wymienić bez zmian w pozostałych komponentach.

---

# 7.12 Aktualizacja modeli

System powinien umożliwiać:

```text
Gemma

↓

Qwen

↓

DeepSeek

↓

Nowy model
```

bez:

* przebudowy RAG,
* przebudowy Obsidiana,
* przebudowy dokumentacji.

---

# 7.13 Zarządzanie kontekstem

Model nie powinien otrzymywać:

```text
100 000 linii kodu
```

Powinien otrzymać:

```text
README

+

ADR

+

3 funkcje

+

2 klasy

+

1 datasheet
```

Czyli dokładnie to, czego potrzebuje.

Resztą zajmuje się RAG.

---

# 7.14 Współpraca z Odysseusem

Odysseus pełni rolę orkiestratora.

Model:

* nie zarządza plikami,
* nie zarządza pamięcią,
* nie indeksuje dokumentów.

To robi Odysseus.

Model odpowiada wyłącznie za analizę dostarczonego kontekstu.

---

# 7.15 Strategia rozwoju

Projekt zakłada trzy etapy.

### Etap 1

Jeden model.

Najprostsza konfiguracja.

---

### Etap 2

Oddzielny model embeddingów.

Lepszy RAG.

---

### Etap 3

Modele wyspecjalizowane.

Na przykład:

```text
Kod

↓

Model A

OCR

↓

Model B

Audio

↓

Model C
```

Nie wdrażamy tego od razu.

Projektujemy możliwość rozbudowy.

---

# ADR

### ADR-021

Model AI jest wymiennym komponentem.

---

### ADR-022

Embeddingi są generowane przez dedykowany model.

---

### ADR-023

RAG odpowiada za dostarczanie kontekstu.

Model odpowiada za analizę.

---

### ADR-024

System ma być gotowy na obsługę wielu modeli jednocześnie.

---

# Podsumowanie rozdziału

Najważniejsza decyzja architektoniczna brzmi:

> **Nie wybieramy "najlepszego modelu". Budujemy system, w którym model można wymienić w ciągu kilku minut, bez naruszania całej architektury.**

To podejście sprawi, że Twoje środowisko pozostanie aktualne nawet wtedy, gdy za rok lub dwa pojawią się nowe modele przewyższające obecne rozwiązania.

---

# Zapowiedź Rozdziału 8

W następnym rozdziale zajmiemy się **agentami i narzędziami (MCP)**. To będzie moment, w którym AI przestanie być wyłącznie modelem językowym, a stanie się aktywnym uczestnikiem pracy nad projektem: będzie przeszukiwać repozytoria, czytać dokumentację, wykonywać polecenia w terminalu, analizować pliki oraz korzystać z narzędzi w kontrolowany i bezpieczny sposób. Rozdział ten będzie stanowił fundament codziennej pracy z Odysseusem jako lokalnym środowiskiem AI.

[1]: https://docs.ollama.com/capabilities/embeddings?utm_source=chatgpt.com "Embeddings - Ollama"
[2]: https://odysseusai.dev/ollama?utm_source=chatgpt.com "Odysseus AI Ollama Setup Guide"
[3]: https://docs.ollama.com/api/embed?utm_source=chatgpt.com "Generate embeddings - Ollama"
