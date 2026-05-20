# MVP

MVP ma pokazać jeden pełny przepływ: telefon wysyła prompt, komputer odbiera zadanie, lokalny Codex CLI wykonuje pracę, a wynik wraca do aplikacji mobilnej.

## Zakres

- Backend DRF z użytkownikami, JWT, urządzeniami, projektami, zadaniami i eventami.
- Expo React Native z ekranami: logowanie, urządzenia/projekty, szczegóły zadania.
- Python CLI z komendami: `pair`, `connect`, `status`, `doctor`, `logout`.
- Działający `CodexAdapter`.
- Testowy `ShellAdapter` do bezpiecznej diagnostyki.

## Poza MVP

- WebSockety i push notifications.
- GitHub API.
- ClaudeAdapter albo inne agenty.
- Zaawansowane uprawnienia per projekt.
- Deployment produkcyjny.

## Kryterium sukcesu

Użytkownik może sparować komputer, wysłać prompt z telefonu i zobaczyć wynik zadania po wykonaniu przez lokalne CLI.

Po MVP kolejne prace są rozpisane w [roadmap.md](roadmap.md).
