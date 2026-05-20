# Codex Chat Workspace

Etap 7 zmienia glowny sposob korzystania z DevLink. Uzytkownik nie tworzy juz recznie "taskow" w normalnym flow. Task zostaje technicznym runem agenta, a aplikacja mobilna pokazuje jedna rozmowe z lokalnym Codexem.

## Model UX

Glowny ekran mobile to `WorkspaceChatScreen`:

- gorny pasek pokazuje aktywny komputer, projekt, status CLI i model,
- timeline pokazuje wiadomosci uzytkownika, odpowiedzi Codexa, statusy, terminal, bledy i finalny wynik,
- composer wysyla zwykla wiadomosc do sesji,
- panel ustawien pozwala wybrac projekt, model, profil, sandbox/access, web search i skillsy.

Stare ekrany taskow i historii zostaja jako kompatybilne zaplecze, ale nie sa juz centrum aplikacji.

## Backend

`AgentSession` reprezentuje rozmowe. `Task` reprezentuje pojedynczy run/turn w tej rozmowie. `SessionMessage` zapisuje widoczne wiadomosci:

- `user` - prompt z telefonu,
- `assistant` - finalna odpowiedz po zakonczeniu taska,
- `system` - przyszle komunikaty techniczne.

Timeline sesji laczy `SessionMessage` i `TaskEvent`, zeby mobile moglo renderowac jeden strumien:

```http
GET /api/sessions/{id}/timeline/?after=12
POST /api/sessions/{id}/messages/
PATCH /api/sessions/{id}/settings/
```

Po kazdym `TaskEvent` backend publikuje event na WebSocket:

```text
/ws/sessions/{session_id}/?token=<jwt_access_token>
```

REST polling zostaje fallbackiem.

## CLI

CLI synchronizuje capabilities komputera:

- wersja i status `codex`,
- surowy output `codex debug models`,
- surowy output `codex mcp list`,
- surowy output `codex features list`,
- lokalne skillsy wykryte po plikach `SKILL.md`.

Skills w Etapie 7 sa selektorem/hintem. Mobile wybiera skill id, backend zapisuje je na sesji, a CLI dopina nazwy i opisy wybranych skillsow do promptu jako jawny kontekst. DevLink nie instaluje i nie usuwa skillsow z telefonu w tym etapie.

## Bezpieczenstwo

Dozwolone tryby sandbox w Etapie 7:

```text
read-only
workspace-write
```

`danger-full-access`, bypass sandboxa, instalowanie MCP/pluginow i inne akcje wysokiego ryzyka pozostaja zablokowane do approval flow.
