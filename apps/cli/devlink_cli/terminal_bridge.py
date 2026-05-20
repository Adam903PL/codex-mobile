from __future__ import annotations

import asyncio
import platform
import shutil
import subprocess
from typing import Any

from .api_client import DevLinkApiClient, DevLinkApiError


async def run_terminal_session(client: DevLinkApiClient, payload: dict[str, Any]) -> None:
    terminal_id = payload["id"]
    cwd = payload.get("cwd") or payload.get("project_path") or None
    cols = int(payload.get("cols") or 96)
    rows = int(payload.get("rows") or 28)

    if platform.system() != "Windows":
        await _terminal_error(client, terminal_id, "TERMINAL_UNSUPPORTED", "Terminal v1 supports Windows pwsh only.")
        return
    shell = shutil.which("pwsh") or shutil.which("powershell.exe")
    if not shell:
        await _terminal_error(client, terminal_id, "PWSH_NOT_FOUND", "PowerShell is not available in PATH.")
        return

    try:
        from winpty import PtyProcess
    except Exception:
        await _run_command_loop(client, terminal_id, shell, cwd, cols, rows)
        return

    try:
        pty = _spawn_pty(PtyProcess, shell, cwd, rows, cols)
    except Exception as exc:
        await _terminal_error(client, terminal_id, "TERMINAL_START_FAILED", str(exc))
        return

    await client.post_terminal_event(
        terminal_id,
        "ready",
        "pwsh started",
        cwd=cwd or "",
        payload={"status": "running", "cols": cols, "rows": rows},
    )
    await client.post_terminal_event(
        terminal_id,
        "status",
        "Terminal running",
        cwd=cwd or "",
        payload={"status": "running"},
    )

    input_task = asyncio.create_task(_pump_terminal_inputs(client, terminal_id, pty))
    try:
        while _pty_alive(pty):
            try:
                chunk = await asyncio.to_thread(pty.read, 4096)
            except EOFError:
                break
            except Exception as exc:
                if _pty_alive(pty):
                    await _terminal_error(client, terminal_id, "TERMINAL_READ_FAILED", str(exc))
                break
            if chunk:
                await client.post_terminal_event(terminal_id, "output", str(chunk), stream="stdout")
            else:
                await asyncio.sleep(0.05)
    finally:
        input_task.cancel()
        await asyncio.gather(input_task, return_exceptions=True)

    exit_code = _pty_exit_code(pty)
    try:
        await client.post_terminal_event(
            terminal_id,
            "exit",
            f"pwsh exited with code {exit_code}",
            exit_code=exit_code,
            payload={"status": "exited"},
        )
    except DevLinkApiError:
        return


async def _run_command_loop(client: DevLinkApiClient, terminal_id: str, shell: str, cwd: str | None, cols: int, rows: int) -> None:
    current_cwd = cwd or None
    await client.post_terminal_event(
        terminal_id,
        "ready",
        "PowerShell command mode started",
        cwd=current_cwd or "",
        payload={"status": "running", "cols": cols, "rows": rows, "mode": "command"},
    )
    await client.post_terminal_event(
        terminal_id,
        "status",
        "pywinpty is missing; using command-per-line fallback",
        cwd=current_cwd or "",
        payload={"status": "running", "mode": "command"},
    )

    last_sequence = 0
    while True:
        try:
            inputs = await client.terminal_inputs(terminal_id, after=last_sequence)
        except DevLinkApiError:
            await asyncio.sleep(0.5)
            continue
        for item in inputs:
            last_sequence = max(last_sequence, int(item.get("sequence") or 0))
            kind = item.get("kind")
            if kind == "kill":
                await client.post_terminal_event(
                    terminal_id,
                    "exit",
                    "Terminal killed",
                    cwd=current_cwd or "",
                    exit_code=0,
                    payload={"status": "killed", "mode": "command"},
                )
                return
            if kind != "stdin":
                continue
            raw = str(item.get("data") or "")
            for command in _split_commands(raw):
                if command.lower() in {"exit", "exit;"}:
                    await client.post_terminal_event(
                        terminal_id,
                        "exit",
                        "Terminal exited",
                        cwd=current_cwd or "",
                        exit_code=0,
                        payload={"status": "exited", "mode": "command"},
                    )
                    return
                next_cwd = _try_local_cd(command, current_cwd)
                if next_cwd:
                    current_cwd = next_cwd
                    await client.post_terminal_event(terminal_id, "cwd", current_cwd, cwd=current_cwd)
                    continue
                result = await asyncio.to_thread(_run_powershell_command, shell, command, current_cwd)
                if result["stdout"]:
                    await client.post_terminal_event(terminal_id, "output", result["stdout"], stream="stdout", cwd=current_cwd or "")
                if result["stderr"]:
                    await client.post_terminal_event(terminal_id, "stderr", result["stderr"], stream="stderr", cwd=current_cwd or "")
                await client.post_terminal_event(
                    terminal_id,
                    "status",
                    f"Command exited with code {result['exit_code']}",
                    cwd=current_cwd or "",
                    exit_code=result["exit_code"],
                    payload={"status": "running", "mode": "command", "last_exit_code": result["exit_code"]},
                )
        await asyncio.sleep(0.2)


async def _pump_terminal_inputs(client: DevLinkApiClient, terminal_id: str, pty) -> None:
    last_sequence = 0
    while _pty_alive(pty):
        try:
            inputs = await client.terminal_inputs(terminal_id, after=last_sequence)
        except DevLinkApiError:
            await asyncio.sleep(0.5)
            continue
        for item in inputs:
            last_sequence = max(last_sequence, int(item.get("sequence") or 0))
            kind = item.get("kind")
            if kind == "stdin":
                data = str(item.get("data") or "")
                if data:
                    await asyncio.to_thread(pty.write, data)
            elif kind == "resize":
                _resize_pty(pty, int(item.get("rows") or 28), int(item.get("cols") or 96))
            elif kind == "kill":
                _terminate_pty(pty)
                return
        await asyncio.sleep(0.2)


def _spawn_pty(pty_process, pwsh: str, cwd: str | None, rows: int, cols: int):
    try:
        return pty_process.spawn([pwsh], cwd=cwd, dimensions=(rows, cols))
    except TypeError:
        try:
            return pty_process.spawn(pwsh, cwd=cwd, dimensions=(rows, cols))
        except TypeError:
            return pty_process.spawn(pwsh, cwd=cwd)


def _resize_pty(pty, rows: int, cols: int) -> None:
    for name in ("setwinsize", "set_winsize", "resize"):
        method = getattr(pty, name, None)
        if method:
            try:
                method(rows, cols)
                return
            except TypeError:
                method(cols, rows)
                return


def _terminate_pty(pty) -> None:
    for args in ((True,), tuple()):
        try:
            pty.terminate(*args)
            return
        except TypeError:
            continue
        except Exception:
            return


def _pty_alive(pty) -> bool:
    method = getattr(pty, "isalive", None)
    if method:
        try:
            return bool(method())
        except Exception:
            return False
    return True


def _pty_exit_code(pty) -> int:
    for name in ("exitstatus", "exit_code", "returncode"):
        value = getattr(pty, name, None)
        if isinstance(value, int):
            return value
    return 0


def _split_commands(raw: str) -> list[str]:
    return [line.strip() for line in raw.replace("\r", "\n").split("\n") if line.strip()]


def _run_powershell_command(shell: str, command: str, cwd: str | None) -> dict[str, Any]:
    result = subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=cwd or None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "stdout": (result.stdout or "").rstrip(),
        "stderr": (result.stderr or "").rstrip(),
        "exit_code": int(result.returncode or 0),
    }


def _try_local_cd(command: str, cwd: str | None) -> str | None:
    lower = command.lower().strip()
    if not (lower == "cd" or lower.startswith("cd ") or lower.startswith("set-location ")):
        return None
    parts = command.split(maxsplit=1)
    if len(parts) == 1:
        return cwd
    from pathlib import Path

    target = parts[1].strip().strip('"').strip("'")
    next_path = Path(target)
    if not next_path.is_absolute() and cwd:
        next_path = Path(cwd) / target
    try:
        resolved = next_path.resolve()
    except Exception:
        return None
    if resolved.exists() and resolved.is_dir():
        return str(resolved)
    return None


async def _terminal_error(client: DevLinkApiClient, terminal_id: str, code: str, message: str) -> None:
    try:
        await client.post_terminal_event(
            terminal_id,
            "error",
            message,
            stream="stderr",
            payload={"status": "failed", "error_code": code},
        )
    except DevLinkApiError:
        return
