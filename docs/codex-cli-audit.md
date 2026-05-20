# Audyt lokalnego Codex CLI

Data audytu: 2026-05-15  
System: Windows / PowerShell  
Katalog audytu: `C:\Users\Adam\Desktop\Programing\ProOpr\projekt\devlink`

## Wersja

```text
codex --version
codex-cli 0.130.0
```

## Zrodla porownawcze

- `codex --help` i helpy lokalnych podkomend.
- https://developers.openai.com/codex/cli
- https://developers.openai.com/codex/cli/reference
- https://developers.openai.com/codex/noninteractive
- https://developers.openai.com/codex/agent-approvals-security
- https://developers.openai.com/codex/mcp

Jezeli lokalny help i docs roznia sie szczegolami, dla implementacji DevLink przyjmujemy lokalny help jako prawde dla zainstalowanej wersji, a docs jako wyjasnienie intencji i zasad bezpieczenstwa.

## `codex --help`

Lokalne CLI udostepnia tryb interaktywny oraz ponizsze komendy:

```text
exec            Run Codex non-interactively [aliases: e]
review          Run a code review non-interactively
login           Manage login
logout          Remove stored authentication credentials
mcp             Manage external MCP servers for Codex
plugin          Manage Codex plugins
mcp-server      Start Codex as an MCP server (stdio)
app-server      [experimental] Run the app server or related tooling
remote-control  [experimental] Start a headless app-server with remote control enabled
app             Launch the Codex desktop app
completion      Generate shell completion scripts
update          Update Codex to the latest version
sandbox         Run commands within a Codex-provided sandbox
debug           Debugging tools
apply           Apply the latest diff produced by Codex agent as a git apply
resume          Resume a previous interactive session
fork            Fork a previous interactive session
cloud           [EXPERIMENTAL] Browse tasks from Codex Cloud and apply changes locally
exec-server     [EXPERIMENTAL] Run the standalone exec-server service
features        Inspect feature flags
help            Print help
```

Najwazniejsze opcje globalne:

```text
-c, --config <key=value>
--enable <FEATURE>
--disable <FEATURE>
--remote <ADDR>
--remote-auth-token-env <ENV_VAR>
-i, --image <FILE>...
-m, --model <MODEL>
--oss
--local-provider <OSS_PROVIDER>
-p, --profile <CONFIG_PROFILE>
-s, --sandbox <read-only|workspace-write|danger-full-access>
--dangerously-bypass-approvals-and-sandbox
-C, --cd <DIR>
--add-dir <DIR>
-a, --ask-for-approval <untrusted|on-failure|on-request|never>
--search
--no-alt-screen
```

## `codex exec --help`

`codex exec` jest glowna komenda dla DevLink MVP. Uruchamia Codexa non-interactively.

```text
Usage: codex exec [OPTIONS] [PROMPT]
       codex exec [OPTIONS] <COMMAND> [ARGS]

Commands:
  resume  Resume a previous session by id or pick the most recent with --last
  review  Run a code review against the current repository
  help    Print help
```

Argument promptu:

```text
[PROMPT]
Initial instructions for the agent. If not provided as an argument
(or if "-" is used), instructions are read from stdin.
```

Opcje istotne dla DevLink:

```text
-i, --image <FILE>...
-m, --model <MODEL>
--oss
--local-provider <OSS_PROVIDER>
-p, --profile <CONFIG_PROFILE>
-s, --sandbox <read-only|workspace-write|danger-full-access>
--dangerously-bypass-approvals-and-sandbox
-C, --cd <DIR>
--add-dir <DIR>
--skip-git-repo-check
--ephemeral
--ignore-user-config
--ignore-rules
--output-schema <FILE>
--color <always|never|auto>
--json
-o, --output-last-message <FILE>
```

Wniosek dla MVP:

```bash
codex exec --cd <project_path> --json --sandbox workspace-write -
```

## `codex exec resume --help`

```text
Usage: codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]

Arguments:
  [SESSION_ID]  Conversation/session id (UUID) or thread name
  [PROMPT]      Prompt to send after resuming the session. If "-" is used, read from stdin

Options:
  --last
  --all
  -i, --image <FILE>
  -m, --model <MODEL>
  --dangerously-bypass-approvals-and-sandbox
  --skip-git-repo-check
  --ephemeral
  --ignore-user-config
  --ignore-rules
  --json
  -o, --output-last-message <FILE>
```

Plan DevLink: Etap 6, po zapisaniu i mapowaniu Codex session/thread id.

## `codex exec review --help`

```text
Usage: codex exec review [OPTIONS] [PROMPT]

Options:
  --uncommitted
  --base <BRANCH>
  --commit <SHA>
  -m, --model <MODEL>
  --title <TITLE>
  --dangerously-bypass-approvals-and-sandbox
  --skip-git-repo-check
  --ephemeral
  --ignore-user-config
  --ignore-rules
  --json
  -o, --output-last-message <FILE>
```

Plan DevLink: Etap 7, jako typ zadania code review.

## `codex review --help`

```text
Usage: codex review [OPTIONS] [PROMPT]

Options:
  --uncommitted
  --base <BRANCH>
  --commit <SHA>
  --title <TITLE>
```

Plan DevLink: Etap 7. Mobile powinno dac wybor: review zmian lokalnych, review commita albo review wzgledem brancha bazowego.

## `codex resume --help`

```text
Usage: codex resume [OPTIONS] [SESSION_ID] [PROMPT]

Options:
  --last
  --all
  --include-non-interactive
  --remote <ADDR>
  --remote-auth-token-env <ENV_VAR>
  -i, --image <FILE>...
  -m, --model <MODEL>
  --oss
  --local-provider <OSS_PROVIDER>
  -p, --profile <CONFIG_PROFILE>
  -s, --sandbox <read-only|workspace-write|danger-full-access>
  --dangerously-bypass-approvals-and-sandbox
  -C, --cd <DIR>
  --add-dir <DIR>
  -a, --ask-for-approval <untrusted|on-failure|on-request|never>
  --search
  --no-alt-screen
```

Plan DevLink: Etap 6. `--all` i `--include-non-interactive` wymagaja uwagi, bo moga pokazac sesje spoza biezacego projektu.

## `codex fork --help`

```text
Usage: codex fork [OPTIONS] [SESSION_ID] [PROMPT]

Options:
  --last
  --all
  --remote <ADDR>
  --remote-auth-token-env <ENV_VAR>
  -i, --image <FILE>...
  -m, --model <MODEL>
  --oss
  --local-provider <OSS_PROVIDER>
  -p, --profile <CONFIG_PROFILE>
  -s, --sandbox <read-only|workspace-write|danger-full-access>
  --dangerously-bypass-approvals-and-sandbox
  -C, --cd <DIR>
  --add-dir <DIR>
  -a, --ask-for-approval <untrusted|on-failure|on-request|never>
  --search
  --no-alt-screen
```

Plan DevLink: Etap 6. Fork tworzy alternatywny tok pracy z istniejacej sesji.

## `codex apply --help`

```text
Usage: codex apply [OPTIONS] <TASK_ID>
```

Plan DevLink: Etap 7, ale jako funkcja wysokiego ryzyka. Przed uruchomieniem mobile musi pokazac, co bedzie aplikowane, i wymagac potwierdzenia.

## `codex login --help` i `codex logout --help`

`codex login`:

```text
Commands:
  status  Show login status

Options:
  --with-api-key
  --with-access-token
  --device-auth
```

`codex logout`:

```text
Remove stored authentication credentials
```

Plan DevLink: w MVP CLI DevLink moze wykonywac `codex login status` w `doctor`. Pelne logowanie/wylogowanie zostaje jako instrukcja lokalna albo etap zaawansowany, bo dotyczy sekretow i lokalnych credentiali.

## `codex mcp --help`

```text
Commands:
  list
  get
  add
  remove
  login
  logout
```

`codex mcp add`:

```text
Usage: codex mcp add [OPTIONS] <NAME> (--url <URL> | -- <COMMAND>...)

Options:
  --env <KEY=VALUE>
  --url <URL>
  --bearer-token-env-var <ENV_VAR>
```

`codex mcp get`:

```text
Usage: codex mcp get [OPTIONS] <NAME>

Options:
  --json
```

Plan DevLink: Etap 8. `list` i `get` sa mniej ryzykowne, ale `add/remove/login/logout` moga zmieniac lokalna konfiguracje i laczyc Codexa z dodatkowymi narzedziami.

## `codex plugin --help`

```text
Commands:
  marketplace  Manage plugin marketplaces for Codex
```

`codex plugin marketplace`:

```text
Commands:
  add
  upgrade
  remove
```

Plan DevLink: Etap 8. Zmiany marketplace pluginow wymagaja potwierdzenia.

## `codex sandbox --help`

```text
Commands:
  macos    Run a command under Seatbelt (macOS only)
  linux    Run a command under the Linux sandbox
  windows  Run a command under Windows restricted token
```

`codex sandbox windows`:

```text
Usage: codex sandbox windows [OPTIONS] [COMMAND]...

Options:
  --permissions-profile <NAME>
  -C, --cd <DIR>
  --include-managed-config
```

Plan DevLink: Etap 7/9. Nie jest potrzebne w MVP; wymaga kontroli komend, katalogu roboczego i profili uprawnien.

## `codex features --help`

```text
Commands:
  list     List known features with their stage and effective state
  enable   Enable a feature in config.toml
  disable  Disable a feature in config.toml
```

Plan DevLink: `list` moze byc diagnostyka, `enable/disable` wymaga potwierdzenia, bo zmienia konfiguracje lokalna.

## `codex debug --help`

```text
Commands:
  models        Render the raw model catalog as JSON
  app-server    Tooling: helps debug the app server
  prompt-input  Render the model-visible prompt input list as JSON
```

Plan DevLink: Etap 7. To narzedzia diagnostyczne; trzeba uwazac, zeby nie wysylac do backendu sekretow ani nadmiarowych danych z lokalnego prompt input.

## `codex completion --help`

```text
Usage: codex completion [OPTIONS] [SHELL]

Possible values:
  bash, elvish, fish, powershell, zsh
```

Plan DevLink: ekran instrukcji lokalnej konfiguracji, raczej nie komenda z telefonu.

## `codex cloud --help`

```text
Commands:
  exec    Submit a new Codex Cloud task without launching the TUI
  status  Show the status of a Codex Cloud task
  list    List Codex Cloud tasks
  apply   Apply the diff for a Codex Cloud task locally
  diff    Show the unified diff for a Codex Cloud task
```

`codex cloud exec`:

```text
Usage: codex cloud exec [OPTIONS] --env <ENV_ID> [QUERY]

Options:
  --env <ENV_ID>
  --attempts <ATTEMPTS>
  --branch <BRANCH>
```

`codex cloud apply`:

```text
Usage: codex cloud apply [OPTIONS] <TASK_ID>

Options:
  --attempt <N>
```

Plan DevLink: Etap 11. Funkcje cloud nie sa czescia lokalnego MVP, bo przenosza prace poza lokalny komputer i maja osobna semantyke bezpieczenstwa.

## Serwery eksperymentalne

`codex app-server`:

```text
Commands:
  proxy
  generate-ts
  generate-json-schema

Options:
  --listen <URL>
  --analytics-default-enabled
  --ws-auth <MODE>
  --ws-token-file <PATH>
  --ws-token-sha256 <HEX>
  --ws-shared-secret-file <PATH>
  --ws-issuer <ISSUER>
  --ws-audience <AUDIENCE>
  --ws-max-clock-skew-seconds <SECONDS>
```

`codex remote-control`:

```text
[experimental] Start a headless app-server with remote control enabled
```

`codex exec-server`:

```text
[EXPERIMENTAL] Run the standalone exec-server service

Options:
  --listen <URL>
  --remote <URL>
  --executor-id <ID>
  --name <NAME>
```

`codex mcp-server`:

```text
Start Codex as an MCP server (stdio)
```

Plan DevLink: Etap 11 albo pozniej. Te funkcje otwieraja lokalne protokoly/serwery i nie powinny byc dostepne jako zwykla akcja mobile.

## Wnioski dla kolejnych etapow

- Etap 5 powinien skupic sie wylacznie na stabilnym `codex exec --json`.
- Etap 6 potrzebuje modelowania `thread_id`/session id, zanim dodamy `resume` i `fork`.
- Etap 7 moze dodac panel komend, ale funkcje modyfikujace konfiguracje musza miec potwierdzenia.
- Etap 8 powinien osobno opisac MCP i pluginy, bo moga rozszerzyc mozliwosci agenta.
- Etap 9 jest konieczny przed oddaniem uzytkownikowi opcji `danger-full-access`, `apply`, `mcp add/remove` i podobnych.
