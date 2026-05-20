from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

from ..base import AgentCanceled, AgentEvent, AgentTask
from ...codex_process import normalize_codex_usage_limits

SUPPORTED_SANDBOXES = {"read-only", "workspace-write", "danger-full-access"}


class CodexAdapter:
    timeout_seconds = 60 * 20

    async def run(self, task: AgentTask):
        codex_path = shutil.which("codex")
        if not codex_path:
            yield AgentEvent(
                event_type="error",
                message="Codex CLI nie jest dostepny w PATH.",
                payload={"error_code": "CODEX_NOT_FOUND"},
            )
            yield AgentEvent(
                event_type="final",
                message="Codex CLI nie jest dostepny w PATH.",
                payload={"status": "failed", "exit_code": None, "error_code": "CODEX_NOT_FOUND"},
            )
            return

        command = self.build_command(task)
        started_at = time.monotonic()
        yield AgentEvent(
            event_type="status",
            message="Starting Codex CLI",
            payload={
                "kind": "running",
                "source": "cli",
                "raw_type": "bridge.codex.starting",
                "title": "Starting Codex CLI",
                "command": command,
                "cwd": task.project_path,
            },
        )

        exec_command = [codex_path, *command[1:]]
        process = await asyncio.create_subprocess_exec(
            *exec_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        assert process.stdin is not None
        process.stdin.write(self._prompt_for_task(task).encode("utf-8"))
        await process.stdin.drain()
        process.stdin.close()

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        readable_messages: list[str] = []
        assistant_messages: list[str] = []
        edited_files: dict[str, dict[str, Any]] = {}
        baseline_diff = await self._git_numstat(task.project_path)

        try:
            async for event in self._stream_process(
                process,
                task,
                stdout_lines,
                stderr_lines,
                readable_messages,
                assistant_messages,
                edited_files,
                baseline_diff,
            ):
                if event.event_type == "final" and event.payload.get("status") == "timed_out":
                    yield event
                    return
                yield event
        except AgentCanceled:
            raise

        exit_code = await process.wait()
        final_files = self._final_file_edits(edited_files)
        final_output = "\n\n".join(message for message in assistant_messages if message).strip()
        if not final_output:
            final_output = "\n".join(message for message in readable_messages if message).strip()
        if not final_output:
            final_output = "\n".join(stdout_lines).strip()
        error_output = "\n".join(stderr_lines).strip()
        file_payload = self._file_summary_payload(final_files)

        if exit_code == 0:
            success_output = self._append_file_summary(final_output or "Codex CLI finished successfully.", final_files)
            yield AgentEvent(
                event_type="final",
                message=success_output,
                payload={
                    "kind": "final",
                    "source": "codex",
                    "raw_type": "codex.final",
                    "title": "Final response",
                    "status": "succeeded",
                    "exit_code": exit_code,
                    "duration_ms": int((time.monotonic() - started_at) * 1000),
                    **file_payload,
                },
            )
        else:
            failed_output = self._append_file_summary(error_output or final_output or "Codex CLI failed.", final_files)
            yield AgentEvent(
                event_type="final",
                message=failed_output,
                payload={
                    "kind": "final",
                    "source": "codex",
                    "raw_type": "codex.final",
                    "title": "Final response",
                    "status": "failed",
                    "exit_code": exit_code,
                    "error_code": "CODEX_EXIT_CODE",
                    "error_message": error_output,
                    "duration_ms": int((time.monotonic() - started_at) * 1000),
                    **file_payload,
                },
            )

    def build_command(self, task: AgentTask) -> list[str]:
        sandbox = task.sandbox if task.sandbox in SUPPORTED_SANDBOXES else "workspace-write"
        model_settings = task.model_settings if isinstance(task.model_settings, dict) else {}
        tool_settings = task.tool_settings if isinstance(task.tool_settings, dict) else {}
        command = ["codex", "exec"]

        command.extend(["--cd", task.project_path, "--json", "--sandbox", sandbox])
        if bool(model_settings.get("bypass_approvals_and_sandbox") or tool_settings.get("bypass_approvals_and_sandbox")):
            command.append("--dangerously-bypass-approvals-and-sandbox")
        if bool(model_settings.get("oss") or tool_settings.get("oss")):
            command.append("--oss")
        local_provider = str(model_settings.get("local_provider") or tool_settings.get("local_provider") or "").strip()
        if local_provider:
            command.extend(["--local-provider", local_provider])
        for add_dir in _as_list([*task.add_dirs, *(_as_list(tool_settings.get("add_dirs")))]):
            if str(add_dir).strip():
                command.extend(["--add-dir", str(add_dir)])
        for image in _as_list([*task.images, *(_as_list(tool_settings.get("images")))]):
            if str(image).strip():
                command.extend(["--image", str(image)])
        if task.model:
            command.extend(["--model", task.model])
        if task.profile:
            command.extend(["--profile", task.profile])
        if task.web_search_enabled:
            command.append("--search")
        for flag_name, cli_flag in (
            ("skip_git_repo_check", "--skip-git-repo-check"),
            ("ephemeral", "--ephemeral"),
            ("ignore_user_config", "--ignore-user-config"),
            ("ignore_rules", "--ignore-rules"),
        ):
            if bool(model_settings.get(flag_name) or tool_settings.get(flag_name)):
                command.append(cli_flag)
        color = str(model_settings.get("color") or tool_settings.get("color") or "").strip()
        if color in {"always", "never", "auto"}:
            command.extend(["--color", color])
        output_schema = str(tool_settings.get("output_schema") or "").strip()
        if output_schema:
            command.extend(["--output-schema", output_schema])
        output_last_message = str(tool_settings.get("output_last_message") or "").strip()
        if output_last_message:
            command.extend(["--output-last-message", output_last_message])
        for value in _as_list(model_settings.get("enable_features") or tool_settings.get("enable_features")):
            if str(value).strip():
                command.extend(["--enable", str(value)])
        for value in _as_list(model_settings.get("disable_features") or tool_settings.get("disable_features")):
            if str(value).strip():
                command.extend(["--disable", str(value)])
        for value in _as_list(model_settings.get("config_overrides") or tool_settings.get("config_overrides")):
            if str(value).strip():
                command.extend(["--config", str(value)])
        if task.resume_mode and task.codex_session_id:
            command.append("resume")
            command.append(task.codex_session_id)
        command.append("-")
        return command

    def _prompt_for_task(self, task: AgentTask) -> str:
        lines: list[str] = []
        if isinstance(task.model_settings, dict) and task.model_settings.get("planning_mode"):
            lines.extend(
                [
                    "DevLink planning mode is enabled for this run.",
                    "Produce a concrete implementation plan and do not modify files or run mutating commands unless the user explicitly asks for implementation in a later turn.",
                    "",
                ]
            )
        if not task.selected_skills:
            lines.append(task.prompt)
            return "\n".join(lines)
        lines.append("DevLink selected Codex skills for this run:")
        for skill in task.selected_skills:
            name = str(skill.get("name") or skill.get("id") or "").strip()
            description = str(skill.get("description") or "").strip()
            if not name:
                continue
            if description:
                lines.append(f"- ${name}: {description}")
            else:
                lines.append(f"- ${name}")
        lines.extend(
            [
                "",
                "Use these skills when they are relevant. Do not assume that unselected skills were requested.",
                "",
                task.prompt,
            ]
        )
        return "\n".join(lines)

    async def _stream_process(
        self,
        process,
        task: AgentTask,
        stdout_lines: list[str],
        stderr_lines: list[str],
        readable_messages: list[str],
        assistant_messages: list[str],
        edited_files: dict[str, dict[str, Any]],
        baseline_diff: dict[str, dict[str, int]],
    ):
        assert process.stdout is not None
        assert process.stderr is not None

        queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()

        async def read_stdout() -> None:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                stdout_lines.append(text)
                payload = self._parse_json_line(text)
                if payload:
                    message = self._message_from_payload(payload)
                    file_edit = self._extract_file_edit(payload)
                    if file_edit:
                        file_edit = await self._enrich_file_edit_with_git_diff(file_edit, task.project_path, baseline_diff)
                        self._merge_file_edits(edited_files, file_edit.get("files") or [])
                        message = str(file_edit.get("message") or message)
                    if self._is_agent_message_completed(payload) and message:
                        assistant_messages.append(message)
                    if message:
                        readable_messages.append(message)
                    await queue.put(self._agent_event_from_payload(payload, message, task, file_edit=file_edit))
                else:
                    readable_messages.append(text)
                    await queue.put(
                        AgentEvent(
                            event_type="stdout",
                            message=text,
                            payload={"kind": "terminal_stdout", "source": "codex", "raw_type": "stdout", "cwd": task.project_path},
                        )
                    )
            await queue.put(None)

        async def read_stderr() -> None:
            emitted_stderr_keys: set[str] = set()
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                stderr_lines.append(text)
                if not self._should_emit_stderr_line(text):
                    continue
                text = self._compact_stderr_line(text)
                compact_key = self._stderr_compaction_key(text)
                if compact_key:
                    if compact_key in emitted_stderr_keys:
                        continue
                    emitted_stderr_keys.add(compact_key)
                    text = self._stderr_compaction_message(compact_key)
                await queue.put(
                    AgentEvent(
                        event_type="stderr",
                        message=text,
                        payload={
                            "kind": "warning" if self._is_warning_line(text) else "terminal_stderr",
                            "level": "warning" if self._is_warning_line(text) else "error",
                            "source": "codex",
                            "raw_type": "stderr",
                            "cwd": task.project_path,
                        },
                    )
                )
            await queue.put(None)

        readers = [asyncio.create_task(read_stdout()), asyncio.create_task(read_stderr())]
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout_seconds
        next_idle_event = loop.time() + 30
        finished_readers = 0

        try:
            while finished_readers < 2:
                if task.cancel_event and task.cancel_event.is_set():
                    await self._terminate_process(process)
                    raise AgentCanceled("Task canceled by backend.")

                if loop.time() >= deadline:
                    await self._terminate_process(process)
                    yield AgentEvent(
                        event_type="final",
                        message="Codex CLI przekroczyl limit czasu.",
                        payload={
                            "kind": "final",
                            "source": "cli",
                            "raw_type": "bridge.codex.timeout",
                            "status": "timed_out",
                            "exit_code": None,
                            "error_code": "CODEX_TIMEOUT",
                        },
                    )
                    return

                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    if loop.time() >= next_idle_event:
                        next_idle_event = loop.time() + 30
                        yield AgentEvent(
                            event_type="agent_event",
                            message="Codex still running...",
                            payload={
                                "kind": "running",
                                "source": "cli",
                                "raw_type": "bridge.codex.idle",
                                "title": "Codex still running",
                                "cwd": task.project_path,
                            },
                        )
                    continue

                if item is None:
                    finished_readers += 1
                else:
                    next_idle_event = loop.time() + 30
                    yield item
        finally:
            for reader in readers:
                if not reader.done():
                    reader.cancel()
            await asyncio.gather(*readers, return_exceptions=True)

    async def _terminate_process(self, process) -> None:
        if process.returncode is None:
            process.kill()
        await process.wait()

    def _parse_json_line(self, text: str) -> dict[str, Any] | None:
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else {"value": value}

    def _event_name(self, payload: dict[str, Any]) -> str:
        value = payload.get("type") or payload.get("event") or payload.get("name")
        return str(value or "Codex event")

    def _agent_event_from_payload(
        self,
        payload: dict[str, Any],
        message: str,
        task: AgentTask,
        file_edit: dict[str, Any] | None = None,
    ) -> AgentEvent:
        raw_type = self._event_name(payload)
        usage_limits = normalize_codex_usage_limits(payload)
        if file_edit is None:
            file_edit = self._extract_file_edit(payload)
        kind = "usage_limits" if usage_limits else "diff" if file_edit else self._kind_for_payload(payload)
        title = self._title_for_kind(kind, raw_type)
        display_message = str(file_edit.get("message") or message or raw_type) if file_edit else message or raw_type
        normalized = {
            **payload,
            "kind": kind,
            "source": "codex",
            "raw_type": raw_type,
            "title": title,
            "message": display_message,
            "cwd": task.project_path,
        }
        if file_edit:
            normalized.update(file_edit)
        if usage_limits:
            normalized["codex_usage_limits"] = usage_limits
        codex_session_id = self._extract_session_id(payload)
        if codex_session_id:
            normalized["codex_session_id"] = codex_session_id
        command = self._extract_command(payload)
        if command:
            normalized["command"] = command
        return AgentEvent(event_type="agent_event", message=display_message or title, payload=normalized)

    def _kind_for_payload(self, payload: dict[str, Any]) -> str:
        if self._is_agent_message_completed(payload):
            return "assistant_preview"
        item_type = self._item_type(payload)
        if item_type == "reasoning":
            return "thinking"
        if item_type == "command_execution":
            return "command"
        if item_type == "file_change":
            return "diff"
        if item_type == "todo_list":
            return "running"
        event_name = self._event_name(payload).lower()
        text = self._message_from_payload(payload).lower()
        combined = f"{event_name} {text}"
        if "reason" in combined or "thinking" in combined:
            return "thinking"
        if "exec" in combined or "command" in combined or "shell" in combined:
            return "command"
        if "tool" in combined:
            return "tool_call"
        if "diff" in event_name or "patch" in event_name or "file" in event_name or "diff" in text or "patch" in text:
            return "diff"
        if "thread" in combined or "session" in combined or "turn.started" in combined or "turn.completed" in combined:
            return "running"
        if "final" in combined:
            return "final"
        if "error" in combined or "failed" in combined:
            return "error"
        return "status"

    def _is_agent_message_completed(self, payload: dict[str, Any]) -> bool:
        if str(payload.get("type") or payload.get("event") or "").lower() != "item.completed":
            return False
        item = payload.get("item")
        return isinstance(item, dict) and str(item.get("type") or "").lower() == "agent_message"

    def _item_type(self, payload: dict[str, Any]) -> str:
        item = payload.get("item")
        if not isinstance(item, dict):
            return ""
        return str(item.get("type") or "").lower()

    def _title_for_kind(self, kind: str, raw_type: str) -> str:
        titles = {
            "thinking": "Thinking",
            "tool_call": "Using tool",
            "command": "Running command",
            "diff": "Editing files",
            "running": "Codex running",
            "assistant_preview": "Assistant response",
            "final": "Final response",
            "error": "Codex error",
            "usage_limits": "Usage limits updated",
            "status": "Codex event",
        }
        return titles.get(kind, raw_type)

    def _extract_session_id(self, value: Any) -> str:
        if isinstance(value, dict):
            for key in ("codex_session_id", "thread_id", "session_id", "conversation_id"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate:
                    return candidate
            event_name = str(value.get("type") or value.get("event") or value.get("name") or "").lower()
            candidate_id = value.get("id")
            if ("thread" in event_name or "session" in event_name) and isinstance(candidate_id, str) and candidate_id:
                return candidate_id
            for key in ("payload", "thread", "session", "conversation", "data", "item"):
                if key in value:
                    candidate = self._extract_session_id(value[key])
                    if candidate:
                        return candidate
        if isinstance(value, list):
            for item in value:
                candidate = self._extract_session_id(item)
                if candidate:
                    return candidate
        return ""

    def _extract_command(self, value: Any) -> str:
        if isinstance(value, dict):
            for key in ("command", "cmd", "args"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate:
                    return candidate
                if isinstance(candidate, list) and candidate:
                    return " ".join(str(part) for part in candidate)
            for nested in value.values():
                candidate = self._extract_command(nested)
                if candidate:
                    return candidate
        if isinstance(value, list):
            for item in value:
                candidate = self._extract_command(item)
                if candidate:
                    return candidate
        return ""

    def _extract_file_edit(self, value: Any) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for text in self._iter_strings(value):
            if self._looks_like_patch(text):
                files.extend(self._parse_patch_files(text))
        if not files:
            files.extend(self._extract_structured_file_edits(value))
        if not files:
            direct_path = self._extract_file_path(value)
            additions = self._extract_number(value, {"additions", "added", "lines_added", "insertions", "added_lines"})
            deletions = self._extract_number(value, {"deletions", "deleted", "removed", "lines_deleted", "removed_lines"})
            if direct_path or additions is not None or deletions is not None:
                files.append(
                    {
                        "file_path": direct_path or "unknown file",
                        "additions": additions or 0,
                        "deletions": deletions or 0,
                        "counts_known": additions is not None or deletions is not None,
                    }
                )
        if not files:
            return {}

        collapsed = self._collapse_file_edits(files)
        additions = sum(int(item.get("additions") or 0) for item in collapsed)
        deletions = sum(int(item.get("deletions") or 0) for item in collapsed)
        first = collapsed[0]
        file_path = str(first.get("file_path") or "unknown file")
        file_name = self._file_name(file_path)
        return {
            "file_path": file_path,
            "file_name": file_name,
            "additions": additions,
            "deletions": deletions,
            "counts_known": any(bool(item.get("counts_known")) for item in collapsed),
            "files": collapsed,
            "message": self._format_edit_message(file_name, additions, deletions, counts_known=any(bool(item.get("counts_known")) for item in collapsed)),
        }

    def _iter_strings(self, value: Any):
        if isinstance(value, str):
            yield value
            return
        if isinstance(value, dict):
            for nested in value.values():
                yield from self._iter_strings(nested)
            return
        if isinstance(value, list):
            for nested in value:
                yield from self._iter_strings(nested)

    def _looks_like_patch(self, text: str) -> bool:
        return (
            "*** Update File:" in text
            or "*** Add File:" in text
            or "*** Delete File:" in text
            or "diff --git " in text
        )

    def _parse_patch_files(self, text: str) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        def ensure_file(path: str) -> dict[str, Any]:
            nonlocal current
            path = path.strip().strip('"')
            current = next((item for item in files if item["file_path"] == path), None)
            if current is None:
                current = {"file_path": path, "additions": 0, "deletions": 0, "counts_known": True}
                files.append(current)
            return current

        for line in text.splitlines():
            if line.startswith("*** Update File:"):
                ensure_file(line.split(":", 1)[1])
                continue
            if line.startswith("*** Add File:"):
                ensure_file(line.split(":", 1)[1])
                continue
            if line.startswith("*** Delete File:"):
                ensure_file(line.split(":", 1)[1])
                continue
            if line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4:
                    path = parts[3]
                    if path.startswith("b/"):
                        path = path[2:]
                    ensure_file(path)
                continue
            if line.startswith("+++ "):
                path = line[4:].strip()
                if path != "/dev/null":
                    if path.startswith("b/"):
                        path = path[2:]
                    ensure_file(path)
                continue
            if line.startswith("--- "):
                path = line[4:].strip()
                if path != "/dev/null" and current is None:
                    if path.startswith("a/"):
                        path = path[2:]
                    ensure_file(path)
                continue
            if current is None:
                continue
            if line.startswith("+") and not line.startswith("+++"):
                current["additions"] = int(current.get("additions") or 0) + 1
            elif line.startswith("-") and not line.startswith("---"):
                current["deletions"] = int(current.get("deletions") or 0) + 1
        return files

    def _collapse_file_edits(self, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        collapsed: dict[str, dict[str, Any]] = {}
        for item in files:
            path = str(item.get("file_path") or "unknown file")
            target = collapsed.setdefault(
                path,
                {"file_path": path, "file_name": self._file_name(path), "additions": 0, "deletions": 0, "counts_known": False},
            )
            target["additions"] = int(target.get("additions") or 0) + int(item.get("additions") or 0)
            target["deletions"] = int(target.get("deletions") or 0) + int(item.get("deletions") or 0)
            target["counts_known"] = bool(target.get("counts_known") or item.get("counts_known"))
        return list(collapsed.values())

    def _extract_structured_file_edits(self, value: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(value, dict):
            direct_path = self._extract_direct_file_path(value)
            additions = self._extract_number(value, {"additions", "added", "lines_added", "insertions", "added_lines"})
            deletions = self._extract_number(value, {"deletions", "deleted", "removed", "lines_deleted", "removed_lines"})
            if direct_path:
                found.append(
                    {
                        "file_path": direct_path,
                        "additions": additions or 0,
                        "deletions": deletions or 0,
                        "counts_known": additions is not None or deletions is not None,
                        "change_kind": str(value.get("kind") or value.get("change_kind") or ""),
                    }
                )
                return found
            for nested in value.values():
                found.extend(self._extract_structured_file_edits(nested))
        if isinstance(value, list):
            for item in value:
                found.extend(self._extract_structured_file_edits(item))
        return found

    async def _enrich_file_edit_with_git_diff(
        self,
        file_edit: dict[str, Any],
        cwd: str,
        baseline_diff: dict[str, dict[str, int]],
    ) -> dict[str, Any]:
        files = file_edit.get("files")
        if not isinstance(files, list) or not files:
            return file_edit
        paths = [str(item.get("file_path") or "") for item in files if isinstance(item, dict) and item.get("file_path")]
        current_diff = await self._git_numstat(cwd, paths)
        enriched: list[dict[str, Any]] = []
        for item in files:
            if not isinstance(item, dict):
                continue
            next_item = dict(item)
            path = str(next_item.get("file_path") or "")
            key = self._diff_key(path, cwd)
            current = current_diff.get(key)
            baseline = baseline_diff.get(key, {"additions": 0, "deletions": 0})
            if current:
                next_item["additions"] = max(0, int(current.get("additions") or 0) - int(baseline.get("additions") or 0))
                next_item["deletions"] = max(0, int(current.get("deletions") or 0) - int(baseline.get("deletions") or 0))
                next_item["counts_known"] = True
            elif str(next_item.get("change_kind") or "").lower() in {"add", "create", "created"}:
                added_lines = await self._count_file_lines(cwd, path)
                if added_lines is not None:
                    next_item["additions"] = added_lines
                    next_item["deletions"] = 0
                    next_item["counts_known"] = True
            enriched.append(next_item)
        collapsed = self._collapse_file_edits(enriched)
        additions = sum(int(item.get("additions") or 0) for item in collapsed)
        deletions = sum(int(item.get("deletions") or 0) for item in collapsed)
        counts_known = any(bool(item.get("counts_known")) for item in collapsed)
        first = collapsed[0]
        file_path = str(first.get("file_path") or "unknown file")
        file_name = self._file_name(file_path)
        return {
            **file_edit,
            "file_path": file_path,
            "file_name": file_name,
            "additions": additions,
            "deletions": deletions,
            "counts_known": counts_known,
            "files": collapsed,
            "message": self._format_edit_message(file_name, additions, deletions, counts_known=counts_known),
        }

    async def _git_numstat(self, cwd: str, paths: list[str] | None = None) -> dict[str, dict[str, int]]:
        root = Path(cwd)
        if not root.exists():
            return {}

        def run_git() -> dict[str, dict[str, int]]:
            command = ["git", "-C", str(root), "diff", "--numstat", "--"]
            if paths:
                command.extend(self._git_pathspec(path, cwd) for path in paths if path)
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=2,
                )
            except (OSError, subprocess.SubprocessError):
                return {}
            if result.returncode != 0:
                return {}
            parsed: dict[str, dict[str, int]] = {}
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                additions = self._coerce_int(parts[0])
                deletions = self._coerce_int(parts[1])
                if additions is None or deletions is None:
                    continue
                file_path = parts[2]
                parsed[self._diff_key(file_path, cwd)] = {"additions": additions, "deletions": deletions}
            return parsed

        return await asyncio.to_thread(run_git)

    async def _count_file_lines(self, cwd: str, path: str) -> int | None:
        if not path or path == "unknown file":
            return None
        root = Path(cwd)
        candidate = Path(path)
        file_path = candidate if candidate.is_absolute() else root / path
        if not file_path.exists() or not file_path.is_file():
            return None

        def count_lines() -> int | None:
            try:
                data = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
            if not data:
                return 0
            return len(data.splitlines())

        return await asyncio.to_thread(count_lines)

    def _diff_key(self, path: str, cwd: str = "") -> str:
        text = str(path or "").strip().strip('"').replace("\\", "/")
        if text.startswith("a/") or text.startswith("b/"):
            text = text[2:]
        if cwd:
            try:
                candidate = Path(path)
                if candidate.is_absolute():
                    text = candidate.relative_to(Path(cwd)).as_posix()
            except (OSError, ValueError):
                pass
        return text

    def _git_pathspec(self, path: str, cwd: str) -> str:
        try:
            candidate = Path(path)
            if candidate.is_absolute():
                return candidate.relative_to(Path(cwd)).as_posix()
        except (OSError, ValueError):
            return path
        return path

    def _merge_file_edits(self, target: dict[str, dict[str, Any]], files: list[Any]) -> None:
        for raw in files:
            if not isinstance(raw, dict):
                continue
            path = str(raw.get("file_path") or "")
            if not path:
                continue
            key = self._diff_key(path)
            existing = target.setdefault(
                key,
                {"file_path": path, "file_name": self._file_name(path), "additions": 0, "deletions": 0, "counts_known": False},
            )
            existing["file_path"] = path
            existing["file_name"] = str(raw.get("file_name") or self._file_name(path))
            if raw.get("counts_known"):
                existing["additions"] = int(raw.get("additions") or 0)
                existing["deletions"] = int(raw.get("deletions") or 0)
                existing["counts_known"] = True

    def _final_file_edits(self, edited_files: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in edited_files.values() if str(item.get("file_path") or "")]

    def _file_summary_payload(self, files: list[dict[str, Any]]) -> dict[str, Any]:
        if not files:
            return {}
        additions = sum(int(item.get("additions") or 0) for item in files if item.get("counts_known"))
        deletions = sum(int(item.get("deletions") or 0) for item in files if item.get("counts_known"))
        return {
            "files": files,
            "additions": additions,
            "deletions": deletions,
            "counts_known": any(bool(item.get("counts_known")) for item in files),
        }

    def _append_file_summary(self, text: str, files: list[dict[str, Any]]) -> str:
        if not files:
            return text
        lines = ["", "Edited files:"]
        for item in files:
            name = str(item.get("file_path") or item.get("file_name") or "file")
            if item.get("counts_known"):
                lines.append(f"- {name} (+{int(item.get('additions') or 0)} -{int(item.get('deletions') or 0)})")
            else:
                lines.append(f"- {name}")
        return text.rstrip() + "\n" + "\n".join(lines)

    def _extract_file_path(self, value: Any) -> str:
        if isinstance(value, dict):
            direct = self._extract_direct_file_path(value)
            if direct:
                return direct
            for nested in value.values():
                candidate = self._extract_file_path(nested)
                if candidate:
                    return candidate
        if isinstance(value, list):
            for item in value:
                candidate = self._extract_file_path(item)
                if candidate:
                    return candidate
        return ""

    def _extract_direct_file_path(self, value: dict[str, Any]) -> str:
        for key in ("file_path", "filename", "relative_path", "target_file", "path"):
            candidate = value.get(key)
            if isinstance(candidate, str) and self._looks_like_file_path(candidate, key):
                return candidate
        return ""

    def _looks_like_file_path(self, value: str, key: str) -> bool:
        if key in {"cwd", "project_path"}:
            return False
        text = value.strip()
        if not text or "\n" in text:
            return False
        return any(part in text for part in ("/", "\\")) or "." in self._file_name(text)

    def _extract_number(self, value: Any, keys: set[str]) -> int | None:
        if isinstance(value, dict):
            for key, candidate in value.items():
                if key in keys:
                    number = self._coerce_int(candidate)
                    if number is not None:
                        return number
            for nested in value.values():
                number = self._extract_number(nested, keys)
                if number is not None:
                    return number
        if isinstance(value, list):
            for item in value:
                number = self._extract_number(item, keys)
                if number is not None:
                    return number
        return None

    def _coerce_int(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                return None
        return None

    def _file_name(self, path: str) -> str:
        return path.replace("\\", "/").rstrip("/").split("/")[-1] or path

    def _format_edit_message(self, file_name: str, additions: int, deletions: int, counts_known: bool = True) -> str:
        if not counts_known:
            return f"Editing {file_name}"
        return f"Editing {file_name} +{additions} -{deletions}"

    def _message_from_payload(self, payload: dict[str, Any]) -> str:
        text = self._extract_text(payload)
        return text.strip()

    def _extract_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(part for item in value if (part := self._extract_text(item)))
        if isinstance(value, dict):
            for key in ("message", "text", "content", "output", "summary", "final_output"):
                if key in value:
                    text = self._extract_text(value[key])
                    if text:
                        return text
            for key in ("item", "delta", "data"):
                if key in value:
                    text = self._extract_text(value[key])
                    if text:
                        return text
        return ""

    def _should_emit_stderr_line(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        lower = stripped.lower()
        if lower.startswith("<") or "window._cf_chl_opt" in lower or "challenge-platform" in lower:
            return False
        noisy_fragments = (
            "codex_core_skills::loader: ignoring interface.icon",
            "codex_core_plugins::manifest: ignoring interface.defaultprompt",
            "failed to create shell snapshot for powershell",
        )
        if any(fragment in lower for fragment in noisy_fragments):
            return False
        return True

    def _compact_stderr_line(self, text: str) -> str:
        return text if len(text) <= 500 else f"{text[:500]}..."

    def _stderr_compaction_key(self, text: str) -> str:
        lower = text.lower()
        if (
            "running scripts is disabled" in lower
            or "pssecurityexception" in lower
            or "execution_policies" in lower
            or "microsoft.powershell_profile.ps1 cannot be loaded" in lower
            or "npm.ps1 cannot be loaded" in lower
        ):
            return "powershell_execution_policy"
        return ""

    def _stderr_compaction_message(self, key: str) -> str:
        if key == "powershell_execution_policy":
            return "PowerShell execution policy blocked a script; Codex may retry with npm.cmd or an execution-policy bypass."
        return key

    def _is_warning_line(self, text: str) -> bool:
        return " warn " in f" {text.lower()} " or "warning" in text.lower()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
