# Milestone 2: Tool Runtime Wrappers — UKOŃCZONO ✓

**Data ukończenia**: 2026-08-28  
**Status**: Wszystkie komponenty zaimplementowane i przetestowane

---

## Podsumowanie

Milestone 2 został w pełni zrealizowany. Zaimplementowano wszystkie 4 narzędzia runtime z wymuszaniem bezpieczeństwa poniżej warstwy modelu (Principle P8).

---

## Zaimplementowane komponenty

### 1. **PathResolver** (`laew/security/path_resolver.py`)
- ✅ Rozwiązywanie aliasów `@project`, `@projects`, `@knowledge`
- ✅ Ochrona przed path traversal (`../` escaping)
- ✅ Blokowanie restrykcyjnych ścieżek (`.git`, `secrets`)
- ✅ Filtrowanie wzorców (`.env`, `.gguf`, `.safetensors`)
- ✅ 18 testów jednostkowych

### 2. **FilesystemTool** (`laew/tools/filesystem.py`)
- ✅ Operacje read-only: `view_file`, `list_dir`, `find_by_name`, `grep_search`
- ✅ Operacje mutujące (z approval): `write_file`, `replace_file_content`, `delete_file`
- ✅ Wymuszanie mutacji tylko w `@project`
- ✅ Read-only access dla `@knowledge` i `@projects`
- ✅ 28 testów jednostkowych

### 3. **TerminalTool** (`laew/tools/terminal.py`)
- ✅ Blacklist destrukcyjnych komend (`sudo`, `rm -rf`, `chmod`, `dd`, itp.)
- ✅ Allowlist bezpiecznych komend inspekcyjnych (`ls`, `cat`, `git status`, itp.)
- ✅ Workspace confinement (bez path traversal poza workspace)
- ✅ Timeout execution (domyślnie 30s)
- ✅ 19 testów jednostkowych

### 4. **GitTool** (`laew/tools/git.py`)
- ✅ Operacje read-only: `git_status`, `git_diff`, `git_log`
- ✅ Operacje mutujące (z approval): `git_commit`, `git_checkout`, `git_branch`
- ✅ Blokowanie zabronionych subkomend (`reset --hard`, `push --force`, `clean -f`, `branch -D`)
- ✅ Wymuszanie angielskich komunikatów git (locale `LC_ALL=C`)
- ✅ 24 testy jednostkowe

### 5. **WebTool** (`laew/tools/web.py`)
- ✅ Read-only search: `search_web(query, domain)`
- ✅ URL fetching z konwersją do Markdown: `read_url_content(url)`
- ✅ Ograniczenie protokołów do `http://` i `https://`
- ✅ Ochrona przed wyciekiem sekretów
- ✅ 15 testów jednostkowych

---

## Statystyki testów

```
Total: 124 unit tests — ALL PASSING ✓

Breakdown:
- test_path_resolver.py:     18 tests ✓
- test_filesystem_tool.py:   28 tests ✓
- test_terminal_tool.py:     19 tests ✓
- test_git_tool.py:          24 tests ✓
- test_web_tool.py:          15 tests ✓
- test_manifest.py:          20 tests ✓ (Milestone 1)
```

---

## Struktura katalogów

```
laew/
├── security/
│   ├── __init__.py
│   └── path_resolver.py          (18 tests)
├── tools/
│   ├── __init__.py
│   ├── base.py                   (Tool, ToolResult, ErrorCode)
│   ├── filesystem.py             (28 tests)
│   ├── terminal.py               (19 tests)
│   ├── git.py                    (24 tests)
│   └── web.py                    (15 tests)
├── manifest.py                   (20 tests — Milestone 1)
└── cli.py

tests/unit/
├── test_path_resolver.py
├── test_filesystem_tool.py
├── test_terminal_tool.py
├── test_git_tool.py
├── test_web_tool.py
└── test_manifest.py
```

---

## Kluczowe osiągnięcia

1. **Programmatic Security (P8)**:
   - Wszystkie restrykcje bezpieczeństwa wymuszane w kodzie Pythona
   - Zero polegania na prompt compliance
   - Deny-by-default dla wszystkich destrukcyjnych operacji

2. **ADR-010 Path Aliasing**:
   - Pełne wsparcie dla `@project`, `@projects`, `@knowledge`
   - Path traversal prevention na poziomie resolvera
   - Mutacje ograniczone tylko do `@project`

3. **Approval Gates**:
   - Filesystem mutations wymagają user approval
   - Git state changes wymagają user approval
   - Terminal non-allowlisted commands wymagają approval
   - Read-only operations (Web, Filesystem read) bez approval

4. **Standardized Error Codes**:
   - Wszystkie narzędzia zwracają `ToolResult` z error codes z `CONTRACT.md`
   - Spójna obsługa błędów w całym systemie
   - Pełna zgodność z kontraktami narzędzi

5. **Comprehensive Testing**:
   - 104 nowe testy dla Milestone 2 (plus 20 z Milestone 1)
   - Coverage security boundaries, approval gates, error paths
   - Wszystkie testy przechodzą ✓

---

## Następne kroki (Milestone 3)

**Chief Agent Runtime & Tool Orchestration**:
1. Implementacja Chief Agent loop
2. Integracja z tool wrappers
3. Context budgeting (ADR-004)
4. Prompt layering (ADR-005)
5. RAG integration
6. Memory persistence

---

## Czas wykonania

- Szacowany: 9-14h
- Rzeczywisty: ~1 sesja (kontynuowana po context compaction)

---

## Uwagi techniczne

1. **Git locale handling**: Wszystkie git commands wykonywane z `LC_ALL=C` dla konsystentnych angielskich komunikatów błędów (rozwiązuje problem polskich locale).

2. **Web tool dependencies**: Używa `requests` dla HTTP i opcjonalnie `html2text` dla konwersji Markdown (graceful fallback jeśli brak).

3. **Tool base class**: Abstract `Tool` class z metodami `validate()`, `execute()`, `call()` zapewnia spójny interfejs dla wszystkich narzędzi.

4. **Error code enum**: `ErrorCode` enum w `base.py` definiuje wszystkie standardowe kody błędów zgodnie z CONTRACT.md.

---

**Status: MILESTONE 2 COMPLETED ✓**  
**All 124 unit tests passing**  
**Ready for Milestone 3: Chief Agent Runtime**
