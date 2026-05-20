# Wzorzec strukturalny: Adapter

## Wybrany wzorzec

Adapter zostal zastosowany w module CLI do ujednolicenia sposobu wykonywania roznych agentow. `CodexAdapter` i `ShellAdapter` wystawiaja ten sam kontrakt `AgentAdapter`, mimo ze pod spodem moga wykonywac calkowicie inne operacje.

Implementacja:

- `apps/cli/devlink_cli/agents/base.py`
- `apps/cli/devlink_cli/agents/adapters/codex.py`
- `apps/cli/devlink_cli/agents/adapters/shell.py`
- `apps/cli/devlink_cli/daemon.py`

Diagram:

- `adapter.puml`
- `adapter.svg`

## Uzasadnienie wyboru wzorca

DevLink integruje sie z zewnetrznym narzedziem `Codex CLI`, ktore zwraca dane jako proces terminalowy i strumien JSON. Backend oraz aplikacja mobilna nie powinny znac szczegolow tego formatu. Potrzebny jest wspolny format zdarzen, ktory mozna zapisac w backendzie i wyswietlic w telefonie.

Adapter pasuje tutaj, bo tlumaczy specyficzny format zewnetrznego narzedzia na format domenowy aplikacji: `AgentEvent`.

## Problem projektowy rozwiazywany przez wzorzec

Problemem jest roznica miedzy formatem zewnetrznego narzedzia a formatem aplikacji.

`Codex CLI` pracuje jako:

- proces systemowy,
- stdout/stderr,
- JSON stream,
- kody wyjscia,
- informacje o diffach i finalnej odpowiedzi.

DevLink potrzebuje prostych eventow:

```text
AgentEvent(event_type, message, payload)
```

Adapter oddziela te dwa swiaty. Dzieki temu daemon nie musi parsowac JSONL z Codexa ani znac szczegolow terminala.

## Sposob wykorzystania w aplikacji

1. Daemon dostaje gotowy `AgentTask`.
2. Factory zwraca adapter zgodny z `AgentAdapter`.
3. Daemon uruchamia `adapter.run(task)`.
4. `CodexAdapter` uruchamia `codex exec --json`.
5. Adapter czyta stdout, stderr i eventy JSON.
6. Adapter zamienia je na `AgentEvent`.
7. Daemon wysyla `AgentEvent` do backendu.
8. Backend zapisuje eventy i udostepnia je aplikacji mobilnej.

## Stan wewnetrzny i zewnetrzny

Stan zewnetrzny:

- lokalny system plikow projektu,
- proces `Codex CLI`,
- konfiguracja zadania,
- aktualny stan repozytorium Git,
- backend odbierajacy eventy.

Stan wewnetrzny:

- tymczasowe bufory stdout/stderr,
- lista czytelnych komunikatow,
- lista finalnych odpowiedzi asystenta,
- lista edytowanych plikow,
- baseline diff do porownania zmian,
- kolejka eventow asynchronicznych.

Ten stan istnieje tylko podczas wykonywania jednego taska. Trwale dane trafiaja do backendu jako `TaskEvent` i finalny wynik zadania.
