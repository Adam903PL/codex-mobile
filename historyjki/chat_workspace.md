# Historyjka uzytkownika: wysylanie promptu do workspace

## User Story

Jako uzytkownik chce wyslac prompt z aplikacji mobilnej do wybranego workspace, aby lokalny Codex CLI wykonal zadanie w odpowiednim projekcie i zwrocil wynik w rozmowie.

## Kryteria akceptacji (AC)

- AC1: Uzytkownik moze wybrac projekt/workspace w aplikacji mobilnej.
- AC2: Uzytkownik moze wpisac wiadomosc w ekranie chatu i wyslac ja do backendu.
- AC3: Backend tworzy zadanie Task przypisane do projektu, sesji i urzadzenia.
- AC4: CLI pobiera zadanie przez devlink connect i uruchamia odpowiedniego agenta.
- AC5: Aplikacja pokazuje postep pracy w timeline, np. statusy, komendy i logi.
- AC6: Po zakonczeniu zadania finalna odpowiedz asystenta pojawia sie jako normalna wiadomosc w czacie.
- AC7: Gdy wystapi blad, uzytkownik widzi czytelny komunikat zamiast pustego ekranu.

## Powod biznesowy

To glowny przeplyw aplikacji: telefon jest pilotem, backend koordynuje zadania, a komputer lokalnie wykonuje prace na plikach projektu.

