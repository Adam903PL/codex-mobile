from __future__ import annotations

import html
import re
from typing import Any

import httpx

from .config import DevLinkConfig, save_config


class DevLinkApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DevLinkApiClient:
    def __init__(self, config: DevLinkConfig, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        token = self.config.get_device_token()
        if not token:
            return {}
        return {"Authorization": f"Device {token}"}

    async def pair(
        self,
        code: str,
        name: str,
        platform: str,
        project_path: str | None = None,
        project_name: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "code": code,
            "name": name,
            "platform": platform,
            "project_path": project_path or "",
            "project_name": project_name or "",
        }
        return await self._request("POST", "/cli/pair/", json=payload, auth_required=False)

    async def heartbeat(self, busy: bool = False) -> dict[str, Any]:
        result = await self._request("POST", "/cli/heartbeat/", json={"busy": busy})
        self.config.last_device_status = result.get("status")
        self.config.last_heartbeat_at = result.get("last_seen_at")
        save_config(self.config)
        return result

    async def post_capabilities(self, capabilities: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/cli/capabilities/", json=capabilities)

    async def register_project(
        self,
        name: str,
        local_path: str,
        repository_url: str = "",
        default_model: str = "",
        default_profile: str = "",
        default_sandbox: str = "workspace-write",
        default_approval_policy: str = "on-request",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/cli/projects/",
            json={
                "name": name,
                "local_path": local_path,
                "repository_url": repository_url,
                "default_model": default_model,
                "default_profile": default_profile,
                "default_sandbox": default_sandbox,
                "default_approval_policy": default_approval_policy,
            },
        )

    async def list_projects(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/cli/projects/")

    async def remove_project(self, project_id: str) -> None:
        await self._request("DELETE", f"/cli/projects/{project_id}/", allow_no_content=True)

    async def next_task(self) -> dict[str, Any] | None:
        result = await self._request("GET", "/cli/tasks/next/", allow_no_content=True)
        return result or None

    async def next_approval(self) -> dict[str, Any] | None:
        result = await self._request("GET", "/cli/actions/next/", allow_no_content=True)
        return result or None

    async def finish_approval(
        self,
        approval_id: str,
        status: str,
        result_message: str = "",
        error_message: str = "",
        stdout: str = "",
        stderr: str = "",
        exit_code: int | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/cli/actions/{approval_id}/finish/",
            json={
                "status": status,
                "result_message": result_message,
                "error_message": error_message,
                "stdout": stdout or result_message,
                "stderr": stderr or error_message,
                "exit_code": exit_code if exit_code is not None else (0 if status == "succeeded" else 1),
            },
        )

    async def task_status(self, task_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/cli/tasks/{task_id}/")

    async def start_task(self, task_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/cli/tasks/{task_id}/start/")

    async def post_task_event(self, task_id: str, event_type: str, message: str = "", payload: dict | None = None) -> dict:
        return await self._request(
            "POST",
            f"/cli/tasks/{task_id}/events/",
            json={"event_type": event_type, "message": message, "payload": payload or {}},
        )

    async def finish_task(
        self,
        task_id: str,
        status: str,
        final_output: str = "",
        exit_code: int | None = None,
        error_code: str = "",
        error_message: str = "",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/cli/tasks/{task_id}/finish/",
            json={
                "status": status,
                "final_output": final_output,
                "exit_code": exit_code if exit_code is not None else (0 if status == "succeeded" else 1),
                "error_code": error_code,
                "error_message": error_message,
            },
        )

    async def next_terminal_session(self) -> dict[str, Any] | None:
        result = await self._request("GET", "/cli/terminal/sessions/next/", allow_no_content=True)
        return result or None

    async def terminal_inputs(self, terminal_id: str, after: int = 0) -> list[dict[str, Any]]:
        suffix = f"?after={after}" if after else ""
        return await self._request("GET", f"/cli/terminal/sessions/{terminal_id}/input/{suffix}")

    async def post_terminal_event(
        self,
        terminal_id: str,
        kind: str,
        data: str = "",
        stream: str = "",
        cwd: str = "",
        exit_code: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/cli/terminal/sessions/{terminal_id}/events/",
            json={
                "kind": kind,
                "data": data,
                "stream": stream,
                "cwd": cwd,
                "exit_code": exit_code,
                "payload": payload or {},
            },
        )

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        auth_required: bool = True,
        allow_no_content: bool = False,
    ) -> Any:
        headers = self.headers if auth_required else {}
        if auth_required and not headers:
            raise DevLinkApiError("CLI nie jest sparowane z backendem.")

        api_url = self.config.api_url.rstrip("/")
        try:
            async with httpx.AsyncClient(base_url=api_url, timeout=self.timeout) as client:
                response = await client.request(method, path, json=json, headers=headers)
        except httpx.TimeoutException as exc:
            raise DevLinkApiError(
                f"API timeout during {method} {api_url}{path}. Backend may be busy; retrying is safe."
            ) from exc
        except httpx.RequestError as exc:
            detail = str(exc) or exc.__class__.__name__
            raise DevLinkApiError(
                f"Network error during {method} {api_url}{path}: {detail}. Retrying is safe."
            ) from exc

        if allow_no_content and response.status_code == 204:
            return None
        if response.is_error:
            message = response.text
            try:
                payload = response.json()
                message = payload.get("message") or message
            except ValueError:
                message = _message_from_html_error(message) or _truncate(message)
            raise DevLinkApiError(f"API error {response.status_code}: {message}", status_code=response.status_code)
        return response.json()


def _message_from_html_error(text: str) -> str:
    title = _first_html_match(text, r"<title>(.*?)</title>")
    exception_value = _first_html_match(text, r'<pre class="exception_value">(.*?)</pre>')
    if title and exception_value:
        return f"{title}: {exception_value}"
    return title or exception_value


def _first_html_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    value = re.sub(r"<[^>]+>", " ", match.group(1))
    value = html.unescape(value)
    return " ".join(value.split())


def _truncate(text: str, limit: int = 600) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else f"{clean[:limit]}..."
