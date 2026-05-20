# Kolejne etapy budowy DevLink

Ten dokument opisuje docelowa droge od obecnego szkieletu do pelnej aplikacji, ktora obsluguje funkcje Codex CLI z telefonu. Do zaliczeniowego MVP wystarczy pierwsze 5 etapow. Do pelnego dzialania DevLink planujemy 12 etapow.

## Etap 0: Szkielet projektu i lokalne srodowisko

Status: wykonane.

- Monorepo z backendem DRF, aplikacja Expo i lokalnym CLI.
- PostgreSQL w Dockerze.
- Podstawowe modele Django ORM.
- Minimalny przeplyw taskow.
- Factory Method i Adapter w warstwie agentow.

Kryterium gotowosci: projekt uruchamia backend, mobile, CLI i baze danych lokalnie.

## Etap 1: Backend produkcyjny dla MVP

Status: wykonane w Etapie 1.

Cel: miec stabilne API i pewny model danych.

- Dodac Django admin dla `Device`, `Project`, `Task`, `TaskEvent`, `PairingCode`, `AgentSession`.
- Doprecyzowac przejscia statusow, zeby nie bylo niepoprawnych zmian typu `succeeded -> running`.
- Dodac paginacje, filtrowanie i sortowanie list zadan.
- Rozbudowac testy API o bledy autoryzacji i uprawnien.
- Dodano indeksy pod liste zadan i kolejke CLI.

Kryterium gotowosci: backend bezpiecznie przechowuje uzytkownikow, urzadzenia, projekty, zadania i historie.

## Etap 2: Audyt Codex CLI i mapa funkcji

Status: wykonane w Etapie 2 jako audyt i dokumentacja kontraktu.

Cel: zanim rozbudujemy aplikacje, trzeba dokladnie opisac aktualne dzialanie Codex CLI.

- Przeczytano oficjalne docs OpenAI dla Codex CLI, non-interactive mode, approvals/security, MCP i command line options.
- Spisano aktualny output lokalnego `codex --help` i helpy podkomend w `docs/codex-cli-audit.md`.
- Utrzymujemy `docs/codex-cli-scope.md` jako liste funkcji, flag, ryzyk i statusu implementacji.
- Dodano `contracts/codex-command-catalog.json` jako maszynowy katalog funkcji dla przyszlego backendu i mobile.
- Rozdzielono funkcje na: MVP, pelna aplikacja, funkcje niebezpieczne wymagajace blokad, funkcje eksperymentalne.

Kryterium gotowosci: wiemy, ktore komendy Codex CLI maja byc dostepne w mobile i jak bezpiecznie je wywolac.

## Etap 3: Parowanie i bezpieczenstwo urzadzen

Status: wykonane w Etapie 3.

Cel: telefon moze sterowac tylko zaufanym komputerem.

- Dodano ekran generowania kodu parowania w mobile.
- Dodano wygasanie kodow, blokade ponownego uzycia i uniewaznianie poprzedniego aktywnego kodu.
- Dodano widok szczegolow urzadzenia: status, ostatnie polaczenie, projekty.
- Odlaczanie urzadzenia ustawia status `revoked`.
- CLI konczy prace z jasnym komunikatem po cofnieciu dostepu.

Kryterium gotowosci: po odpieciu urzadzenia nie da sie zdalnie uruchomic zadania na komputerze.

## Etap 4: Projekty i workspace'y

Status: wykonane w Etapie 4.

Cel: telefon wybiera tylko repozytoria zarejestrowane lokalnie przez komputer.

- `devlink projects add/list/remove` dziala z backendowym API.
- Mobile pokazuje projekty pogrupowane po komputerach i ma ekran szczegolow projektu.
- Backend blokuje tworzenie zadan dla cudzych albo nieaktywnych projektow.
- CLI sprawdza, czy katalog projektu istnieje i czy jest repozytorium Git.
- Dodano pola konfiguracyjne projektu: domyslny model, sandbox, approval policy, profil Codex.

Kryterium gotowosci: zadania zawsze uruchamiaja sie w jawnie zatwierdzonym katalogu.

## Etap 5: Pelny przeplyw `codex exec`

Status: wykonane w Etapie 5 jako core MVP.

Cel: najwazniejszy scenariusz aplikacji dziala end-to-end.

- `CodexAdapter` uruchamia `codex exec --cd <project_path> --json --sandbox <sandbox> -`.
- Prompt trafia przez `stdin`, proces dziala bez shella.
- Backend zapisuje eventy JSONL, statusy, output, bledy i exit code.
- Mobile pokazuje aktywne zadanie przez polling i dopina eventy po `sequence`.
- Dziala anulowanie zadania i timeout.

Kryterium gotowosci: uzytkownik wysyla prompt z telefonu, lokalny Codex wykonuje prace, wynik wraca do mobile.

## Etap 6: Historia, sesje i kontynuowanie pracy

Cel: DevLink nie jest jednorazowym formularzem, tylko panelem pracy.

- Lista wszystkich zadan z filtrami po statusie, projekcie i komputerze.
- Szczegoly zadania z eventami, finalnym wynikiem i bledami.
- Model sesji powiazany z Codex session/thread id.
- Obsluga `codex exec resume`, `codex resume` i `codex fork`.
- Mobile pozwala kontynuowac poprzednie zadanie albo stworzyc fork.

Kryterium gotowosci: uzytkownik moze wrocic do starej sesji i kontynuowac prace.

## Etap 7: Codex Chat Workspace

Status: wykonane jako przebudowa glownego UX.

Cel: aplikacja ma dzialac jak mobilny panel Codexa, a nie dashboard taskow.

- `WorkspaceChatScreen` jest glownym ekranem po zalogowaniu.
- `AgentSession` jest rozmowa, `Task` jest technicznym runem.
- Dodano `SessionMessage` dla wiadomosci `user` i `assistant`.
- Timeline laczy wiadomosci, eventy, terminal, bledy i finalne odpowiedzi.
- Dodano Django Channels + Redis i WebSocket `/ws/sessions/{session_id}/`.
- CLI synchronizuje capabilities: wersje Codexa, modele, MCP, features i lokalne skillsy.
- Mobile pozwala zmieniac model, profil, sandbox/access, web search i wybrane skillsy w jednym panelu.

Kryterium gotowosci: uzytkownik pisze do lokalnego Codexa w jednym ekranie chatu i widzi live postep pracy.

## Etap 8: MCP, pluginy i konfiguracja Codexa

Cel: uzytkownik moze zarzadzac narzedziami, ktore Codex widzi lokalnie, oraz kolejnymi komendami Codex CLI.

- Obsluga `codex mcp list/get/add/remove/login/logout`.
- Obsluga `codex plugin marketplace`.
- Widok konfiguracji `~/.codex/config.toml` bez pokazywania sekretow.
- Zarzadzanie opcjami tasku: model, profile, sandbox, approval policy, web search, images, add-dir.
- Dokumentacja zasad bezpieczenstwa dla MCP i pluginow.
- Panel funkcji: `review`, `apply`, `features`, `debug`, `completion`, `update`, `login status`, `logout`.

Kryterium gotowosci: uzytkownik widzi i kontroluje lokalne integracje Codexa.

## Etap 9: Approval flow i bezpieczenstwo pracy agenta

Cel: telefon nie moze przypadkiem dac agentowi zbyt duzych uprawnien.

- Wlasny model `ApprovalRequest` w backendzie.
- CLI pauzuje zadanie, gdy Codex wymaga decyzji.
- Mobile pokazuje prosbe o zatwierdzenie komendy, edycji albo dostepu.
- Domyslny tryb: `workspace-write` i approval `on-request` albo `untrusted`.
- `danger-full-access` i `--dangerously-bypass-approvals-and-sandbox` tylko jako tryb developerski, z blokada i wyraznym ostrzezeniem.

Kryterium gotowosci: ryzykowne akcje wymagaja swiadomej decyzji uzytkownika.

## Etap 10: Streaming realtime

Cel: output Codexa pojawia sie w telefonie szybko i wygodnie.

- Zamienic polling historii na WebSockety albo Server-Sent Events.
- CLI nadal laczy sie wychodzaco do backendu.
- Mobile dostaje eventy `stdout`, `stderr`, `agent_event`, `approval_request`, `final`.
- Backend zachowuje eventy w bazie, nawet jesli mobile bylo offline.

Kryterium gotowosci: aktywne zadanie wyglada w mobile jak zdalny terminal/panel agenta.

## Etap 11: Funkcje zaawansowane Codexa

Cel: obsluzyc rzeczy, ktore nie sa konieczne dla szkolnego MVP, ale naleza do pelnego DevLinka.

- `codex cloud`: lista taskow Codex Cloud i aplikowanie zmian lokalnie, jezeli konto to wspiera.
- `app-server`, `remote-control`, `exec-server`, `mcp-server`: ekran eksperymentalnych uslug lokalnych z bezpiecznymi limitami.
- Obsluga wejsc obrazow przez `--image`.
- Obsluga `--output-schema` dla strukturyzowanych wynikow.
- Tryb `--search` dla zadan wymagajacych web search.

Kryterium gotowosci: funkcje eksperymentalne sa dostepne, ale oddzielone od bezpiecznego MVP.

## Etap 12: Testy, dokumentacja i wdrozenie

Cel: projekt jest gotowy do prezentacji i dalszego rozwoju.

- Testy backendu, CLI i mobile.
- Test integracyjny: mobile -> backend -> CLI -> Codex -> backend -> mobile.
- README z pelnym setupem.
- Diagramy architektury i przeplywu.
- Deployment backendu po HTTPS.
- Instrukcja konfiguracji telefonu poza siecia domowa.

Kryterium gotowosci: aplikacje da sie uruchomic od zera i pokazac pelny scenariusz z prawdziwym Codex CLI.
