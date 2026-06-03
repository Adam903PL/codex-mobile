# Historyjka uzytkownika: parowanie CLI z aplikacja

## User Story

Jako uzytkownik aplikacji DevLink chce sparowac moj komputer z aplikacja mobilna, aby telefon mogl wysylac zadania do lokalnego CLI bez recznego kopiowania tokenow i konfigracji.

## Kryteria akceptacji (AC)

- AC1: Uzytkownik moze wygenerowac kod parowania w aplikacji mobilnej.
- AC2: Uzytkownik moze uruchomic w terminalu komende `devlink pair --code <KOD> --name <NAZWA>`.
- AC3: Po poprawnym sparowaniu backend zapisuje urzadzenie przypisane do aktualnego knota.
- AC4: CLI zapisuje token urzadzenia lokalnie i moze pozniej uzyc go przy `devlink connect`.
- AC5: Gdy kod jest niepoprawny albo wygasl, aplikacja/CLI pokazuje czytelny komunikat bledu.
- AC6: Sparowane urzadzenie jest widoczne w aplikacji mobilnej na liscie urzadzen.

## Powod biznesowy

Parowanie jest potrzebne, bo DevLink laczy telefon z lokalnym komputerem. Bez tego backend nie wie, ktore CLI moze odbierac zadania danego uzytkonika.
