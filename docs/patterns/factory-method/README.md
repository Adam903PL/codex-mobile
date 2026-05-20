# Wzorzec kreacyjny: Factory Method

## Wybrany wzorzec

Factory Method zostal zastosowany w aplikacji CLI do tworzenia odpowiedniego adaptera agenta na podstawie pola `agent_type`.

Implementacja:

- `apps/cli/devlink_cli/agents/factory.py`
- `apps/cli/devlink_cli/agents/adapters/codex.py`
- `apps/cli/devlink_cli/agents/adapters/shell.py`
- `apps/cli/devlink_cli/daemon.py`

Diagram:

- `factory-method.puml`
- `factory-method.svg`

## Uzasadnienie wyboru wzorca

DevLink moze wykonywac zadania przez rozne typy agentow. Obecnie najwazniejszy jest `CodexAdapter`, ale w projekcie istnieje tez prosty `ShellAdapter`, a architektura pozwala dodac kolejne adaptery bez przebudowy glownej petli CLI.

Factory Method pasuje tutaj, poniewaz decyzja o tym, jaki obiekt ma zostac utworzony, zalezy od danych przychodzacych z backendu. Daemon nie powinien znac szczegolow tworzenia kazdej implementacji agenta.

## Problem projektowy rozwiazywany przez wzorzec

Bez Factory Method kod w `daemon.py` musialby sam sprawdzac typ agenta i tworzyc konkretne klasy:

```text
if agent_type == "codex":
    adapter = CodexAdapter()
elif agent_type == "shell":
    adapter = ShellAdapter()
```

Taki kod miesza dwie odpowiedzialnosci:

- daemon odpowiada za polling backendu i obsluge cyklu zycia taska,
- fabryka odpowiada za wybor konkretnej klasy agenta.

Factory Method wydziela decyzje tworzenia obiektu do jednego miejsca.

## Sposob wykorzystania w aplikacji

1. Backend tworzy zadanie `Task` z polem `agent_type`.
2. CLI pobiera zadanie w `run_daemon`.
3. `run_task` buduje obiekt `AgentTask`.
4. Daemon wywoluje `AgentFactory.create(task.agent_type)`.
5. Fabryka zwraca obiekt zgodny z interfejsem `AgentAdapter`.
6. Daemon uruchamia `adapter.run(task)` bez znajomosci szczegolow konkretnego adaptera.

## Stan wewnetrzny i zewnetrzny

Stan zewnetrzny:

- wartosc `agent_type` z backendowego taska,
- dostepne klasy adapterow w kodzie CLI,
- konfiguracja zadania pobrana z API.

Stan wewnetrzny:

- prosta decyzja wyboru w metodzie `create`,
- nowa instancja adaptera utworzona dla danego taska.

Fabryka nie zapisuje trwalego stanu, nie trzyma cache i nie laczy sie z backendiem. Jej rola jest ograniczona do wyboru i utworzenia obiektu.
