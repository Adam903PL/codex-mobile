# DevLink - overview projektu

Ten dokument opisuje ogolne dzialanie DevLinka: z czego sklada sie aplikacja, jaki ma stack, gdzie trzyma stan, jakie wzorce projektowe sa uzyte i jak plyna dane miedzy telefonem, backendem oraz lokalnym komputerem.

## 1. Co robi DevLink

DevLink pozwala sterowac lokalnym `Codex CLI` z telefonu. Telefon nie wykonuje kodu bezposrednio i nie ma dostepu do plikow projektu. Zamiast tego:

1. Aplikacja mobilna wysyla prompt i ustawienia pracy do backendu.
2. Backend zapisuje zadanie w bazie danych jako `Task`.
3. Lokalny bridge `devlink connect` dzialajacy na komputerze odpytuje backend o nowe zadania.
4. CLI odbiera zadanie, uruchamia lokalnie `codex exec --json` w katalogu projektu i streamuje eventy z powrotem do backendu.
5. Backend zapisuje statusy, logi, finalna odpowiedz i rozglasza timeline do aplikacji mobilnej przez WebSocket.
6. Mobile pokazuje chat, run log, finalna odpowiedz, terminal i workspace'y.

Najwazniejsza zasada: kod projektu zostaje lokalnie na komputerze. Backend przechowuje metadane, historie, statusy i wyniki, ale nie jest miejscem wykonywania pracy na repozytorium.

## 2. Struktura monorepo

```text
apps/backend   API, baza danych, auth, kolejka taskow, WebSocket timeline
apps/cli       lokalny bridge, parowanie urzadzenia, polling, adapter Codex CLI
apps/mobile    aplikacja Expo React Native sterujaca workspace'ami i chatem
contracts      kontrakty API i katalog komend
docs           starsza/dodatkowa dokumentacja techniczna
scripts        skrypty developerskie, np. live logi
script         proste skrypty pomocnicze
```

## 3. Stack technologiczny

### Backend

- `Django 5` jako glowny framework aplikacji serwerowej.
- `Django REST Framework` do REST API.
- `Simple JWT` do logowania uzytkownika z aplikacji mobilnej.
- `Django ORM` jako warstwa dostepu do danych.
- `PostgreSQL` jako docelowa baza developerska z `docker-compose.yml`.
- `SQLite` jako fallback, gdy `.env` nie wymusza Postgresa.
- `Django Channels` + `Daphne` do WebSocketow.
- `Redis` jako channel layer dla realtime timeline.
- `drf-spectacular` do schematu API.
- `django-filter` do filtrowania list, np. taskow.

### Mobile

- `Expo SDK 54`.
- `React Native 0.81`.
- `React 19`.
- `TypeScript`.
- `React Navigation` do ekranow.
- `expo-secure-store` do lokalnych preferencji i tokenow.
- `lucide-react-native` do ikon.
- `react-native-markdown-display` do renderowania odpowiedzi modelu.

### CLI

- Python `3.11+`.
- `Typer` jako CLI framework.
- `httpx` do komunikacji HTTP z backendem.
- `pydantic` do lokalnego configu.
- `keyring` do przechowywania tokenu urzadzenia w systemowym sejfie.
- `platformdirs` do lokalizacji pliku konfiguracyjnego.
- `pywinpty` do obslugi terminala na Windows.
- Zewnetrzne `Codex CLI`, uruchamiane lokalnie jako proces.

### Infrastruktura lokalna

- `docker compose up -d postgres redis` uruchamia Postgresa i Redisa.
- Postgres jest wystawiony lokalnie na `54329`.
- Redis jest wystawiony lokalnie na `63799`.
- Backend zwykle dziala na `0.0.0.0:8000`, zeby telefon mogl wejsc po LAN IP.

## 4. Glowne domeny backendu

### Accounts

Odpowiada za logowanie uzytkownika i tokeny JWT. Mobile loguje sie jako zwykly uzytkownik, a potem wysyla `Authorization: Bearer <token>` do endpointow API.

### Devices

Reprezentuje komputer/laptop, na ktorym dziala lokalne CLI. Najwazniejsze pola:

- `owner` - wlasciciel urzadzenia.
- `name` i `platform` - opis komputera.
- `status` - `online`, `offline`, `busy`, `revoked`.
- `token_hash` - hash tokenu urzadzenia.
- `capabilities` - modele, skille, pliki projektu, stan Codexa, usage limits.
- `last_seen_at` - ostatni heartbeat.

Parowanie odbywa sie przez `PairingCode`: mobile generuje kod, CLI wysyla kod do backendu, backend tworzy `Device` i zwraca token urzadzenia.

### Projects

Projekt to lokalny workspace przypiety do konkretnego urzadzenia. Backend zna sciezke, nazwe i ustawienia domyslne, ale nie przechowuje kodu projektu.

Najwazniejsze pola:

- `device` - urzadzenie, ktore ma dostep do tej sciezki.
- `owner` - wlasciciel.
- `local_path` - lokalna sciezka na komputerze.
- `default_model`, `default_profile`, `default_sandbox`, `default_approval_policy`.
- `is_active`.

Jeden laptop moze miec wiele workspace'ow. Parowanie urzadzenia i dodawanie workspace'ow sa rozdzielone.

### Sessions

`AgentSession` to rozmowa/chatek zwiazany z projektem, urzadzeniem i uzytkownikiem. Trzyma:

- wybrany model, profil, sandbox i approval policy,
- `codex_session_id`, czyli identyfikator watku Codexa do resume,
- wybrane skille,
- ustawienia narzedzi i web search,
- relacje do wiadomosci `SessionMessage`.

`SessionMessage` przechowuje wiadomosci `user`, `assistant` i `system`. Finalna odpowiedz z taska jest zamieniana na wiadomosc asystenta, zeby chat mial normalna historie.

### Tasks

`Task` to jednostka pracy dla lokalnego CLI. Ma statusy:

```text
queued -> claimed -> running -> succeeded
                           -> failed
                           -> canceled
                           -> timed_out
```

`TaskEvent` to eventy w run logu: statusy, stdout, stderr, eventy agenta, final. Kazdy event ma `sequence`, dzieki czemu timeline mozna odtwarzac w kolejnosci.

### Agents

Warstwa pomocnicza dla komend i approvali. Backend ma katalog komend, statusy akcji i endpointy do decyzji typu zatwierdz/odrzuc. To pozwala oddzielic "co user chce wykonac" od faktycznego wykonania lokalnie na komputerze.

### Terminals

Obsluga zdalnego terminala z telefonu. Backend przechowuje sesje terminalowe i eventy, a CLI uruchamia lokalna powloke i odsyla stdout/stderr/status.

## 5. Stan wewnetrzny i zewnetrzny

### Stan zewnetrzny

To stan trwaly albo pochodzacy spoza procesu aplikacji:

- PostgreSQL/SQLite: uzytkownicy, urzadzenia, projekty, sesje, wiadomosci, taski, eventy.
- Redis: tymczasowy channel layer do WebSocketow.
- Systemowy keychain: token urzadzenia w CLI.
- Plik configu CLI: fallback tokenu, `device_id`, `api_url`, ostatni status.
- SecureStore w mobile: preferencje aplikacji, wybrany backend API.
- Lokalne repozytoria uzytkownika: prawdziwy kod projektu, ktorego backend nie przechowuje.
- Proces `codex`: zewnetrzny program, ktory wykonuje prace na plikach.
- Docker: Postgres i Redis w lokalnym srodowisku developerskim.

### Stan wewnetrzny backendu

To stan runtime w procesie Django:

- request/response i serializery DRF,
- transakcje ORM,
- blokady `select_for_update` przy pobieraniu taska,
- walidacja przejsc statusow,
- broadcast do Channels,
- logi developerskie w middleware.

Ten stan znika po restarcie procesu. Trwale dane musza trafic do bazy.

### Stan wewnetrzny mobile

To stan Reacta:

- aktywna sesja,
- aktywny projekt i urzadzenie,
- timeline w pamieci,
- stan inputu, paneli, modalow, filtracji workspace'ow,
- lokalne preferencje po wczytaniu z SecureStore,
- stan WebSocket/pollingu.

Mobile traktuje backend jako zrodlo prawdy. Jesli realtime sie rozjedzie, REST timeline sluzy jako fallback.

### Stan wewnetrzny CLI

To stan procesu `devlink connect`:

- petla pollingowa,
- mapa aktywnych terminali,
- aktualnie wykonywany task,
- `cancel_event`,
- tymczasowe buforowanie stdout/stderr/eventow Codexa,
- wykryte capabilities,
- adapter agenta.

Po zamknieciu CLI ten stan znika, ale backend nadal zna ostatni status taskow i eventy.

## 6. Przeplyw danych: parowanie

1. Mobile tworzy kod parowania przez backend.
2. User uruchamia na laptopie `devlink pair --code <KOD> --name "Laptop"`.
3. CLI wysyla kod, nazwe i platforme do `/api/cli/pair/`.
4. Backend sprawdza `PairingCode`, tworzy `Device`, generuje token i zapisuje tylko hash tokenu.
5. CLI zapisuje token lokalnie w keychain albo config fallback.
6. Od tego momentu CLI uwierzytelnia sie jako urzadzenie przez token urzadzenia, nie przez JWT usera.

## 7. Przeplyw danych: dodawanie workspace'u

1. User uruchamia `devlink projects add --path C:\repo --name "Nazwa"`.
2. CLI sprawdza lokalny katalog i wysyla metadane do backendu.
3. Backend tworzy `Project` przypisany do danego `Device` i `owner`.
4. Backend emituje update workspace'ow.
5. Mobile odswieza bootstrap/workspaces i pokazuje nowy projekt.

## 8. Przeplyw danych: prompt w chacie

1. User wpisuje prompt w mobile.
2. Mobile tworzy/wybiera `AgentSession`.
3. Mobile zapisuje `SessionMessage` usera i tworzy `Task`.
4. Backend ustawia task jako `queued`.
5. CLI w petli `devlink connect` pyta o `/api/cli/tasks/next/`.
6. Backend wybiera najstarszy task dla urzadzenia i przechodzi `queued -> claimed`.
7. CLI wywoluje `/start/`, task przechodzi `claimed -> running`.
8. CLI uruchamia adapter, zwykle `CodexAdapter`.
9. `CodexAdapter` odpala `codex exec --json` w `project_path`.
10. Eventy JSONL z Codexa sa normalizowane do `AgentEvent`.
11. CLI wysyla eventy do `/api/cli/tasks/<id>/events/`.
12. Backend zapisuje `TaskEvent` i broadcastuje timeline przez WebSocket.
13. Mobile pokazuje run log, statusy, komendy, diffy i podglad odpowiedzi.
14. Po koncu CLI wysyla `/finish/`.
15. Backend przechodzi na status terminalny, zapisuje final output i tworzy `SessionMessage` asystenta.

## 9. Przeplyw danych: realtime timeline

Realtime dziala tak:

1. Mobile laczy sie z WebSocketem sesji.
2. Backend po kazdym `TaskEvent` buduje timeline item.
3. Timeline item jest wysylany do grupy Channels dla danej sesji.
4. Mobile scala itemy po `id`, sortuje po czasie/sekwencji i grupuje eventy techniczne w run log.
5. Gdy WebSocket zawiedzie albo event przyjdzie w zlej kolejnosc, mobile moze dociagnac timeline REST-em.

W praktyce timeline ma dwa typy informacji:

- normalne wiadomosci chatu: prompt usera i finalna odpowiedz asystenta,
- techniczne eventy run logu: claimed, running, komendy, reasoning, diffy, stderr, final status.

## 10. Przeplyw danych: terminal

1. Mobile tworzy terminal session.
2. Backend zapisuje sesje terminalowa.
3. CLI odbiera terminal przez polling.
4. CLI uruchamia lokalna powloke.
5. Mobile wysyla komendy do backendu.
6. CLI pobiera komendy, wykonuje lokalnie i odsyla output.
7. Backend zapisuje eventy i pokazuje je w mobile.

Tak jak przy Codexie, wykonywanie dzieje sie lokalnie na komputerze.

## 11. Wzorce projektowe uzyte w projekcie

### Client-server

Mobile i CLI sa klientami backendu. Backend jest centralnym API i zrodlem prawdy dla uzytkownikow, urzadzen, projektow, sesji i taskow.

Dlaczego: telefon i komputer nie musza laczyc sie bezposrednio. Backend posredniczy, zapisuje historie i pozwala na realtime.

### Queue / worker polling

`Task` dziala jak kolejka. Mobile wrzuca zadanie, CLI jako worker pobiera najstarszy `queued` task dla swojego urzadzenia.

Dlaczego: komputer uzytkownika moze byc offline, za NAT-em albo w innej sieci. Polling jest prostszy i stabilniejszy niz wymaganie inbound polaczenia do laptopa.

### State machine

Task ma kontrolowane przejscia statusow w `ALLOWED_STATUS_TRANSITIONS`.

Dlaczego: latwiej uniknac absurdalnych stanow, np. `succeeded -> running` albo `canceled -> succeeded`.

### Adapter

`CodexAdapter` i `ShellAdapter` wystawiaja wspolny interfejs `run(task) -> AgentEvent`.

Dlaczego: backend i daemon nie musza wiedziec, czy prace wykonuje Codex, shell czy w przyszlosci inny agent. Wystarczy, ze adapter emituje eventy w tym samym formacie.

### Factory Method

`AgentFactory.create(agent_type)` wybiera adapter na podstawie typu agenta.

Dlaczego: centralizuje decyzje "jaki agent ma wykonac task" i izoluje reszte kodu od importow konkretnych adapterow.

### Repository / ORM

Django ORM ukrywa szczegoly SQL za modelami `Device`, `Project`, `AgentSession`, `Task`, `TaskEvent`.

Dlaczego: aplikacja operuje na pojeciach domenowych, a nie na recznie skladanych zapytaniach SQL.

### Serializer / DTO

DRF serializery zamieniaja modele na payloady API i waliduja dane wejsciowe.

Dlaczego: mobile i CLI dostaja przewidywalny kontrakt danych, a backend ma jedno miejsce na walidacje formatu.

### Observer / Pub-sub

Django Channels + Redis rozglaszaja eventy timeline do klientow WebSocket.

Dlaczego: mobile widzi postep pracy na zywo bez ciaglego odpytywania REST API.

### Command pattern

Katalog komend i approval actions opisuja operacje jako dane: `command_id`, argumenty, risk level, status.

Dlaczego: mobile moze wyswietlic akcje i poprosic o zatwierdzenie, a CLI wykona ja dopiero po decyzji.

### Strategy

Model, sandbox, approval policy, profile i selected skills sa strategiami wykonania taska.

Dlaczego: ta sama wiadomosc moze byc wykonana roznymi ustawieniami bez zmiany glownego flow.

### Facade / API Client

Mobile ma `api/client.ts`, a CLI ma `DevLinkApiClient`. Oba ukrywaja szczegoly endpointow za funkcjami.

Dlaczego: ekrany i daemon nie musza recznie skladac URL-i i naglowkow za kazdym razem.

### Context / Provider

Mobile uzywa React Context do auth i preferencji.

Dlaczego: token, ustawienia API, jezyk i preferencje sa potrzebne w wielu ekranach, ale nie powinny byc przekazywane recznie przez kazdy komponent.

## 11A. Factory Method - dokladne omowienie

Factory Method jest uzyte w lokalnym CLI do wyboru konkretnego adaptera agenta na podstawie wartosci `agent_type`. Zamiast tworzyc `CodexAdapter` albo `ShellAdapter` bezposrednio w petli bridge'a, kod pyta fabryke: "daj mi adapter dla tego typu zadania".

### Gdzie jest implementacja

- [AgentFactory](apps/cli/devlink_cli/agents/factory.py#L8) - klasa fabryki.
- [AgentFactory.create](apps/cli/devlink_cli/agents/factory.py#L10) - metoda wybierajaca adapter po `agent_type`.
- [Uzycie fabryki w daemonie](apps/cli/devlink_cli/daemon.py#L128) - daemon nie zna szczegolow adaptera, tylko bierze wynik z `AgentFactory.create(...)`.
- [Test wyboru adapterow](apps/cli/tests/test_agents.py#L37) - test potwierdza, ze `codex` daje `CodexAdapter`, a `shell` daje `ShellAdapter`.

### Jak to dziala krok po kroku

1. Backend zwraca CLI zadanie z polem `agent_type`.
2. `run_task` buduje obiekt `AgentTask`.
3. Daemon wywoluje `AgentFactory.create(task.agent_type)`.
4. Fabryka sprawdza typ:
   - `codex` -> tworzy `CodexAdapter`,
   - `shell` -> tworzy `ShellAdapter`,
   - inna wartosc -> rzuca blad `Unsupported agent type`.
5. Daemon dostaje gotowy adapter i uruchamia `adapter.run(task)`.

### Stan zewnetrzny we wzorcu

Factory Method nie przechowuje wlasnego stanu trwalego. Korzysta jednak z danych zewnetrznych:

- `agent_type` zapisany w backendowym `Task`.
- Konfiguracja taska przychodzaca przez API CLI.
- Dostepne klasy adapterow w kodzie CLI.

Ten stan jest "zewnetrzny", bo fabryka go nie tworzy i nie zapisuje. Ona tylko podejmuje decyzje na podstawie przekazanego stringa.

### Stan wewnetrzny we wzorcu

Stan wewnetrzny jest minimalny:

- lokalna decyzja `if agent_type == ...`,
- tymczasowo utworzony obiekt adaptera,
- brak cache, brak singletona, brak globalnej listy instancji.

Fabryka jest dzieki temu prosta i przewidywalna. Kazde wywolanie tworzy nowy adapter dla jednego taska.

### Dlaczego ten wzorzec pasuje tutaj

Bez Factory Method `daemon.py` musialby znac wszystkie adaptery i robic `if agent_type == "codex"` wewnatrz glownej logiki wykonywania taska. To mieszaloby odpowiedzialnosci:

- daemon odpowiada za polling, statusy i komunikacje z backendem,
- fabryka odpowiada za wybor implementacji agenta,
- adapter odpowiada za uruchomienie konkretnego narzedzia.

Dzieki temu dodanie nowego agenta w przyszlosci jest proste: dodaje sie nowy adapter i jedna galaz w `AgentFactory.create`.

## 11B. Adapter - dokladne omowienie

Adapter jest uzyty po stronie CLI. Jego zadaniem jest ukrycie roznic pomiedzy roznymi wykonawcami taskow. Dla daemona kazdy agent wyglada tak samo: ma metode `run(task)` i zwraca strumien `AgentEvent`.

### Gdzie jest implementacja

- [AgentAdapter Protocol](apps/cli/devlink_cli/agents/base.py#L38) - wspolny kontrakt adapterow.
- [AgentTask](apps/cli/devlink_cli/agents/base.py#L9) - ujednolicony opis zadania przekazywany do adaptera.
- [AgentEvent](apps/cli/devlink_cli/agents/base.py#L32) - ujednolicony event zwracany przez adapter.
- [CodexAdapter](apps/cli/devlink_cli/agents/adapters/codex.py#L17) - adapter dla realnego `Codex CLI`.
- [CodexAdapter.run](apps/cli/devlink_cli/agents/adapters/codex.py#L20) - uruchamia proces `codex`, czyta JSON stream i normalizuje eventy.
- [ShellAdapter](apps/cli/devlink_cli/agents/adapters/shell.py#L6) - prosty/testowy adapter shellowy.
- [ShellAdapter.run](apps/cli/devlink_cli/agents/adapters/shell.py#L7) - zwraca testowe eventy bez pelnej integracji z Codexem.
- [Daemon wykonuje adapter](apps/cli/devlink_cli/daemon.py#L135) - daemon robi `async for event in adapter.run(task)`.

### Jak to dziala krok po kroku

1. Daemon odbiera `Task` z backendu.
2. Buduje `AgentTask`, czyli wspolny format danych dla adapterow.
3. Factory wybiera adapter.
4. Daemon uruchamia `adapter.run(task)`.
5. Adapter tlumaczy "swoj swiat" na wspolne `AgentEvent`.
6. Daemon nie analizuje szczegolow Codexa, shell outputu ani JSONL. On tylko wysyla eventy do backendu.

### Co adapter adaptuje

`CodexAdapter` adaptuje zewnetrzny proces `codex exec --json` do formatu DevLinka.

Po stronie Codexa dane przychodza jako:

- JSONL z roznych typow eventow,
- stdout,
- stderr,
- kod wyjscia procesu,
- informacje o plikach, diffach, finalnej odpowiedzi, modelu i usage limits.

Po stronie DevLinka wszystko ma wspolny format:

```text
AgentEvent(event_type, message, payload)
```

To jest sedno Adaptera: zewnetrzny format narzedzia zostaje przetlumaczony na format aplikacji.

### Stan zewnetrzny adaptera

Adapter korzysta z kilku zewnetrznych zrodel stanu:

- lokalny system plikow projektu w `task.project_path`,
- zainstalowany binarny `codex` w `PATH`,
- proces `codex exec --json`,
- aktualny stan Git, np. `git diff --numstat`,
- konfiguracja taska: model, profile, sandbox, skills, images, web search,
- tokeny/logowanie Codexa poza DevLinkiem.

Te rzeczy nie sa wlasnoscia adaptera. Adapter tylko je odczytuje albo uruchamia.

### Stan wewnetrzny adaptera

`CodexAdapter.run` ma stan tymczasowy potrzebny tylko podczas jednego uruchomienia:

- `stdout_lines` i `stderr_lines`,
- `readable_messages`,
- `assistant_messages`,
- `edited_files`,
- `baseline_diff`,
- kolejka async eventow,
- deadline timeoutu,
- informacja o cancelu przez `cancel_event`.

Ten stan znika po zakonczeniu taska. Trwale wyniki trafiaja dopiero do backendu jako `TaskEvent` i `final_output`.

### Dlaczego Adapter jest potrzebny

Bez Adaptera backend i daemon musialyby znac szczegoly kazdego narzedzia: jak Codex streamuje JSON, jak shell zwraca output, jak liczyc diffy, jak wykrywac finalna odpowiedz. To szybko zrobiloby z `daemon.py` wielki plik od wszystkiego.

Adapter daje trzy korzysci:

- izoluje szczegoly `Codex CLI`,
- pozwala testowac agenta przez prostszy `ShellAdapter`,
- pozwala dodac nowego wykonawce bez przebudowy backendu i mobile.

## 11C. Provider / Context - dokladne omowienie

Provider jest uzyty w aplikacji mobilnej jako React Context. To wzorzec przekazywania wspolnego stanu do wielu komponentow bez recznego podawania propsow przez kazdy poziom drzewa.

W DevLinku sa dwa glowne providery:

- `AuthProvider` - stan logowania.
- `PreferencesProvider` - preferencje aplikacji, w tym globalny API URL.

### Gdzie jest implementacja

- [AuthContext createContext](apps/mobile/src/auth/AuthContext.tsx#L12) - utworzenie kontekstu auth.
- [AuthProvider](apps/mobile/src/auth/AuthContext.tsx#L14) - provider stanu logowania.
- [AuthProvider laduje token](apps/mobile/src/auth/AuthContext.tsx#L19) - odczyt tokenu z `SecureStore`.
- [AuthProvider value](apps/mobile/src/auth/AuthContext.tsx#L24) - obiekt udostepniany komponentom.
- [AuthProvider zapisuje tokeny](apps/mobile/src/auth/AuthContext.tsx#L30) - zapis access/refresh tokenu.
- [useAuth](apps/mobile/src/auth/AuthContext.tsx#L46) - hook do pobierania auth state.
- [PreferencesContext createContext](apps/mobile/src/preferences/PreferencesContext.tsx#L140) - utworzenie kontekstu preferencji.
- [PreferencesProvider](apps/mobile/src/preferences/PreferencesContext.tsx#L159) - provider preferencji.
- [PreferencesProvider laduje preferencje](apps/mobile/src/preferences/PreferencesContext.tsx#L164) - odczyt z `SecureStore`.
- [setApiUrlOverride](apps/mobile/src/api/client.ts#L22) - globalne ustawienie API URL dla klienta API.
- [PreferencesProvider value](apps/mobile/src/preferences/PreferencesContext.tsx#L177) - obiekt udostepniany ekranom.
- [usePreferences](apps/mobile/src/preferences/PreferencesContext.tsx#L197) - hook do preferencji.
- [Provider nesting w App](apps/mobile/App.tsx#L24) - `PreferencesProvider` opakowuje `AuthProvider`.
- [Uzycie providerow w WorkspaceChatScreen](apps/mobile/src/screens/WorkspaceChatScreen.tsx#L151) - ekran pobiera token i preferencje przez hooki.

### Jak to dziala krok po kroku

1. `App.tsx` opakowuje cala aplikacje w `PreferencesProvider` i `AuthProvider`.
2. Provider przy starcie czyta dane z `SecureStore`.
3. Provider trzyma dane w `useState`.
4. Provider buduje obiekt `value` w `useMemo`.
5. Komponenty wywoluja `useAuth()` albo `usePreferences()`.
6. Komponent dostaje stan i akcje, np. `accessToken`, `signIn`, `signOut`, `preferences`, `updatePreferences`.
7. Gdy stan sie zmienia, React odswieza komponenty, ktore korzystaja z danego kontekstu.

### Stan zewnetrzny providera

Provider czyta i zapisuje stan trwaly poza Reactem:

- `SecureStore` dla tokenow auth,
- `SecureStore` dla preferencji,
- API URL w `api/client.ts`,
- token JWT otrzymany z backendu,
- ustawienia backendu wpisane przez usera.

To jest stan zewnetrzny, bo istnieje poza aktualnym renderem Reacta i moze przetrwac restart aplikacji.

### Stan wewnetrzny providera

Provider ma stan w pamieci Reacta:

- `accessToken`,
- `isLoading`,
- `preferences`,
- funkcje `signIn`, `signOut`, `updatePreferences`,
- memoizowany obiekt `value`.

Ten stan jest szybki i wygodny dla UI, ale po restarcie aplikacji musi byc odtworzony z `SecureStore`.

### Dlaczego Provider jest potrzebny

Bez Providerow kazdy ekran musialby osobno:

- czytac token z `SecureStore`,
- trzymac wlasny stan logowania,
- wiedziec, jaki jest aktualny API URL,
- przekazywac `accessToken` przez propsy do kolejnych komponentow.

To powodowaloby duplikacje i latwe rozjechanie stanu. Provider daje jedno miejsce prawdy w aplikacji mobilnej.

### Relacja Providerow z klientem API

`PreferencesProvider` ma dodatkowa role: po wczytaniu preferencji wywoluje `setApiUrlOverride`. Dzieki temu funkcje w [api/client.ts](apps/mobile/src/api/client.ts#L399) korzystaja z aktualnego backendu bez przekazywania URL-a do kazdego requestu.

To jest mieszanka Provider + Facade:

- Provider trzyma decyzje usera o URL-u.
- `api/client.ts` ukrywa szczegoly requestow.
- Ekrany wolaja funkcje typu `fetchWorkspaceBootstrap`, `sendSessionMessage`, `fetchSessionTimeline`, a nie recznie `fetch(...)`.

## 11D. Porownanie stanu dla trzech wzorcow

| Wzorzec | Stan wewnetrzny | Stan zewnetrzny | Co daje |
| --- | --- | --- | --- |
| Factory Method | lokalna decyzja wyboru klasy, nowa instancja adaptera | `agent_type` z taska, dostepne klasy adapterow | rozdziela wybor agenta od wykonania taska |
| Adapter | bufory eventow, stdout/stderr, lista edytowanych plikow, timeout | proces `codex`, Git, system plikow, config taska | tlumaczy obcy format narzedzia na format DevLinka |
| Provider | React state, memoizowane value, funkcje update | SecureStore, JWT, API URL, preferencje usera | udostepnia wspolny stan ekranom bez prop drillingu |

## 11E. Krotki przyklad calego laczenia wzorcow

Gdy user wysyla prompt:

1. `WorkspaceChatScreen` bierze token z [useAuth](apps/mobile/src/auth/AuthContext.tsx#L46) i preferencje z [usePreferences](apps/mobile/src/preferences/PreferencesContext.tsx#L197).
2. Mobile wysyla request przez [sendSessionMessage](apps/mobile/src/api/client.ts#L648).
3. Backend tworzy `Task`.
4. CLI odbiera task i buduje [AgentTask](apps/cli/devlink_cli/daemon.py#L107).
5. CLI wybiera adapter przez [AgentFactory.create](apps/cli/devlink_cli/daemon.py#L128).
6. Wybrany adapter wykonuje [adapter.run](apps/cli/devlink_cli/daemon.py#L135).
7. `CodexAdapter` tlumaczy eventy Codexa na `AgentEvent`.
8. Backend zapisuje eventy jako `TaskEvent`.
9. Mobile odbiera timeline i renderuje chat.

W jednym przeplywie dzialaja wiec naraz:

- Provider - daje ekranowi token, preferencje i API URL.
- Factory Method - wybiera, jaki agent wykona zadanie.
- Adapter - ukrywa szczegoly wykonania przez `Codex CLI`.

## 12. Dlaczego architektura jest taka, a nie prostsza

Najprostszy wariant wygladalby tak: telefon laczy sie prosto z laptopem i odpala komendy. DevLink robi inaczej, bo:

- telefon i laptop czesto sa w roznych sieciach,
- laptop moze byc za NAT-em albo firewallem,
- backend moze przechowac historie rozmow i taskow,
- backend moze walidowac uprawnienia,
- CLI moze dzialac jako worker i sam odbierac zadania,
- kod projektu zostaje lokalnie,
- realtime timeline nadal dziala przez WebSocket z backendu.

W praktyce backend jest "koordynatorem", CLI jest "wykonawca", a mobile jest "pilotem".

## 13. Bezpieczenstwo i granice odpowiedzialnosci

- Mobile loguje sie JWT usera.
- CLI loguje sie tokenem urzadzenia.
- Backend trzyma hash tokenu urzadzenia, nie token jawny.
- Projekty sa filtrowane po `owner`.
- Taski sa przypisane do konkretnego `device` i `project`.
- CLI wykonuje prace tylko w lokalnym `project_path`.
- Sandbox i approval policy sa czescia ustawien projektu/sesji.
- Backend nie powinien przechowywac zawartosci plikow repozytorium, tylko metadane i eventy.

## 14. Najwazniejsze encje i relacje

```text
User
  -> Device
      -> Project
          -> AgentSession
              -> SessionMessage
              -> Task
                  -> TaskEvent
      -> TerminalSession
```

Praktycznie:

- user moze miec wiele urzadzen,
- urzadzenie moze miec wiele projektow,
- projekt moze miec wiele sesji,
- sesja moze miec wiele wiadomosci i taskow,
- task ma wiele eventow,
- final taska tworzy wiadomosc asystenta.

## 15. Typowy tryb pracy developerski

1. Uruchom infrastrukture:

```powershell
docker compose up -d postgres redis
```

2. Uruchom backend:

```powershell
cd apps\backend
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

3. Uruchom mobile:

```powershell
cd apps\mobile
npm run start
```

4. Sparuj CLI:

```powershell
devlink pair --code <KOD> --name "Laptop" --api-url http://192.168.0.238:8000/api
```

5. Dodaj workspace:

```powershell
devlink projects add --path C:\path\to\repo --name "My Project"
```

6. Uruchom bridge:

```powershell
devlink connect --api-url http://192.168.0.238:8000/api
```

## 16. Najczestsze problemy

### Backend startuje, ale potem pada

Najczesciej Postgres albo Redis nie dziala. Jesli widac `connection timeout expired`, Django nie moze polaczyc sie z baza.

### Telefon nie widzi backendu

Trzeba sprawdzic:

- czy backend slucha na `0.0.0.0:8000`,
- czy IP w mobile jest aktualne,
- czy Windows Firewall wpuszcza port `8000`,
- czy telefon i komputer sa w tej samej sieci.

### CLI ma zly backend

Mozna podac backend bezposrednio:

```powershell
devlink connect --api-url http://192.168.0.238:8000/api
```

### Workspace nie pojawia sie w mobile

Najczestsze powody:

- CLI sparowane z innym userem niz mobile,
- projekt dodany do innego urzadzenia,
- mobile nie odswiezylo bootstrapu,
- `devlink connect` nie dziala albo nie zsynchronizowal capabilities.

### Run log wyglada dziwnie

Run log sklada eventy z Codex JSON streamu, stderr, statusow taska i eventow bridge'a. To techniczny podglad pracy, a normalna odpowiedzia chatu powinna byc finalna wiadomosc asystenta.

## 17. Najwazniejsze pliki

```text
apps/backend/devlink_backend/settings.py        konfiguracja Django, DB, Channels, logging
apps/backend/tasks/models.py                    Task i TaskEvent
apps/backend/tasks/services.py                  state machine taskow i broadcast timeline
apps/backend/tasks/views.py                     endpointy taskow dla mobile i CLI
apps/backend/sessions/models.py                 AgentSession i SessionMessage
apps/backend/sessions/services.py               timeline itemy i assistant message po tasku
apps/backend/devices/models.py                  Device i PairingCode
apps/backend/projects/models.py                 Project/workspace
apps/cli/devlink_cli/main.py                    komendy devlink pair/connect/projects
apps/cli/devlink_cli/daemon.py                  petla bridge'a
apps/cli/devlink_cli/api_client.py              klient backendu dla CLI
apps/cli/devlink_cli/agents/adapters/codex.py   integracja z Codex CLI
apps/mobile/src/api/client.ts                   klient API mobile
apps/mobile/src/preferences/PreferencesContext.tsx preferencje i API URL
apps/mobile/src/screens/WorkspaceChatScreen.tsx glowny chat workspace
docker-compose.yml                              Postgres i Redis
```

## 18. Mentalny model aplikacji

DevLink mozna rozumiec jako trzy osobne procesy:

- Mobile: interfejs, ktory wysyla intencje usera.
- Backend: koordynator, ktory zapisuje stan i rozglasza zmiany.
- CLI: lokalny worker, ktory wykonuje prace na prawdziwym repozytorium.

To rozdzielenie jest najwazniejsze dla calej architektury. Jesli cos sie psuje, warto najpierw ustalic, w ktorej czesci jest problem:

- mobile nie wyslalo requestu,
- backend nie zapisal taska,
- CLI nie odebralo taska,
- Codex nie wykonal pracy,
- backend nie rozglosil timeline,
- mobile zle posortowalo lub zgrupowalo timeline.
