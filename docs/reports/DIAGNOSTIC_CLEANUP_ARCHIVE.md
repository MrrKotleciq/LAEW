# Archiwum diagnostyczne LAEW

Daty i godziny podano w czasie lokalnym (Europe/Warsaw). Z oryginalnych logów zachowano tylko fragmenty potrzebne do rozpoznania problemów i wynik regresji.

## ChromaDB HNSW — otwarte

4 listopada 2026 o 12:23, podczas regresji zapisanej w `diagnostics-regression.log`, zapytanie Global RAG w teście `test_prefetch_reaches_provider_before_first_generation` zakończyło się błędem.

```text
ERR_RAG_FAILURE
Error creating hnsw segment reader: Nothing found on disk
```

To wystąpienie dotyczy ścieżki prefetch. Osobny przebieg Stage 2B.2 odnotował tę samą sygnaturę w teście zakresu Chief Agenta. Powtórzenia izolowane przechodziły, a przyczyna pozostaje nieustalona. Zdarzenie uzupełnia [otwarty wpis w backlogu](../roadmap/BACKLOG.md#future-candidates-not-yet-sequenced) i [raport Stage 2B.2](STAGE_2B2_CONTEXT_PRESERVATION_PL.md).

## Diagnostyka Workbench po restarcie — historyczne

4 listopada 2026 około 12:31, w przebiegu zapisanym w `diagnostics-regression-verified.log`, test `test_four_diagnostic_turns_remain_inspectable_after_restart` przerwał się w `_stream_chat` podczas wywołania z anulowaniem po prefetch.

```text
assert self._executor is not None
AssertionError
```

W przechwyconych logach wystąpiły również błędy atrap `SimpleNamespace` związane z brakującymi atrybutami `baseline` i `enqueue`. Przyczyna asercji i jej związek z błędami atrap pozostają nieustalone. Asercję odnotowano jako zdarzenie historyczne.

## Zakończona regresja — historyczne

6 listopada 2026 około 18:05, w przebiegu oznaczonym `baseline-loopback`, odnotowano **1509 passed, 4 skipped, 2 deselected**. Przebieg trwał 195,88 s i zgłosił 39 ostrzeżeń. Lista zmian zapisana obok logu odpowiada commitowi `5071fda`. Wynik stanowi punkt odniesienia dla tamtej regresji. Przyczyna sporadycznego błędu HNSW pozostaje otwarta.
