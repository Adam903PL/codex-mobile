# API DevLink

Backend wystawia REST API pod prefiksem `/api/`.

## Auth uzytkownika

```http
POST /api/auth/register/
POST /api/auth/login/
POST /api/auth/refresh/
GET  /api/me/
```

Mobile uzywa tokenu JWT:

```http
Authorization: Bearer <access_token>
```

CLI po sparowaniu uzywa osobnego tokenu urzadzenia:

```http
Authorization: Device <device_token>
```

## Parowanie

```http
POST /api/pairing-codes/
POST /api/cli/pair/
```

`POST /api/pairing-codes/` tworzy krotki kod wazny przez kilka minut. Uzytkownik wpisuje go w lokalnym CLI:

```bash
devlink pair --code ABC123 --project C:\repo
```

Request:

```json
{}
```

Response:

```json
{
  "code": "ABC123",
  "expires_at": "2026-05-15T10:20:00Z",
  "created_at": "2026-05-15T10:10:00Z"
}
```

Kod jest jednorazowy, wazny 10 minut i uniewaznia poprzedni aktywny kod tego samego uzytkownika.

`POST /api/cli/pair/`:

```json
{
  "code": "ABC123",
  "name": "Laptop",
  "platform": "Windows",
  "project_path": "C:\\repo",
  "project_name": "Repo"
}
```

Response:

```json
{
  "device": {
    "id": "...",
    "name": "Laptop",
    "platform": "Windows",
    "status": "online",
    "last_seen_at": "2026-05-15T10:10:30Z",
    "project_count": 1,
    "created_at": "2026-05-15T10:10:30Z",
    "updated_at": "2026-05-15T10:10:30Z"
  },
  "device_token": "returned-only-once",
  "project_id": "..."
}
```

## Urzadzenia i projekty

```http
GET    /api/devices/
GET    /api/devices/{id}/
GET    /api/devices/{id}/capabilities/
PATCH  /api/devices/{id}/
DELETE /api/devices/{id}/

POST   /api/cli/capabilities/

GET   /api/projects/
GET   /api/projects/{id}/
PATCH /api/projects/{id}/

GET    /api/cli/projects/
POST   /api/cli/projects/
GET    /api/cli/projects/{id}/
PATCH  /api/cli/projects/{id}/
DELETE /api/cli/projects/{id}/
```

Telefon wybiera tylko projekty zarejestrowane wczesniej przez lokalne CLI. Listy urzadzen i projektow pozostaja niepaginowane w Etapie 1, zeby nie zrywac istniejacego kontraktu mobile/CLI.

`GET /api/devices/{id}/` zwraca szczegoly komputera i aktywne projekty:

```json
{
  "id": "...",
  "name": "Laptop",
  "platform": "Windows",
  "status": "online",
  "last_seen_at": "2026-05-15T10:12:00Z",
  "project_count": 1,
  "created_at": "2026-05-15T10:10:30Z",
  "updated_at": "2026-05-15T10:12:00Z",
  "projects": [
    {
      "id": "...",
      "name": "Repo",
      "local_path": "C:\\repo",
      "repository_url": "",
      "default_model": "",
      "default_profile": "",
      "default_sandbox": "workspace-write",
      "default_approval_policy": "on-request",
      "is_active": true
    }
  ]
}
```

`PATCH /api/devices/{id}/` pozwala zmienic bezpieczne pola uzytkownika, przede wszystkim `name`.

`DELETE /api/devices/{id}/` nie usuwa rekordu z bazy. Ustawia `status=revoked`. Od tego momentu lokalne CLI z dawnym tokenem urzadzenia nie moze wykonac heartbeat, pobrac taska ani dodac projektu.

Projekt zawiera lokalna sciezke oraz bezpieczne domyslne ustawienia Codexa:

```json
{
  "id": "...",
  "device": "...",
  "device_name": "Laptop",
  "device_status": "online",
  "name": "Repo",
  "local_path": "C:\\repo",
  "repository_url": "",
  "default_model": "",
  "default_profile": "",
  "default_sandbox": "workspace-write",
  "default_approval_policy": "on-request",
  "is_active": true,
  "created_at": "2026-05-15T10:10:30Z",
  "updated_at": "2026-05-15T10:12:00Z"
}
```

Mobile moze zmienic tylko nazwe i bezpieczne ustawienia projektu. Nie moze zmieniac `local_path`.

W Etapie 4 API akceptuje tylko:

```text
default_sandbox: read-only, workspace-write
default_approval_policy: untrusted, on-request
```

`danger-full-access` i `never` sa zablokowane do approval flow.

`DELETE /api/cli/projects/{id}/` nie usuwa projektu fizycznie. Ustawia `is_active=false`, dzieki czemu telefon nie moze juz tworzyc dla niego nowych taskow.

## Chat workspace

Etap 7 dodaje API rozmowy. `AgentSession` jest rozmowa, `Task` jest technicznym runem, a `SessionMessage` jest widoczna wiadomoscia w timeline.

```http
GET   /api/workspace/bootstrap/
GET   /api/sessions/{id}/timeline/?after=<sequence>
POST  /api/sessions/{id}/messages/
PATCH /api/sessions/{id}/settings/
GET   /api/devices/{id}/capabilities/
POST  /api/cli/capabilities/
```

`POST /api/sessions/{id}/messages/` tworzy `SessionMessage(user)` i `Task(queued)`:

```json
{
  "content": "napraw blad logowania",
  "settings_overrides": {
    "model": "gpt-5.3-codex",
    "sandbox": "workspace-write",
    "web_search_enabled": false
  },
  "selected_skill_ids": ["react-patterns"]
}
```

`GET /api/sessions/{id}/timeline/` zwraca jeden strumien do renderowania chatu:

```json
[
  {
    "kind": "user_message",
    "content": "uruchom testy",
    "task_id": "...",
    "sequence": 1,
    "payload": {},
    "created_at": "2026-05-15T10:10:30Z"
  },
  {
    "kind": "terminal",
    "content": "pytest ok",
    "task_id": "...",
    "sequence": 2,
    "payload": {"line": "pytest ok"},
    "created_at": "2026-05-15T10:10:31Z"
  }
]
```

Realtime:

```text
ws://<backend>/ws/sessions/{session_id}/?token=<jwt_access_token>
```

REST polling przez `timeline/?after=` zostaje fallbackiem.

`POST /api/cli/capabilities/` zapisuje mozliwosci lokalnego CLI: wersje Codexa, modele, MCP, features i lokalne skillsy. Skills sa w Etapie 7 tylko hintami wybieranymi dla sesji. Instalowanie/usuwanie skillsow, MCP i pluginow zostaje na dalsze etapy.

## Zadania mobile

```http
POST /api/tasks/
GET  /api/tasks/
GET  /api/tasks/{id}/
POST /api/tasks/{id}/cancel/
GET  /api/tasks/{id}/events/
```

`GET /api/tasks/` jest paginowane:

```json
{
  "count": 42,
  "next": "http://127.0.0.1:8001/api/tasks/?page=2",
  "previous": null,
  "results": []
}
```

Dostepne parametry filtrowania i sortowania:

```http
GET /api/tasks/?status=running
GET /api/tasks/?agent_type=codex
GET /api/tasks/?device=<device_uuid>
GET /api/tasks/?project=<project_uuid>
GET /api/tasks/?created_after=2026-05-15T08:00:00Z
GET /api/tasks/?created_before=2026-05-15T12:00:00Z
GET /api/tasks/?ordering=-created_at
GET /api/tasks/?ordering=updated_at
GET /api/tasks/?ordering=status
```

Kazdy uzytkownik widzi tylko swoje zadania, nawet jesli poda identyfikator cudzego projektu albo urzadzenia.

`GET /api/tasks/{id}/events/` pozostaje niepaginowane i wspiera `after`:

```http
GET /api/tasks/{id}/events/?after=12
```

Mobile uzywa tego jako prostego pseudo-live pollingu. Ekran aktywnego zadania pobiera najpierw task, potem tylko nowe eventy po ostatnim znanym `sequence`.

`POST /api/tasks/{id}/cancel/` dziala dla statusow:

```text
queued
claimed
running
```

Po statusie terminalnym anulowanie zwraca blad `400`.

## Zadania CLI

```http
POST /api/cli/heartbeat/
GET  /api/cli/tasks/next/
GET  /api/cli/tasks/{id}/
POST /api/cli/tasks/{id}/start/
POST /api/cli/tasks/{id}/events/
POST /api/cli/tasks/{id}/finish/
```

Backend nie inicjuje polaczenia do komputera. Lokalne CLI samo odpytuje backend o zadania dla sparowanego urzadzenia.

`GET /api/cli/tasks/next/` zwraca task wraz z lokalna sciezka projektu i ustawieniami Codexa:

```json
{
  "id": "...",
  "prompt": "napraw blad logowania",
  "agent_type": "codex",
  "project": "...",
  "project_path": "C:\\repo",
  "status": "claimed",
  "created_at": "2026-05-15T10:10:30Z",
  "default_model": "",
  "default_profile": "",
  "default_sandbox": "workspace-write",
  "default_approval_policy": "on-request",
  "selected_skills": [],
  "web_search_enabled": false
}
```

`GET /api/cli/tasks/{id}/` zwraca minimalny status taska dla CLI:

```json
{
  "id": "...",
  "status": "running",
  "updated_at": "2026-05-15T10:12:00Z"
}
```

CLI uzywa tego endpointu do wykrywania anulowania taska przez mobile.

## Status machine zadan

Dozwolone przejscia:

```text
queued -> claimed
queued -> canceled
claimed -> running
claimed -> canceled
running -> succeeded
running -> failed
running -> timed_out
running -> canceled
```

Statusy koncowe:

```text
succeeded
failed
canceled
timed_out
```

Po statusie koncowym zadanie nie moze wrocic do pracy. Przyklad niedozwolonego przejscia:

```text
succeeded -> running
failed -> running
canceled -> succeeded
```

Kazda zmiana statusu tworzy `TaskEvent` typu `status`. Zakonczenie zadania tworzy dodatkowo `TaskEvent` typu `final`.

## Format bledow

API zwraca jednolity format bledow:

```json
{
  "code": "INVALID",
  "message": "Wystapil blad.",
  "details": {
    "status": ["Invalid task status transition: succeeded -> running."]
  },
  "request_id": "..."
}
```
