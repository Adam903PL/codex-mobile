from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import time

from .agents.base import AgentCanceled, AgentTask
from .agents.factory import AgentFactory
from .api_client import DevLinkApiClient, DevLinkApiError
from .codex_process import collect_capabilities
from .terminal_bridge import run_terminal_session

CAPABILITIES_SYNC_INTERVAL_SECONDS = 60
IDLE_LOG_INTERVAL_SECONDS = 30


async def run_daemon(client: DevLinkApiClient, interval_seconds: float = 5.0) -> None:
    _log("Connecting bridge...")
    try:
        _log("Refreshing Codex capabilities...")
        await sync_capabilities(client)
        _log("Capabilities synced.")
    except DevLinkApiError as exc:
        if exc.status_code in {401, 403}:
            raise
        _print_transient_api_error(exc, interval_seconds)
        await asyncio.sleep(interval_seconds)
    next_capabilities_sync = time.monotonic() + CAPABILITIES_SYNC_INTERVAL_SECONDS
    next_idle_log = 0.0
    heartbeat_logged = False
    terminal_workers: dict[str, asyncio.Task] = {}
    while True:
        try:
            terminal_workers = {
                terminal_id: worker
                for terminal_id, worker in terminal_workers.items()
                if not worker.done()
            }
            await client.heartbeat(busy=False)
            if not heartbeat_logged:
                _log("Connected. Waiting for mobile tasks.")
                heartbeat_logged = True
            if time.monotonic() >= next_capabilities_sync:
                _log("Refreshing Codex capabilities...")
                await sync_capabilities(client)
                _log("Capabilities synced.")
                next_capabilities_sync = time.monotonic() + CAPABILITIES_SYNC_INTERVAL_SECONDS
            terminal = await client.next_terminal_session()
            if terminal and terminal["id"] not in terminal_workers:
                _log(f"Starting terminal session {terminal['id']}.")
                terminal_workers[terminal["id"]] = asyncio.create_task(run_terminal_session(client, terminal))
            approval = await client.next_approval()
            if approval:
                _log(f"Running approved action {approval.get('command_id') or approval.get('action_type') or approval.get('id')}.")
                await client.heartbeat(busy=True)
                await run_approval(client, approval)
                _log("Approved action finished.")
                await sync_capabilities(client)
                next_capabilities_sync = time.monotonic() + CAPABILITIES_SYNC_INTERVAL_SECONDS
                await client.heartbeat(busy=False)
                continue
            task = await client.next_task()
            if not task:
                if time.monotonic() >= next_idle_log:
                    _log(f"Idle. Polling every {interval_seconds:.1f}s; capabilities every {CAPABILITIES_SYNC_INTERVAL_SECONDS}s.")
                    next_idle_log = time.monotonic() + IDLE_LOG_INTERVAL_SECONDS
                await asyncio.sleep(interval_seconds)
                continue

            _log(f"Claiming task {task['id']} for project {task.get('project_name') or task.get('project_path') or '-'}...")
            await client.heartbeat(busy=True)
            try:
                await client.start_task(task["id"])
            except DevLinkApiError:
                status_payload = await client.task_status(task["id"])
                if status_payload.get("status") == "canceled":
                    await client.heartbeat(busy=False)
                    continue
                raise
            _log("Task started.")
            await client.post_task_event(
                task["id"],
                "agent_event",
                "Bridge claimed task",
                {"kind": "running", "source": "cli", "raw_type": "bridge.task.claimed", "title": "Bridge claimed task"},
            )
            await run_task(client, task)
            _log(f"Task {task['id']} finished.")
            await client.post_task_event(
                task["id"],
                "agent_event",
                "Bridge finished task",
                {"kind": "status", "source": "cli", "raw_type": "bridge.task.finished", "title": "Bridge finished task"},
            )
            await client.heartbeat(busy=False)
        except DevLinkApiError as exc:
            if exc.status_code in {401, 403}:
                raise
            _print_transient_api_error(exc, interval_seconds)
            await asyncio.sleep(interval_seconds)


async def run_task(client: DevLinkApiClient, task_payload: dict) -> None:
    cancel_event = asyncio.Event()
    task = AgentTask(
        id=task_payload["id"],
        prompt=task_payload["prompt"],
        project_path=task_payload["project_path"],
        agent_type=task_payload.get("agent_type", "codex"),
        model=task_payload.get("default_model", ""),
        profile=task_payload.get("default_profile", ""),
        sandbox=task_payload.get("default_sandbox", "workspace-write"),
        approval_policy=task_payload.get("default_approval_policy", "on-request"),
        git_branch=task_payload.get("git_branch") or "",
        add_dirs=task_payload.get("add_dirs") or [],
        model_settings=task_payload.get("model_settings") or {},
        tool_settings=task_payload.get("tool_settings") or {},
        images=task_payload.get("images") or [],
        session_id=task_payload.get("session") or "",
        codex_session_id=task_payload.get("codex_session_id") or "",
        resume_mode=bool(task_payload.get("resume_mode")),
        selected_skills=task_payload.get("selected_skills") or [],
        web_search_enabled=bool(task_payload.get("web_search_enabled")),
        cancel_event=cancel_event,
    )
    adapter = AgentFactory.create(task.agent_type)
    cancel_watcher = asyncio.create_task(watch_task_cancellation(client, task.id, cancel_event))

    final_payload = {"status": "failed", "exit_code": None, "error_code": "NO_FINAL_EVENT"}
    final_message = ""

    try:
        async for event in adapter.run(task):
            if event.event_type == "final":
                final_payload = event.payload
                final_message = event.message
                await client.post_task_event(task.id, event.event_type, event.message, event.payload)
                continue
            await client.post_task_event(task.id, event.event_type, event.message, event.payload)
    except AgentCanceled:
        await _post_task_canceled_event(client, task.id)
        return
    except Exception as exc:
        if cancel_event.is_set():
            return
        try:
            await client.finish_task(
                task.id,
                status="failed",
                error_code="CLI_AGENT_ERROR",
                error_message=str(exc),
            )
        except DevLinkApiError:
            pass
        return
    finally:
        cancel_watcher.cancel()
        await asyncio.gather(cancel_watcher, return_exceptions=True)

    if cancel_event.is_set():
        await _post_task_canceled_event(client, task.id)
        return

    try:
        status_payload = await client.task_status(task.id)
    except DevLinkApiError:
        status_payload = {}
    if status_payload.get("status") == "canceled":
        return

    await client.finish_task(
        task.id,
        status=final_payload.get("status", "failed"),
        final_output=final_message,
        exit_code=final_payload.get("exit_code"),
        error_code=final_payload.get("error_code", ""),
        error_message=final_payload.get("error_message", ""),
    )


async def _post_task_canceled_event(client: DevLinkApiClient, task_id: str) -> None:
    try:
        await client.post_task_event(
            task_id,
            "agent_event",
            "Task canceled by emergency stop",
            {
                "kind": "status",
                "source": "cli",
                "raw_type": "bridge.task.canceled",
                "title": "Task canceled by emergency stop",
                "status": "canceled",
            },
        )
    except DevLinkApiError:
        return


def _print_transient_api_error(exc: DevLinkApiError, interval_seconds: float) -> None:
    print(f"Temporary API error: {exc}. Retrying in {interval_seconds:.1f}s.", file=sys.stderr)


def _log(message: str) -> None:
    print(f"[devlink] {message}", flush=True)


async def watch_task_cancellation(
    client: DevLinkApiClient,
    task_id: str,
    cancel_event: asyncio.Event,
    interval_seconds: float = 2.0,
) -> None:
    while not cancel_event.is_set():
        await asyncio.sleep(interval_seconds)
        try:
            status_payload = await client.task_status(task_id)
        except DevLinkApiError:
            continue
        if status_payload.get("status") == "canceled":
            cancel_event.set()
            return


async def sync_capabilities(client: DevLinkApiClient) -> None:
    try:
        projects = await client.list_projects()
        capabilities = await asyncio.to_thread(collect_capabilities, projects, True)
        await client.post_capabilities(capabilities)
    except DevLinkApiError:
        raise
    except Exception:
        return


async def run_approval(client: DevLinkApiClient, approval: dict) -> None:
    try:
        result = await asyncio.to_thread(execute_approval_action, approval)
    except Exception as exc:
        await client.finish_approval(
            approval["id"],
            status="failed",
            error_message=str(exc),
        )
        return
    await client.finish_approval(
        approval["id"],
        status="succeeded" if result.get("exit_code", 0) == 0 else "failed",
        result_message=result.get("stdout", ""),
        error_message=result.get("stderr", ""),
        stdout=result.get("stdout", ""),
        stderr=result.get("stderr", ""),
        exit_code=result.get("exit_code"),
    )


def execute_approval_action(approval: dict) -> dict:
    action_type = approval.get("command_id") or approval.get("action_type")
    payload = approval.get("arguments") or approval.get("action_payload") or {}
    project_path = approval.get("project_path") or ""
    if action_type == "codex.capabilities.refresh":
        return _ok("Capabilities refresh queued.")
    if action_type == "codex.session.settings.update":
        return _ok("Approved session settings update.")
    if action_type == "git.branch.switch":
        branch = str(payload.get("branch") or "").strip()
        if not branch:
            raise ValueError("Branch is required.")
        result = _run_git(project_path, ["checkout", branch])
        return _ok(f"Switched branch to {branch}.\n{result}".strip())
    if action_type == "git.branch.create":
        branch = str(payload.get("branch") or "").strip()
        base = str(payload.get("base") or "").strip()
        if not branch:
            raise ValueError("Branch is required.")
        args = ["checkout", "-b", branch]
        if base:
            args.append(base)
        result = _run_git(project_path, args)
        return _ok(f"Created and switched branch to {branch}.\n{result}".strip())
    if action_type == "codex.login.status":
        return _run_codex_action(["login", "status"])
    if action_type == "codex.logout":
        return _run_codex_action(["logout"])
    if action_type == "codex.login.device":
        return _run_codex_action(["login", "--device-auth"])
    if action_type == "codex.login.api_key":
        env_name = str(payload.get("api_key_env") or "OPENAI_API_KEY").strip()
        return _run_codex_action(["login", "--with-api-key"], input_text=_env_value(env_name))
    if action_type == "codex.features.list":
        return _run_codex_action(["features", "list"])
    if action_type == "codex.features.enable":
        return _run_codex_action(["features", "enable", _required(payload, "feature")])
    if action_type == "codex.features.disable":
        return _run_codex_action(["features", "disable", _required(payload, "feature")])
    if action_type == "codex.debug.models":
        args = ["debug", "models"]
        if payload.get("bundled"):
            args.append("--bundled")
        return _run_codex_action(args)
    if action_type == "codex.debug.app_server.send_message_v2":
        return _run_codex_action(["debug", "app-server", "send-message-v2", _required(payload, "user_message")])
    if action_type == "codex.version":
        return _run_codex_action(["--version"])
    if action_type == "codex.help":
        command = str(payload.get("command") or "").strip()
        args = [*command.split(), "--help"] if command else ["--help"]
        return _run_codex_action(args)
    if action_type == "codex.mcp.list":
        args = ["mcp", "list"]
        if payload.get("json", True):
            args.append("--json")
        return _run_codex_action(args)
    if action_type == "codex.mcp.get":
        args = ["mcp", "get", _required(payload, "name")]
        if payload.get("json", True):
            args.append("--json")
        return _run_codex_action(args)
    if action_type == "codex.mcp.remove":
        return _run_codex_action(["mcp", "remove", _required(payload, "name")])
    if action_type == "codex.mcp.login":
        args = ["mcp", "login", _required(payload, "name")]
        scopes = str(payload.get("scopes") or "").strip()
        if scopes:
            args.extend(["--scopes", scopes])
        return _run_codex_action(args)
    if action_type == "codex.mcp.logout":
        return _run_codex_action(["mcp", "logout", _required(payload, "name")])
    if action_type == "codex.mcp.add":
        return _run_codex_action(_mcp_add_args(payload))
    if action_type == "codex.plugin.marketplace.add":
        return _run_codex_action(_plugin_marketplace_add_args(payload))
    if action_type == "codex.plugin.marketplace.upgrade":
        name = str(payload.get("name") or "").strip()
        return _run_codex_action(["plugin", "marketplace", "upgrade", *([name] if name else [])])
    if action_type == "codex.plugin.marketplace.remove":
        return _run_codex_action(["plugin", "marketplace", "remove", _required(payload, "name")])
    if action_type == "codex.plugin.list":
        return _ok("Plugin inventory is reported through capabilities refresh.")
    if action_type == "codex.apply":
        return _run_codex_action(["apply", _required(payload, "task_id")], cwd=project_path or None)
    if action_type == "codex.cloud.list":
        args = ["cloud", "list"]
        for key in ("env", "limit", "cursor"):
            value = str(payload.get(key) or "").strip()
            if value:
                args.extend([f"--{key}", value])
        if payload.get("json"):
            args.append("--json")
        return _run_codex_action(args)
    if action_type == "codex.cloud.exec":
        args = ["cloud", "exec", str(payload.get("query") or "")]
        env = str(payload.get("env") or "").strip()
        if env:
            args.extend(["--env", env])
        attempts = str(payload.get("attempts") or "").strip()
        if attempts:
            args.extend(["--attempts", attempts])
        return _run_codex_action(args)
    if action_type == "codex.update":
        return _run_codex_action(["update"])
    if action_type == "codex.completion":
        return _run_codex_action(["completion", str(payload.get("shell") or "powershell")])
    if action_type == "codex.app":
        path = str(payload.get("path") or project_path or ".")
        args = ["app", path]
        download_url = str(payload.get("download_url") or "").strip()
        if download_url:
            args.extend(["--download-url", download_url])
        return _run_codex_action(args)
    if action_type == "codex.app-server":
        args = ["app-server"]
        for key in ("listen", "ws_auth", "ws_token_file", "ws_shared_secret_file", "ws_issuer", "ws_audience"):
            value = str(payload.get(key) or "").strip()
            if value:
                args.extend([f"--{key.replace('_', '-')}", value])
        return _run_codex_action(args)
    if action_type == "codex.remote-control":
        args = ["remote-control"]
        listen = str(payload.get("listen") or "").strip()
        if listen:
            args.extend(["--listen", listen])
        return _run_codex_action(args)
    if action_type == "codex.exec-server":
        args = ["exec-server"]
        listen = str(payload.get("listen") or "").strip()
        if listen:
            args.extend(["--listen", listen])
        return _run_codex_action(args)
    if action_type == "codex.mcp-server":
        return _run_codex_action(["mcp-server"])
    if action_type == "codex.sandbox.run":
        command = payload.get("command")
        if isinstance(command, str):
            command = [command]
        if not isinstance(command, list) or not command:
            raise ValueError("command is required.")
        platform_name = str(payload.get("platform") or "windows")
        args = ["sandbox", platform_name]
        profile = str(payload.get("permissions_profile") or "").strip()
        if profile:
            args.extend(["--permissions-profile", profile])
        cd = str(payload.get("cd") or project_path or "").strip()
        if cd:
            args.extend(["--cd", cd])
        if payload.get("include_managed_config"):
            args.append("--include-managed-config")
        config_values = payload.get("config") or []
        if isinstance(config_values, str):
            config_values = [config_values]
        if isinstance(config_values, list):
            for value in config_values:
                if str(value).strip():
                    args.extend(["--config", str(value)])
        if platform_name == "macos":
            sockets = payload.get("allow_unix_socket") or []
            if isinstance(sockets, str):
                sockets = [sockets]
            if isinstance(sockets, list):
                for socket in sockets:
                    if str(socket).strip():
                        args.extend(["--allow-unix-socket", str(socket)])
            if payload.get("log_denials"):
                args.append("--log-denials")
        args.extend(["--", *[str(part) for part in command]])
        return _run_codex_action(args)
    raise ValueError(f"Unsupported approval action: {action_type}")


def _run_git(project_path: str, args: list[str]) -> str:
    if not project_path:
        raise ValueError("Project path is required.")
    result = subprocess.run(
        ["git", "-C", project_path, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in ((result.stdout or "").strip(), (result.stderr or "").strip()) if part)
    if result.returncode != 0:
        raise RuntimeError(output or "Git command failed.")
    return output


def _run_codex_action(args: list[str], cwd: str | None = None, input_text: str | None = None) -> dict:
    codex_path = shutil.which("codex")
    if not codex_path:
        return {"stdout": "", "stderr": "Codex CLI nie jest dostepny w PATH.", "exit_code": 127}
    result = subprocess.run(
        [codex_path, *args],
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        cwd=cwd or None,
    )
    return {
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
        "exit_code": result.returncode,
    }


def _ok(stdout: str) -> dict:
    return {"stdout": stdout, "stderr": "", "exit_code": 0}


def _required(payload: dict, key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required.")
    return value


def _env_value(name: str) -> str:
    import os

    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} environment variable is required.")
    return value


def _mcp_add_args(payload: dict) -> list[str]:
    args = ["mcp", "add", _required(payload, "name")]
    url = str(payload.get("url") or "").strip()
    if url:
        args.extend(["--url", url])
        bearer = str(payload.get("bearer_token_env_var") or "").strip()
        if bearer:
            args.extend(["--bearer-token-env-var", bearer])
        return args
    env = payload.get("env") or {}
    if isinstance(env, dict):
        for key, value in env.items():
            args.extend(["--env", f"{key}={value}"])
    command = payload.get("command")
    if isinstance(command, str):
        command = [command]
    if not isinstance(command, list) or not command:
        raise ValueError("command or url is required.")
    args.extend(["--", *[str(part) for part in command]])
    return args


def _plugin_marketplace_add_args(payload: dict) -> list[str]:
    args = ["plugin", "marketplace", "add", _required(payload, "source")]
    ref = str(payload.get("ref") or "").strip()
    if ref:
        args.extend(["--ref", ref])
    sparse = payload.get("sparse") or []
    if isinstance(sparse, str):
        sparse = [sparse]
    if isinstance(sparse, list):
        for path in sparse:
            if str(path).strip():
                args.extend(["--sparse", str(path)])
    return args
