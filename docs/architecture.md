# Architektura DevLink

DevLink składa się z trzech głównych części: backendu Django REST Framework, aplikacji mobilnej Expo React Native oraz lokalnego CLI uruchamianego na komputerze użytkownika.

## Sens aplikacji

Normalnie użytkownik musi siedzieć przy komputerze, aby używać `Codex CLI` w terminalu. DevLink pozwala wysłać polecenie z telefonu, na przykład "uruchom testy" albo "napraw błąd w logowaniu". Telefon nie łączy się bezpośrednio z komputerem. Obie strony komunikują się przez backend.

Backend nie uruchamia Codexa i nie pracuje na kodzie projektu. Kod pozostaje na komputerze użytkownika. Lokalny program DevLink CLI pobiera zadania z backendu i dopiero na komputerze uruchamia:

```bash
codex exec --cd <project_path> --json --sandbox workspace-write -
```

Prompt trafia do procesu przez standardowe wejście. Proces jest uruchamiany bez shella.

## Odpowiedzialności

Backend:

- przechowuje użytkowników, urządzenia, projekty, sesje, zadania i historię eventów;
- wystawia REST API dla mobile i CLI;
- uwierzytelnia użytkownika przez JWT;
- uwierzytelnia CLI osobnym tokenem urządzenia;
- nie inicjuje połączeń do komputera użytkownika.

Mobile:

- loguje użytkownika;
- pokazuje listę sparowanych komputerów i projektów;
- wysyła prompt jako zadanie;
- pobiera status i historię wykonania.

CLI lokalne:

- paruje komputer z kontem użytkownika;
- rejestruje lokalne projekty;
- wysyła heartbeat;
- odpytuje backend o zadania;
- uruchamia lokalnego agenta, domyślnie Codex CLI;
- odsyła statusy, output i błędy do backendu.

## Komunikacja

DevLink używa w MVP REST polling. CLI regularnie wykonuje zapytania wychodzące do backendu:

1. `POST /api/cli/heartbeat/`
2. `GET /api/cli/tasks/next/`
3. `POST /api/cli/tasks/{id}/start/`
4. `POST /api/cli/tasks/{id}/events/`
5. `POST /api/cli/tasks/{id}/finish/`

Dzięki temu komputer może znajdować się za NAT-em, a telefon może być w dowolnej sieci.

## Chat workspace

Od Etapu 7 glowny UX mobile to jeden ekran rozmowy z lokalnym Codexem. Uzytkownik nie musi myslec o taskach. Wpisuje wiadomosc, widzi swoj prompt, status pracy, terminal, bledy i finalna odpowiedz.

Technicznie backend nadal tworzy `Task`, ale przypina go do `AgentSession`. `AgentSession` jest rozmowa, a `SessionMessage` przechowuje widoczne wiadomosci `user` i `assistant`.

Realtime dziala przez Django Channels:

```text
mobile WebSocket -> backend Channels -> session group
CLI polling REST -> backend TaskEvent -> broadcast timeline item
```

Kod projektu nadal nie trafia na backend. Backend przechowuje rozmowe, statusy, eventy i output, a lokalne CLI uruchamia Codexa w repozytorium uzytkownika.

## Wzorce projektowe

Factory Method jest użyty w `AgentFactory`, aby tworzyć właściwego agenta na podstawie typu zadania, np. `codex` albo `shell`.

Adapter jest użyty w warstwie agentów CLI. Każde narzędzie lokalne ma inny sposób uruchamiania i inny format outputu, ale DevLink potrzebuje wspólnego formatu eventów. `CodexAdapter` tłumaczy output `codex exec --json` na wspólny model `AgentEvent`, a `ShellAdapter` daje prosty adapter testowy.
