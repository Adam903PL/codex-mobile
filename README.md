# DevLink

DevLink to monorepo dla aplikacji mobilnej sterującej lokalnym `Codex CLI` z telefonu.
Telefon komunikuje się z backendem Django REST Framework, a komputer użytkownika uruchamia lokalne CLI DevLink, które cyklicznie odpytuje backend o nowe zadania.

Najważniejsza zasada architektury: kod projektu nie trafia na backend. Backend przechowuje konta, urządzenia, projekty, zadania, statusy i historię wyników. Właściwa praca na plikach odbywa się lokalnie na komputerze użytkownika przez `Codex CLI`.

## Części projektu

```text
apps/backend   Django REST Framework, Django ORM, REST API, auth, urządzenia i zadania
apps/mobile    Expo React Native, logowanie, chat workspace, workspace settings i historia
apps/cli       Python CLI, parowanie komputera, polling backendu, uruchamianie Codex CLI
docs           dokumentacja architektury, API, parowania i MVP
contracts      kontrakty API, w tym szkic OpenAPI
```

## Wymagania

- Python 3.11+
- Node.js 20+
- NPM
- Codex CLI zainstalowany i zalogowany lokalnie na komputerze użytkownika

## Backend

```bash
docker compose up -d postgres redis
cd apps/backend
copy .env.example .env
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Lokalna baza developerska działa jako PostgreSQL w Dockerze na porcie `54329`. Backend czyta konfigurację z `apps/backend/.env`. Jeśli plik `.env` nie istnieje, Django wraca do SQLite.

Backend ma Django admin, paginowana liste zadan, filtrowanie przez `django-filter` oraz centralna walidacje przejsc statusow zadan.

Redis z `docker-compose.yml` jest uzywany przez Django Channels do live timeline WebSocketow w chat workspace.

## Mobile

```bash
cd apps/mobile
npm install
npm run start
```

Adres backendu dla aplikacji mobilnej ustawiany jest przez `EXPO_PUBLIC_API_URL`.

## CLI lokalne

```bash
cd apps/cli
python -m venv .venv
.venv\Scripts\activate
pip install -e .
devlink doctor
devlink pair --code ABC123 --name "Laptop"
devlink projects add --path C:\path\to\repo --name "My Project"
devlink connect
```

CLI przechowuje token urządzenia lokalnie. Jeśli systemowy keychain jest dostępny, używa `keyring`; w przeciwnym razie zostawia fallback deweloperski w pliku konfiguracyjnym użytkownika.

## Demo chat workspace

Minimalny przeplyw po Etapie 7:

1. Uruchom backend i mobile.
2. W mobile wygeneruj kod parowania.
3. Na komputerze uruchom:

```bash
devlink pair --code ABC123 --name "Laptop"
devlink projects add --path C:\path\to\repo --name "My Project"
devlink connect
```

4. W mobile otwiera sie glowny ekran chatu `WorkspaceChatScreen`.
5. W panelu workspace wybierz projekt, model, access i opcjonalne skillsy.
6. Napisz wiadomosc jak w Codex/ChatGPT.
7. Lokalne CLI odbierze techniczny task, uruchomi `codex exec --json` w zarejestrowanym repozytorium i odesle eventy do backendu.
8. Timeline chatu pokazuje status pracy, terminal, bledy i finalna odpowiedz Codexa.

## Wzorce projektowe

- Factory Method: `AgentFactory` tworzy właściwy adapter agenta na podstawie `agent_type`.
- Adapter: `CodexAdapter` i `ShellAdapter` udostępniają jeden wspólny interfejs dla różnych agentów CLI.

W MVP działa `CodexAdapter` oraz testowy `ShellAdapter`. `ClaudeAdapter` jest jedynie planem rozbudowy architektury, nie elementem MVP.

### Z1 - historyjki użytkownika

- [Parowanie CLI z aplikacją](historyjki/parowanie_cli.md)
- [Wysyłanie promptu do workspace](historyjki/chat_workspace.md)
- [Terminal projektu w aplikacji mobilnej](historyjki/terminal_workspace.md)

### Z2 - wzorce projektowe

- [Factory Method - opis i uzasadnienie](docs/patterns/factory-method/README.md)
- [Factory Method - diagram PUML](docs/patterns/factory-method/factory-method.puml)
- [Factory Method - diagram SVG](docs/patterns/factory-method/factory-method.svg)
- [Adapter - opis i uzasadnienie](docs/patterns/adapter/README.md)
- [Adapter - diagram PUML](docs/patterns/adapter/adapter.puml)
- [Adapter - diagram SVG](docs/patterns/adapter/adapter.svg)

## Dokumentacja

- [Architektura](docs/architecture.md)
- [API](docs/api.md)
- [Parowanie](docs/pairing.md)
- [MVP](docs/mvp.md)
- [Kolejne etapy](docs/roadmap.md)
- [Lokalna baza danych](docs/database.md)
- [Zakres integracji z Codex CLI](docs/codex-cli-scope.md)
- [Audyt lokalnego Codex CLI](docs/codex-cli-audit.md)
- [Katalog komend Codex CLI](contracts/codex-command-catalog.json)
- [Projekty i workspace'y](docs/workspaces.md)
- [Codex Chat Workspace](docs/chat-workspace.md)
