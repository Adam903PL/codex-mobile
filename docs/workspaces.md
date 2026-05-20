# Projekty i workspace'y

Workspace w DevLink to lokalny katalog projektu zarejestrowany przez CLI na konkretnym komputerze. Telefon nigdy nie wysyla dowolnej sciezki do backendu. Telefon wybiera tylko `Project`, ktory wczesniej dodal lokalny komputer.

## Dlaczego to wazne

Codex CLI dziala lokalnie i moze czytac albo modyfikowac pliki w katalogu roboczym. Dlatego katalog musi byc wybrany na komputerze uzytkownika, a nie wpisany zdalnie w telefonie.

Bezpieczny przeplyw:

```text
devlink projects add --path C:\repo
        -> backend zapisuje Project.local_path
mobile wybiera Project.id
        -> backend tworzy Task dla tego Project
CLI odbiera Task
        -> CLI uruchamia Codexa w Project.local_path
```

## Rejestracja projektu

CLI sprawdza lokalnie:

- czy sciezka istnieje,
- czy jest katalogiem,
- czy zawiera `.git` jako katalog albo plik.

Plik `.git` jest dozwolony, bo wystepuje np. w Git worktree i submodule.

## Domyslne ustawienia projektu

Projekt przechowuje ustawienia, ktore beda wykorzystane przy pelnym `codex exec` w Etapie 5:

- `default_model`,
- `default_profile`,
- `default_sandbox`,
- `default_approval_policy`.

W Etapie 4 dozwolone sa tylko bezpieczne wartosci:

```text
default_sandbox: read-only, workspace-write
default_approval_policy: untrusted, on-request
```

Opcje `danger-full-access` i `never` pozostaja zablokowane do approval flow.

## Usuwanie projektu

`devlink projects remove <project_id>` nie usuwa rekordu z bazy. Backend ustawia `is_active=false`.

Dzieki temu:

- historia taskow nadal wskazuje dawny projekt,
- telefon nie pokazuje projektu jako aktywnego,
- backend nie pozwala utworzyc nowych zadan dla nieaktywnego projektu.
