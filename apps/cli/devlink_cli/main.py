from __future__ import annotations

import asyncio
import platform
from pathlib import Path

import typer

from .api_client import DevLinkApiClient, DevLinkApiError
from .codex_process import collect_capabilities, codex_available, codex_command_preview, codex_login_status, is_git_repository
from .config import DevLinkConfig, clear_config, load_config, save_config, store_device_token
from .daemon import run_daemon

app = typer.Typer(help="DevLink local bridge for Codex CLI.")
projects_app = typer.Typer(help="Manage registered local projects.")
app.add_typer(projects_app, name="projects")


@app.command()
def pair(
    code: str = typer.Option(..., "--code", help="Kod parowania z aplikacji mobilnej."),
    name: str = typer.Option("DevLink Computer", "--name", help="Nazwa komputera."),
    project: Path | None = typer.Option(None, "--project", exists=True, file_okay=False, help="Opcjonalnie: sciezka pierwszego projektu."),
    api_url: str = typer.Option("http://127.0.0.1:8000/api", "--api-url", help="Adres backendu DevLink."),
    force: bool = typer.Option(False, "--force", help="Usun stare dane urzadzenia i sparuj ponownie."),
) -> None:
    """Pair this computer with a DevLink user account."""
    current_config = load_config()
    if current_config.is_paired:
        if not force:
            typer.echo(
                "CLI jest juz sparowane. Jesli token jest stary, uruchom: devlink pair --force --code <KOD> --name \"Laptop\"",
                err=True,
            )
            raise typer.Exit(code=1)
        clear_config()

    config = DevLinkConfig(api_url=api_url)
    client = DevLinkApiClient(config)
    try:
        result = asyncio.run(
            client.pair(
                code=code,
                name=name,
                platform=platform.platform(),
                project_path=str(project) if project else None,
                project_name=project.name if project else None,
            )
        )
    except DevLinkApiError as exc:
        typer.echo(f"Nie udalo sie sparowac komputera: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    device = result["device"]
    store_device_token(device["id"], result["device_token"], config)
    typer.echo(f"Paired device: {device['name']} ({device['id']})")
    if result.get("project_id"):
        typer.echo(f"Registered project: {result['project_id']}")
    else:
        typer.echo("Sparowano samo urzadzenie. Workspaces dodasz przez: devlink projects add --path <SCIEZKA_DO_REPO>")


@app.command()
def connect(
    interval: float = typer.Option(5.0, "--interval", help="Polling interval in seconds."),
    api_url: str | None = typer.Option(None, "--api-url", help="Nadpisz adres backendu DevLink (np. http://192.168.0.17:8000/api)."),
    persist_api_url: bool = typer.Option(False, "--persist-api-url", help="Zapisz --api-url do lokalnego configu."),
) -> None:
    """Run the polling loop and execute tasks assigned to this device."""
    config = load_config()
    if not config.is_paired:
        raise typer.BadParameter("CLI nie jest sparowane. Uruchom devlink pair.")
    if api_url:
        config.api_url = api_url.rstrip("/")
        if persist_api_url:
            save_config(config)
    typer.echo("DevLink CLI starting.")
    typer.echo(f"Backend: {config.api_url}")
    typer.echo(f"Device: {config.device_id}")
    typer.echo("Press Ctrl+C to stop.")
    try:
        asyncio.run(run_daemon(DevLinkApiClient(config), interval_seconds=interval))
    except KeyboardInterrupt:
        typer.echo("Stopped DevLink CLI.")
    except DevLinkApiError as exc:
        if exc.status_code in {401, 403}:
            typer.echo(
                "Backend odrzucil token urzadzenia. Ten token jest stary albo komputer zostal odlaczony.",
                err=True,
            )
            typer.echo(
                "Naprawa: w aplikacji otworz Connect CLI, wygeneruj kod, potem uruchom:",
                err=True,
            )
            typer.echo(
                '  devlink pair --force --code <KOD> --name "Laptop"',
                err=True,
            )
            typer.echo(
                "  devlink projects add --path <SCIEZKA_DO_REPO>",
                err=True,
            )
            typer.echo(
                "  devlink connect",
                err=True,
            )
            raise typer.Exit(code=1) from exc
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def status() -> None:
    """Show local pairing status."""
    config = load_config()
    typer.echo(f"API URL: {config.api_url}")
    typer.echo(f"Device ID: {config.device_id or '-'}")
    typer.echo(f"Device token: {'present' if config.get_device_token() else 'missing'}")
    typer.echo(f"Paired: {'yes' if config.is_paired else 'no'}")
    typer.echo(f"Last known device status: {config.last_device_status or '-'}")
    typer.echo(f"Last heartbeat: {config.last_heartbeat_at or '-'}")


@app.command()
def doctor(project: Path | None = typer.Option(None, "--project", exists=True, file_okay=False)) -> None:
    """Check local prerequisites."""
    config = load_config()
    typer.echo(f"Config path is available. Paired: {'yes' if config.is_paired else 'no'}")
    has_codex = codex_available()
    typer.echo(f"Codex CLI in PATH: {'yes' if has_codex else 'no'}")
    if has_codex:
        typer.echo(f"Codex login status: {codex_login_status()}")
    if project:
        typer.echo(f"Git repository: {'yes' if is_git_repository(str(project)) else 'no'}")
        typer.echo("Codex command preview:")
        typer.echo(" ".join(codex_command_preview(str(project))))


@app.command()
def logout() -> None:
    """Remove local device credentials."""
    clear_config()
    typer.echo("Local DevLink credentials removed.")


@projects_app.command("add")
def add_project(
    path: Path = typer.Option(..., "--path", exists=True, file_okay=False),
    name: str | None = typer.Option(None, "--name"),
    repository_url: str = typer.Option("", "--repository-url"),
    default_model: str = typer.Option("", "--model", help="Default Codex model for this project."),
    default_profile: str = typer.Option("", "--profile", help="Default Codex config profile."),
    default_sandbox: str = typer.Option("workspace-write", "--sandbox", help="Default Codex sandbox."),
    default_approval_policy: str = typer.Option("on-request", "--approval-policy", help="Default approval policy."),
) -> None:
    if not is_git_repository(str(path)):
        raise typer.BadParameter("Projekt musi byc repozytorium Git z plikiem albo katalogiem .git.")
    config = load_config()
    client = DevLinkApiClient(config)
    try:
        result = asyncio.run(
            client.register_project(
                name or path.name,
                str(path),
                repository_url,
                default_model=default_model,
                default_profile=default_profile,
                default_sandbox=default_sandbox,
                default_approval_policy=default_approval_policy,
            )
        )
    except DevLinkApiError as exc:
        message = str(exc)
        if exc.status_code == 400 and "juz zarejestrowany" in message:
            typer.echo("Project already registered for this device. Nothing to do.")
            typer.echo("Run `devlink projects list` to see registered projects, then refresh Workspaces in mobile.")
            return
        typer.echo(message, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Registered project: {result['name']} ({result['id']})")
    try:
        projects = asyncio.run(client.list_projects())
        capabilities = collect_capabilities(projects, probe_usage_limits=True)
        asyncio.run(client.post_capabilities(capabilities))
        typer.echo("Capabilities refreshed.")
    except Exception as exc:
        typer.echo(f"Project registered, but capabilities refresh failed: {exc}", err=True)


@projects_app.command("list")
def list_projects() -> None:
    config = load_config()
    client = DevLinkApiClient(config)
    projects = asyncio.run(client.list_projects())
    for project in projects:
        typer.echo(
            "{id}  {name}  active={active}  sandbox={sandbox}  approval={approval}  path={path}".format(
                id=project["id"],
                name=project["name"],
                active=project["is_active"],
                sandbox=project["default_sandbox"],
                approval=project["default_approval_policy"],
                path=project["local_path"],
            )
        )


@projects_app.command("remove")
def remove_project(project_id: str) -> None:
    config = load_config()
    client = DevLinkApiClient(config)
    asyncio.run(client.remove_project(project_id))
    typer.echo(f"Project deactivated: {project_id}")


if __name__ == "__main__":
    app()
