# Zakres integracji z Codex CLI

Ten dokument opisuje, jakie funkcje lokalnego `codex-cli 0.130.0` maja byc docelowo dostepne w DevLink. Jest to mapa funkcji, a nie lista rzeczy juz zaimplementowanych w aplikacji.

Etap 2 opiera sie na:

- lokalnym `codex --version` i `codex --help`,
- oficjalnej dokumentacji OpenAI Codex CLI,
- dokumentacji trybu non-interactive,
- dokumentacji approvals/security,
- dokumentacji MCP.

## Zasada glowna

DevLink nie zastepuje Codex CLI. DevLink steruje lokalnym Codex CLI przez bezpieczna warstwe:

```text
mobile -> backend Django -> lokalne CLI DevLink -> lokalny codex
```

Kod projektu zostaje na komputerze uzytkownika. Backend przechowuje prompt, metadane, statusy, output i historie. Operacje na plikach wykonuje lokalne CLI DevLink, ktore uruchamia `codex` w zarejestrowanym katalogu projektu.

Backend nie laczy sie bezposrednio z komputerem. To lokalne CLI cyklicznie odpytuje backend o zadania przypisane do sparowanego urzadzenia.

## Slownik statusow w DevLink

| Status | Znaczenie |
| --- | --- |
| `mvp` | funkcja potrzebna do podstawowego dzialajacego scenariusza |
| `full_app` | funkcja docelowej aplikacji, ale niekonieczna do szkolnego MVP |
| `advanced` | funkcja zaawansowana, wymaga osobnego UI i testow |
| `dangerous` | funkcja moze zmienic srodowisko, konfiguracje albo dostep do plikow; wymaga potwierdzenia |
| `experimental` | funkcja z lokalnego CLI oznaczona jako eksperymentalna albo wymagajaca osobnego etapu |

## Klasyfikacja ryzyka

| Poziom | Przyklady | Zasada w DevLink |
| --- | --- | --- |
| `low` | `login status`, `features list`, `completion`, odczyt helpa | mozna pokazac w UI jako informacje |
| `medium` | `exec`, `review`, `resume`, `fork` w katalogu projektu | dozwolone po wyborze zarejestrowanego projektu |
| `high` | `apply`, `mcp add/remove`, `plugin marketplace`, `update`, `logout`, `sandbox` | wymagane osobne potwierdzenie i log audytowy |
| `critical` | `danger-full-access`, `--dangerously-bypass-approvals-and-sandbox`, `remote-control`, `app-server`, `exec-server`, `cloud apply` | domyslnie zablokowane do czasu approval flow |

## Domyslny wariant MVP

W MVP DevLink powinien uruchamiac Codexa w wariancie:

```bash
codex exec --cd <project_path> --json --sandbox workspace-write -
```

Zasady:

- prompt trafia przez `stdin`,
- proces uruchamiamy bez shella,
- `project_path` pochodzi tylko z projektu dodanego lokalnie przez CLI,
- backend nie przyjmuje dowolnej sciezki od telefonu,
- `--ask-for-approval never` nie jest domyslna konfiguracja MVP,
- `danger-full-access` i `--dangerously-bypass-approvals-and-sandbox` sa zablokowane do osobnego etapu approval flow.

Oficjalne docs wskazuja, ze `codex exec` domyslnie dziala w trybie read-only, a dla automatyzacji z edycja plikow nalezy jawnie ustawic minimalnie potrzebne uprawnienia, np. `--sandbox workspace-write`. Tryb `danger-full-access` powinien byc uzywany tylko w kontrolowanym srodowisku.

Etap 5 implementuje ten wariant jako core MVP:

- CLI uruchamia proces bez shella,
- prompt idzie przez `stdin`,
- `stdout` z `--json` jest mapowany na `TaskEvent(agent_event)`,
- `stderr` jest mapowany na `TaskEvent(stderr)`,
- timeout konczy task jako `timed_out`,
- anulowanie z telefonu zatrzymuje lokalny proces i zostawia task w statusie `canceled`.

## Mapa komend Codex CLI

| Komenda | Subkomendy / warianty | DevLink status | Ryzyko | Potwierdzenie | Planowany etap | Powierzchnia w aplikacji |
| --- | --- | --- | --- | --- | --- | --- |
| `codex [PROMPT]` | tryb interaktywny TUI | `full_app` | `medium` | tak, jesli start z telefonu | 10 | przyszly panel realtime |
| `codex exec` | `resume`, `review` | `mvp` | `medium` | nie dla `workspace-write`, tak dla rozszerzen | 5 | podstawowe zadania z telefonu |
| `codex exec --json` | JSONL event stream | `mvp` | `medium` | nie | 5 | mapowanie na `TaskEvent` |
| `codex exec resume` | `--last`, `--all`, `SESSION_ID` | `full_app` | `medium` | tak dla `--all` | 6 | kontynuacja zadania |
| `codex exec review` | `--uncommitted`, `--base`, `--commit` | `full_app` | `medium` | tak dla szerokiego zakresu | 7 | review jako typ zadania |
| `codex review` | `--uncommitted`, `--base`, `--commit`, `--title` | `full_app` | `medium` | tak | 7 | ekran code review |
| `codex resume` | `--last`, `--all`, `--include-non-interactive` | `full_app` | `medium` | tak | 6 | kontynuacja sesji |
| `codex fork` | `--last`, `--all`, `SESSION_ID` | `full_app` | `medium` | tak | 6 | alternatywna galaz sesji |
| `codex apply` | `<TASK_ID>` | `dangerous` | `high` | tak | 7 | aplikowanie diffa po podgladzie |
| `codex login` | `status`, `--with-api-key`, `--with-access-token`, `--device-auth` | `advanced` | `high` | tak poza `status` | 7 | lokalny status auth i instrukcje |
| `codex logout` | brak | `dangerous` | `high` | tak | 7 | wylogowanie lokalnego Codexa |
| `codex mcp` | `list`, `get`, `add`, `remove`, `login`, `logout` | `advanced` | `high` | tak dla zmian | 8 | zarzadzanie MCP |
| `codex plugin` | `marketplace add/upgrade/remove` | `advanced` | `high` | tak | 8 | zarzadzanie marketplace pluginow |
| `codex features` | `list`, `enable`, `disable` | `advanced` | `low`/`high` | tak dla `enable/disable` | 7 | podglad i zmiana flag |
| `codex debug` | `models`, `app-server`, `prompt-input` | `advanced` | `low`/`medium` | zalezne od komendy | 7 | diagnostyka lokalna |
| `codex completion` | `bash`, `elvish`, `fish`, `powershell`, `zsh` | `full_app` | `low` | nie | 7 | instrukcja setupu shella |
| `codex update` | brak | `dangerous` | `high` | tak | 7 | aktualizacja lokalnego CLI |
| `codex sandbox` | `macos`, `linux`, `windows` | `dangerous` | `high` | tak | 7 | uruchamianie komend w sandboxie |
| `codex mcp-server` | stdio server | `experimental` | `critical` | tak, domyslnie ukryte | 11 | lokalna usluga eksperymentalna |
| `codex app-server` | `proxy`, `generate-ts`, `generate-json-schema` | `experimental` | `critical` | tak, domyslnie ukryte | 11 | lokalna usluga eksperymentalna |
| `codex remote-control` | headless app-server | `experimental` | `critical` | tak, domyslnie ukryte | 11 | nie w MVP |
| `codex exec-server` | standalone exec-server | `experimental` | `critical` | tak, domyslnie ukryte | 11 | nie w MVP |
| `codex cloud` | `exec`, `status`, `list`, `apply`, `diff` | `experimental` | `critical` | tak | 11 | integracja z Codex Cloud |
| `codex app` | uruchomienie aplikacji desktopowej | `advanced` | `medium` | tak | 11 | opcjonalny skrot lokalny |

## Opcje globalne i opcje `exec`

| Opcja | Znaczenie | Status | Ryzyko | Plan DevLink |
| --- | --- | --- | --- | --- |
| `--cd`, `-C` | katalog roboczy | `mvp` | `medium` | tylko sciezki projektow dodanych przez CLI |
| `--sandbox read-only` | brak zapisu w workspace | `full_app` | `low` | tryb bezpiecznego audytu |
| `--sandbox workspace-write` | zapis w workspace | `mvp` | `medium` | domyslny tryb pracy Codexa w MVP |
| `--sandbox danger-full-access` | szeroki dostep do systemu | `dangerous` | `critical` | zablokowane do approval flow |
| `--dangerously-bypass-approvals-and-sandbox` | brak approvali i sandboxa | `dangerous` | `critical` | zablokowane, tylko izolowane testy |
| `--json` | JSONL event stream | `mvp` | `medium` | podstawowe zrodlo eventow `TaskEvent` |
| `--output-last-message`, `-o` | zapis finalnej odpowiedzi do pliku | `full_app` | `medium` | opcjonalny lokalny artefakt |
| `--output-schema` | wymuszenie finalnego JSON wedlug schematu | `advanced` | `medium` | przyszle strukturyzowane wyniki |
| `--model`, `-m` | wybor modelu | `full_app` | `medium` | ustawienie projektu albo taska |
| `--profile`, `-p` | profil z `config.toml` | `full_app` | `medium` | wybor profilu lokalnego |
| `--image`, `-i` | zalaczniki obrazow | `advanced` | `medium` | przyszle uploady/zalaczniki lokalne |
| `--search` | web search dla modelu | `advanced` | `medium` | wymagane jasne oznaczenie w UI |
| `--add-dir` | dodatkowy katalog dostepny dla Codexa | `dangerous` | `high` | wymaga lokalnej zgody |
| `--ask-for-approval untrusted` | automatycznie tylko zaufane komendy | `full_app` | `medium` | dobry tryb dla pracy interaktywnej |
| `--ask-for-approval on-request` | model decyduje kiedy prosic | `full_app` | `medium` | docelowo z approval flow |
| `--ask-for-approval never` | brak pytania o approval | `dangerous` | `high` | nie jako domyslne MVP |
| `--skip-git-repo-check` | pozwala pracowac poza repo Git | `dangerous` | `high` | zablokowane albo tylko ostrzezenie |
| `--ephemeral` | bez zapisu session files | `advanced` | `medium` | opcja prywatnosci |
| `--ignore-user-config` | ignoruje `config.toml` | `advanced` | `medium` | izolowane taski |
| `--ignore-rules` | ignoruje reguly uzytkownika/projektu | `dangerous` | `high` | domyslnie zablokowane |
| `--config`, `-c` | override konfiguracji | `advanced` | `high` | tylko allowlista |
| `--enable`, `--disable` | flagi funkcji | `advanced` | `high` | tylko panel admin/advanced |
| `--oss`, `--local-provider` | lokalne providery OSS | `advanced` | `medium` | dalszy etap |
| `--remote`, `--remote-auth-token-env` | polaczenie TUI z remote app serverem | `experimental` | `critical` | nie w MVP |

## Jak mapujemy output `codex exec --json`

Docs OpenAI opisuja `--json` jako JSON Lines stream. DevLink powinien mapowac go tak:

| Event Codexa | Event DevLink | Uzycie |
| --- | --- | --- |
| `thread.started` | `status` albo `agent_event` | zapis `thread_id`/session id |
| `turn.started` | `status` | task przeszedl do pracy agenta |
| `item.started` | `agent_event` | start komendy, reasoning, MCP toola, web search itd. |
| `item.completed` | `stdout` albo `agent_event` | czastkowy wynik, agent message, file change |
| `turn.completed` | `final` | koniec zadania i usage |
| `turn.failed` | `error` | blad runu |
| `error` | `error` | blad CLI albo agenta |

W Etapie 5 wystarczy przechowywac oryginalny JSON eventu w `TaskEvent.payload` i dodatkowo wyciagac najwazniejsze pola do prostego UI: typ eventu, tekst, status, exit code i final message.

## Funkcje zablokowane do pozniejszych etapow

Nastepujace funkcje nie powinny byc dostepne jako zwykle akcje z telefonu przed approval flow:

- `--dangerously-bypass-approvals-and-sandbox`,
- `--sandbox danger-full-access`,
- `--add-dir` poza katalog projektu,
- `--ignore-rules`,
- `codex apply`,
- `codex logout`,
- `codex update`,
- `codex mcp add/remove/login/logout`,
- `codex plugin marketplace add/upgrade/remove`,
- `codex sandbox ...`,
- `codex remote-control`,
- `codex app-server`,
- `codex exec-server`,
- `codex mcp-server`,
- `codex cloud apply`,
- `codex cloud exec`.

Dla tych funkcji DevLink powinien pozniej dodac: osobny ekran potwierdzenia, opis ryzyka, audit log, limit do sparowanego urzadzenia, opcjonalny wymog potwierdzenia lokalnego na komputerze.

## Plan wdrazania funkcji

| Etap | Zakres Codex CLI |
| --- | --- |
| 3 | parowanie i blokada dostepu do urzadzenia |
| 4 | projekty, katalogi robocze, domyslne opcje taskow |
| 5 | stabilne `codex exec --json --sandbox workspace-write -` |
| 6 | sesje, `exec resume`, `resume`, `fork` |
| 7 | chat workspace, capabilities, wybor modelu/sandboxa/web search, skills jako jawne hinty |
| 8 | `review`, `apply`, `features`, `debug`, `completion`, `update`, `login status`, `logout`, MCP, pluginy i konfiguracja Codexa |
| 9 | approval flow i funkcje podwyzszonego ryzyka |
| 10 | realtime output zamiast samego pollingu |
| 11 | `cloud`, serwery eksperymentalne, obrazy, `--output-schema`, `--search`, OSS/local provider |

## Zrodla

- https://developers.openai.com/codex/cli
- https://developers.openai.com/codex/cli/reference
- https://developers.openai.com/codex/noninteractive
- https://developers.openai.com/codex/agent-approvals-security
- https://developers.openai.com/codex/mcp
