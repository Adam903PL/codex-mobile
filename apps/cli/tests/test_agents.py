import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from typer.testing import CliRunner

from devlink_cli import main
from devlink_cli.agents.base import AgentCanceled, AgentEvent, AgentTask
from devlink_cli.agents.factory import AgentFactory
from devlink_cli.agents.adapters.codex import CodexAdapter
from devlink_cli.agents.adapters.shell import ShellAdapter
from devlink_cli.api_client import DevLinkApiClient, DevLinkApiError
from devlink_cli.config import DevLinkConfig
from devlink_cli.codex_process import (
    collect_capabilities,
    discover_codex_skills,
    index_project_files,
    is_git_repository,
    latest_codex_usage_limits,
    model_context_windows,
    normalize_codex_usage_limits,
    parse_features,
    parse_mcp_servers,
    parse_models,
    usage_limits_missing_or_stale,
)
from devlink_cli.daemon import execute_approval_action, run_task, sync_capabilities
from devlink_cli.terminal_bridge import run_terminal_session


class AgentFactoryTests(unittest.TestCase):
    def test_factory_creates_mvp_adapters(self):
        self.assertIsInstance(AgentFactory.create("codex"), CodexAdapter)
        self.assertIsInstance(AgentFactory.create("shell"), ShellAdapter)

    def test_factory_rejects_unknown_agent(self):
        with self.assertRaises(ValueError):
            AgentFactory.create("claude")


class ShellAdapterTests(unittest.TestCase):
    def test_shell_adapter_returns_final_success_event(self):
        async def collect():
            adapter = ShellAdapter()
            task = AgentTask(id="1", prompt="ping", project_path="C:\\repo", agent_type="shell")
            return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())
        self.assertEqual(events[-1].event_type, "final")
        self.assertEqual(events[-1].payload["status"], "succeeded")


class TerminalBridgeTests(unittest.TestCase):
    def test_terminal_bridge_reports_missing_pwsh(self):
        class FakeClient:
            def __init__(self):
                self.events = []

            async def post_terminal_event(self, *args, **kwargs):
                self.events.append((args, kwargs))
                return {}

        async def run():
            client = FakeClient()
            with patch("devlink_cli.terminal_bridge.platform.system", return_value="Windows"), patch(
                "devlink_cli.terminal_bridge.shutil.which", return_value=None
            ):
                await run_terminal_session(client, {"id": "terminal-1", "cwd": "C:\\repo"})
            return client.events

        events = asyncio.run(run())
        self.assertEqual(events[0][0][1], "error")
        self.assertEqual(events[0][1]["payload"]["error_code"], "PWSH_NOT_FOUND")


class FakeStream:
    def __init__(self, lines):
        self.lines = [line.encode("utf-8") for line in lines]

    async def readline(self):
        if self.lines:
            return self.lines.pop(0)
        return b""


class HangingStream:
    async def readline(self):
        await asyncio.sleep(3600)
        return b""


class FakeStdin:
    def __init__(self):
        self.content = b""
        self.closed = False

    def write(self, data):
        self.content += data

    async def drain(self):
        return None

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, stdout_lines=None, stderr_lines=None, exit_code=0, hang=False):
        self.stdin = FakeStdin()
        self.stdout = HangingStream() if hang else FakeStream(stdout_lines or [])
        self.stderr = HangingStream() if hang else FakeStream(stderr_lines or [])
        self.exit_code = exit_code
        self.returncode = None
        self.killed = False

    async def wait(self):
        if self.returncode is None:
            self.returncode = self.exit_code
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class CodexAdapterTests(unittest.TestCase):
    def test_normalize_codex_usage_limits_maps_primary_and_secondary_windows(self):
        usage = normalize_codex_usage_limits(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "rate_limits": {
                        "primary": {"used_percent": 19.0, "window_minutes": 300, "resets_at": 1778958549},
                        "secondary": {"used_percent": 87.0, "window_minutes": 10080, "resets_at": 1779465600},
                        "plan_type": "plus",
                        "rate_limit_reached_type": None,
                    },
                },
            }
        )

        self.assertEqual(usage["five_hour"]["used_percent"], 19.0)
        self.assertEqual(usage["five_hour"]["remaining_percent"], 81.0)
        self.assertEqual(usage["five_hour"]["window_minutes"], 300)
        self.assertEqual(usage["weekly"]["used_percent"], 87.0)
        self.assertEqual(usage["weekly"]["window_minutes"], 10080)
        self.assertTrue(usage["five_hour"]["resets_at"].endswith("+00:00"))
        self.assertEqual(usage["plan_type"], "plus")

    def test_latest_codex_usage_limits_reads_newest_session_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "sessions" / "2026" / "05" / "16"
            session_dir.mkdir(parents=True)
            (session_dir / "rollout.jsonl").write_text(
                "\n".join(
                    [
                        '{"timestamp":"2026-05-16T10:00:00Z","type":"event_msg","payload":{"type":"token_count","rate_limits":{"primary":{"used_percent":3,"window_minutes":300,"resets_at":1778958549},"secondary":{"used_percent":7,"window_minutes":10080,"resets_at":1779465600},"plan_type":"plus","rate_limit_reached_type":null}}}',
                        '{"timestamp":"2026-05-16T11:00:00Z","type":"event_msg","payload":{"type":"token_count","rate_limits":{"primary":{"used_percent":4,"window_minutes":300,"resets_at":1778958549},"secondary":{"used_percent":8,"window_minutes":10080,"resets_at":1779465600},"plan_type":"plus","rate_limit_reached_type":null}}}',
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"CODEX_HOME": str(root)}):
                usage = latest_codex_usage_limits()

        self.assertEqual(usage["five_hour"]["used_percent"], 4.0)
        self.assertEqual(usage["weekly"]["used_percent"], 8.0)
        self.assertEqual(usage["source"], "session_file")

    def test_usage_limits_missing_or_stale_detects_old_observation(self):
        stale = {
            "five_hour": {"used_percent": 1},
            "weekly": {"used_percent": 2},
            "observed_at": "2020-01-01T00:00:00+00:00",
        }

        self.assertTrue(usage_limits_missing_or_stale(stale))

    def test_build_command_uses_project_settings_without_dangerous_flags(self):
        adapter = CodexAdapter()
        task = AgentTask(
            id="1",
            prompt="fix",
            project_path="C:\\repo",
            model="gpt-test",
            profile="school",
            sandbox="read-only",
            approval_policy="never",
        )

        command = adapter.build_command(task)

        self.assertEqual(command[0:4], ["codex", "exec", "--cd", "C:\\repo"])
        self.assertIn("--model", command)
        self.assertIn("gpt-test", command)
        self.assertIn("--profile", command)
        self.assertIn("school", command)
        self.assertIn("read-only", command)
        self.assertEqual(command[-1], "-")
        self.assertNotIn("--ask-for-approval", command)
        self.assertNotIn("never", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_build_command_uses_exec_resume_for_codex_session(self):
        adapter = CodexAdapter()
        task = AgentTask(
            id="1",
            prompt="continue",
            project_path="C:\\repo",
            codex_session_id="codex-thread-1",
            resume_mode=True,
        )

        command = adapter.build_command(task)

        self.assertEqual(command[0:2], ["codex", "exec"])
        self.assertIn("resume", command)
        self.assertLess(command.index("--cd"), command.index("resume"))
        self.assertIn("codex-thread-1", command)
        self.assertEqual(command[-1], "-")
        self.assertNotIn("--ask-for-approval", command)
        self.assertNotIn("on-request", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_build_command_can_enable_search_without_dangerous_flags(self):
        adapter = CodexAdapter()
        task = AgentTask(id="1", prompt="search docs", project_path="C:\\repo", web_search_enabled=True)

        command = adapter.build_command(task)

        self.assertIn("--search", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_build_command_supports_extended_exec_flags_from_settings(self):
        adapter = CodexAdapter()
        task = AgentTask(
            id="1",
            prompt="fix",
            project_path="C:\\repo",
            sandbox="danger-full-access",
            add_dirs=["C:\\shared"],
            images=["C:\\img.png"],
            model_settings={
                "oss": True,
                "local_provider": "ollama",
                "skip_git_repo_check": True,
                "ephemeral": True,
                "ignore_user_config": True,
                "ignore_rules": True,
                "color": "never",
                "enable_features": ["plugins"],
                "disable_features": ["goals"],
                "config_overrides": ["model_provider=\"oss\""],
            },
            tool_settings={
                "output_schema": "C:\\schema.json",
                "output_last_message": "C:\\last.txt",
            },
        )

        command = adapter.build_command(task)

        self.assertIn("danger-full-access", command)
        self.assertIn("--oss", command)
        self.assertIn("--local-provider", command)
        self.assertIn("ollama", command)
        self.assertIn("--skip-git-repo-check", command)
        self.assertIn("--ephemeral", command)
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertIn("--image", command)
        self.assertIn("C:\\img.png", command)
        self.assertIn("--output-schema", command)
        self.assertIn("C:\\schema.json", command)
        self.assertIn("--output-last-message", command)
        self.assertIn("C:\\last.txt", command)
        self.assertIn("--enable", command)
        self.assertIn("plugins", command)
        self.assertIn("--disable", command)
        self.assertIn("goals", command)
        self.assertIn("--config", command)

    def test_extract_session_id_ignores_agent_message_item_ids(self):
        adapter = CodexAdapter()

        session_id = adapter._extract_session_id(
            {
                "type": "item.completed",
                "item": {"id": "item_0", "type": "agent_message", "text": "Pong"},
            }
        )

        self.assertEqual(session_id, "")

    def test_agent_message_completed_is_assistant_preview(self):
        adapter = CodexAdapter()
        task = AgentTask(id="1", prompt="ping", project_path="C:\\repo")
        payload = {
            "type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": "Pong"},
        }

        event = adapter._agent_event_from_payload(payload, "Pong", task)

        self.assertEqual(event.payload["kind"], "assistant_preview")
        self.assertEqual(event.message, "Pong")

    def test_reasoning_mentions_files_without_becoming_diff(self):
        adapter = CodexAdapter()
        task = AgentTask(id="1", prompt="ping", project_path="C:\\repo")
        payload = {
            "type": "item.completed",
            "item": {"id": "item_1", "type": "reasoning", "text": "I should inspect files before editing."},
        }

        event = adapter._agent_event_from_payload(payload, "I should inspect files before editing.", task)

        self.assertEqual(event.payload["kind"], "thinking")
        self.assertNotIn("additions", event.payload)

    def test_file_change_without_counts_does_not_fake_line_numbers(self):
        adapter = CodexAdapter()
        task = AgentTask(id="1", prompt="ping", project_path="C:\\repo")
        payload = {
            "type": "item.started",
            "item": {
                "id": "item_2",
                "type": "file_change",
                "changes": [
                    {"path": "frontend/app/chat-widget.tsx", "kind": "add"},
                    {"path": "frontend/app/layout.tsx", "kind": "update"},
                ],
            },
        }

        event = adapter._agent_event_from_payload(payload, "item.started", task)

        self.assertEqual(event.payload["kind"], "diff")
        self.assertEqual(event.message, "Editing chat-widget.tsx")
        self.assertFalse(event.payload["counts_known"])
        self.assertEqual(len(event.payload["files"]), 2)

    def test_selected_skills_are_added_as_explicit_prompt_context(self):
        adapter = CodexAdapter()
        task = AgentTask(
            id="1",
            prompt="zrob UI",
            project_path="C:\\repo",
            selected_skills=[{"id": "react-patterns", "name": "react-patterns", "description": "React guidance"}],
        )

        prompt = adapter._prompt_for_task(task)

        self.assertIn("$react-patterns", prompt)
        self.assertIn("React guidance", prompt)
        self.assertTrue(prompt.endswith("zrob UI"))

    def test_planning_mode_adds_non_mutating_prompt_instruction(self):
        adapter = CodexAdapter()
        task = AgentTask(
            id="1",
            prompt="zaplanuj migracje",
            project_path="C:\\repo",
            model_settings={"planning_mode": True},
        )

        prompt = adapter._prompt_for_task(task)

        self.assertIn("planning mode is enabled", prompt)
        self.assertIn("do not modify files", prompt)
        self.assertTrue(prompt.endswith("zaplanuj migracje"))

    def test_codex_adapter_returns_not_found_final_event(self):
        async def collect():
            with patch("devlink_cli.agents.adapters.codex.shutil.which", return_value=None):
                adapter = CodexAdapter()
                task = AgentTask(id="1", prompt="fix", project_path="C:\\repo")
                return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())

        self.assertEqual(events[-1].event_type, "final")
        self.assertEqual(events[-1].payload["status"], "failed")
        self.assertEqual(events[-1].payload["error_code"], "CODEX_NOT_FOUND")

    def test_codex_adapter_streams_jsonl_and_succeeds(self):
        fake_process = FakeProcess(
            stdout_lines=['{"type":"item.completed","message":"changed file"}\n'],
            exit_code=0,
        )

        async def collect():
            async def fake_create_subprocess_exec(*args, **kwargs):
                return fake_process

            with (
                patch("devlink_cli.agents.adapters.codex.shutil.which", return_value="codex"),
                patch("devlink_cli.agents.adapters.codex.asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
            ):
                adapter = CodexAdapter()
                task = AgentTask(id="1", prompt="fix login", project_path="C:\\repo")
                return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())

        self.assertEqual(fake_process.stdin.content, b"fix login")
        self.assertTrue(fake_process.stdin.closed)
        self.assertTrue(any(event.event_type == "agent_event" for event in events))
        self.assertEqual(events[-1].payload["status"], "succeeded")
        self.assertIn("changed file", events[-1].message)

    def test_codex_adapter_normalizes_file_patch_event_counts(self):
        patch_text = "\n".join(
            [
                "*** Begin Patch",
                "*** Update File: apps/mobile/src/components/codexHub/CodexHubModal.tsx",
                "@@",
                "-old line",
                "+new line",
                "+another line",
                "*** End Patch",
            ]
        )
        fake_process = FakeProcess(
            stdout_lines=[
                json.dumps(
                    {
                        "type": "item.completed",
                        "payload": {
                            "type": "tool_call",
                            "name": "apply_patch",
                            "arguments": patch_text,
                        },
                    }
                )
                + "\n"
            ],
            exit_code=0,
        )

        async def collect():
            async def fake_create_subprocess_exec(*args, **kwargs):
                return fake_process

            with (
                patch("devlink_cli.agents.adapters.codex.shutil.which", return_value="codex"),
                patch("devlink_cli.agents.adapters.codex.asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
            ):
                adapter = CodexAdapter()
                task = AgentTask(id="1", prompt="fix hub", project_path="C:\\repo")
                return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())
        diff_events = [event for event in events if event.payload.get("kind") == "diff"]

        self.assertEqual(len(diff_events), 1)
        payload = diff_events[0].payload
        self.assertEqual(payload["file_name"], "CodexHubModal.tsx")
        self.assertEqual(payload["additions"], 2)
        self.assertEqual(payload["deletions"], 1)
        self.assertEqual(diff_events[0].message, "Editing CodexHubModal.tsx +2 -1")

    def test_codex_adapter_normalizes_structured_file_edit_payload(self):
        fake_process = FakeProcess(
            stdout_lines=[
                json.dumps(
                    {
                        "type": "codex.file.patch",
                        "files": [
                            {"path": "apps/mobile/src/A.tsx", "additions": 4, "deletions": 1},
                            {"path": "apps/mobile/src/B.tsx", "additions": 2, "deletions": 3},
                        ],
                    }
                )
                + "\n"
            ],
            exit_code=0,
        )

        async def collect():
            async def fake_create_subprocess_exec(*args, **kwargs):
                return fake_process

            with (
                patch("devlink_cli.agents.adapters.codex.shutil.which", return_value="codex"),
                patch("devlink_cli.agents.adapters.codex.asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
            ):
                adapter = CodexAdapter()
                task = AgentTask(id="1", prompt="fix hub", project_path="C:\\repo")
                return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())
        diff_event = next(event for event in events if event.payload.get("kind") == "diff")

        self.assertEqual(diff_event.payload["file_name"], "A.tsx")
        self.assertEqual(diff_event.payload["additions"], 6)
        self.assertEqual(diff_event.payload["deletions"], 4)
        self.assertEqual(len(diff_event.payload["files"]), 2)

    def test_codex_adapter_final_prefers_assistant_message_and_appends_edited_files(self):
        patch_text = "\n".join(
            [
                "*** Begin Patch",
                "*** Update File: frontend/app/chat-widget.tsx",
                "@@",
                "-old line",
                "+new line",
                "+another line",
                "*** End Patch",
            ]
        )
        fake_process = FakeProcess(
            stdout_lines=[
                json.dumps({"type": "item.completed", "item": {"type": "reasoning", "text": "Thinking about files."}}) + "\n",
                json.dumps({"type": "item.completed", "payload": {"type": "tool_call", "name": "apply_patch", "arguments": patch_text}}) + "\n",
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Done."}}) + "\n",
            ],
            exit_code=0,
        )

        async def collect():
            async def fake_create_subprocess_exec(*args, **kwargs):
                return fake_process

            with (
                patch("devlink_cli.agents.adapters.codex.shutil.which", return_value="codex"),
                patch("devlink_cli.agents.adapters.codex.asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
            ):
                adapter = CodexAdapter()
                task = AgentTask(id="1", prompt="fix hub", project_path="C:\\repo")
                return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())
        final = events[-1]

        self.assertEqual(final.event_type, "final")
        self.assertTrue(final.message.startswith("Done."))
        self.assertIn("Edited files:", final.message)
        self.assertIn("frontend/app/chat-widget.tsx (+2 -1)", final.message)
        self.assertNotIn("Thinking about files", final.message)
        self.assertEqual(final.payload["additions"], 2)
        self.assertEqual(final.payload["deletions"], 1)

    def test_codex_adapter_emits_usage_limits_event_from_token_count(self):
        fake_process = FakeProcess(
            stdout_lines=[
                '{"type":"event_msg","payload":{"type":"token_count","rate_limits":{"primary":{"used_percent":19,"window_minutes":300,"resets_at":1778958549},"secondary":{"used_percent":87,"window_minutes":10080,"resets_at":1779465600},"plan_type":"plus","rate_limit_reached_type":null}}}\n'
            ],
            exit_code=0,
        )

        async def collect():
            async def fake_create_subprocess_exec(*args, **kwargs):
                return fake_process

            with (
                patch("devlink_cli.agents.adapters.codex.shutil.which", return_value="codex"),
                patch("devlink_cli.agents.adapters.codex.asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
            ):
                adapter = CodexAdapter()
                task = AgentTask(id="1", prompt="ping", project_path="C:\\repo")
                return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())
        usage_events = [event for event in events if event.payload.get("kind") == "usage_limits"]

        self.assertEqual(len(usage_events), 1)
        self.assertEqual(usage_events[0].payload["codex_usage_limits"]["five_hour"]["used_percent"], 19.0)
        self.assertEqual(usage_events[0].payload["codex_usage_limits"]["weekly"]["used_percent"], 87.0)

    def test_codex_adapter_streams_stderr_and_fails_on_exit_code(self):
        fake_process = FakeProcess(stderr_lines=["boom\n"], exit_code=1)

        async def collect():
            async def fake_create_subprocess_exec(*args, **kwargs):
                return fake_process

            with (
                patch("devlink_cli.agents.adapters.codex.shutil.which", return_value="codex"),
                patch("devlink_cli.agents.adapters.codex.asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
            ):
                adapter = CodexAdapter()
                task = AgentTask(id="1", prompt="fix", project_path="C:\\repo")
                return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())

        self.assertTrue(any(event.event_type == "stderr" for event in events))
        self.assertEqual(events[-1].payload["status"], "failed")
        self.assertEqual(events[-1].payload["error_code"], "CODEX_EXIT_CODE")

    def test_codex_adapter_filters_noisy_html_stderr(self):
        fake_process = FakeProcess(stderr_lines=["<html>\n", "2026 WARN useful warning\n"], exit_code=1)

        async def collect():
            async def fake_create_subprocess_exec(*args, **kwargs):
                return fake_process

            with (
                patch("devlink_cli.agents.adapters.codex.shutil.which", return_value="codex"),
                patch("devlink_cli.agents.adapters.codex.asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
            ):
                adapter = CodexAdapter()
                task = AgentTask(id="1", prompt="fix", project_path="C:\\repo")
                return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())
        stderr_messages = [event.message for event in events if event.event_type == "stderr"]

        self.assertEqual(stderr_messages, ["2026 WARN useful warning"])

    def test_codex_adapter_times_out_and_kills_process(self):
        fake_process = FakeProcess(hang=True)

        async def collect():
            async def fake_create_subprocess_exec(*args, **kwargs):
                return fake_process

            with (
                patch("devlink_cli.agents.adapters.codex.shutil.which", return_value="codex"),
                patch("devlink_cli.agents.adapters.codex.asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
            ):
                adapter = CodexAdapter()
                adapter.timeout_seconds = 0.01
                task = AgentTask(id="1", prompt="fix", project_path="C:\\repo")
                return [event async for event in adapter.run(task)]

        events = asyncio.run(collect())

        self.assertTrue(fake_process.killed)
        self.assertEqual(events[-1].payload["status"], "timed_out")


class DaemonCancellationTests(unittest.TestCase):
    def test_cancel_watcher_prevents_finish_task(self):
        class WaitingAdapter:
            async def run(self, task):
                while not task.cancel_event.is_set():
                    await asyncio.sleep(0.001)
                raise AgentCanceled("cancel")
                yield

        class FakeClient:
            def __init__(self):
                self.finished = False

            async def post_task_event(self, *args, **kwargs):
                return {}

            async def finish_task(self, *args, **kwargs):
                self.finished = True
                return {}

            async def task_status(self, task_id):
                return {"status": "canceled"}

        async def fast_watch(client, task_id, cancel_event):
            cancel_event.set()

        async def run():
            client = FakeClient()
            task_payload = {
                "id": "task-1",
                "prompt": "fix",
                "project_path": "C:\\repo",
                "agent_type": "codex",
                "session": "session-1",
                "codex_session_id": "codex-thread-1",
                "resume_mode": True,
            }
            with (
                patch("devlink_cli.daemon.AgentFactory.create", return_value=WaitingAdapter()),
                patch("devlink_cli.daemon.watch_task_cancellation", side_effect=fast_watch),
            ):
                await run_task(client, task_payload)
            return client

        client = asyncio.run(run())
        self.assertFalse(client.finished)

    def test_run_task_posts_final_event_before_finish(self):
        class FinalAdapter:
            async def run(self, task):
                yield AgentEvent(event_type="agent_event", message="thinking", payload={"kind": "thinking"})
                yield AgentEvent(event_type="final", message="pong", payload={"kind": "final", "status": "succeeded", "exit_code": 0})

        class FakeClient:
            def __init__(self):
                self.events = []
                self.finished = None

            async def post_task_event(self, task_id, event_type, message="", payload=None):
                self.events.append((event_type, message, payload or {}))
                return {}

            async def finish_task(self, *args, **kwargs):
                self.finished = kwargs
                return {}

            async def task_status(self, task_id):
                return {"status": "running"}

        async def run():
            client = FakeClient()
            task_payload = {
                "id": "task-1",
                "prompt": "ping",
                "project_path": "C:\\repo",
                "agent_type": "codex",
                "session": "session-1",
            }
            async def idle_watch(*args, **kwargs):
                await asyncio.Event().wait()

            with (
                patch("devlink_cli.daemon.AgentFactory.create", return_value=FinalAdapter()),
                patch("devlink_cli.daemon.watch_task_cancellation", side_effect=idle_watch),
            ):
                await run_task(client, task_payload)
            return client

        client = asyncio.run(run())
        self.assertEqual(client.events[-1][0], "final")
        self.assertEqual(client.events[-1][1], "pong")
        self.assertEqual(client.finished["final_output"], "pong")

    def test_sync_capabilities_posts_collected_payload(self):
        class FakeClient:
            def __init__(self):
                self.payload = None

            async def list_projects(self):
                return []

            async def post_capabilities(self, capabilities):
                self.payload = capabilities

        async def run():
            client = FakeClient()
            with patch("devlink_cli.daemon.collect_capabilities", return_value={"codex": {"available": True}}):
                await sync_capabilities(client)
            return client

        client = asyncio.run(run())
        self.assertEqual(client.payload, {"codex": {"available": True}})

    def test_execute_safe_mcp_list_action(self):
        with patch("devlink_cli.daemon.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "[]"
            run.return_value.stderr = ""

            result = execute_approval_action(
                {"command_id": "codex.mcp.list", "arguments": {"json": True}}
            )

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "[]")
        self.assertEqual(run.call_args.args[0][1:], ["mcp", "list", "--json"])

    def test_execute_capabilities_refresh_action_is_noop_success(self):
        result = execute_approval_action({"command_id": "codex.capabilities.refresh", "arguments": {}})

        self.assertEqual(result["exit_code"], 0)
        self.assertIn("Capabilities refresh", result["stdout"])

    def test_parse_mcp_json_and_features(self):
        servers = parse_mcp_servers('[{"name":"cloudflare-api","enabled":true}]')
        features = parse_features("plugins stable true\nmulti_agent stable false")

        self.assertEqual(servers[0]["name"], "cloudflare-api")
        self.assertEqual(features[0]["id"], "plugins")
        self.assertTrue(features[0]["enabled"])

    def test_parse_models_and_context_windows(self):
        raw = '{"models":[{"slug":"gpt-test","display_name":"GPT Test","context_window":1234,"supported_reasoning_levels":[{"effort":"low"}]}]}'

        models = parse_models(raw)
        windows = model_context_windows(raw)

        self.assertEqual(models[0]["id"], "gpt-test")
        self.assertEqual(models[0]["context_window"], 1234)
        self.assertEqual(windows["gpt-test"], 1234)

    def test_index_project_files_ignores_heavy_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.tsx").write_text("export {}", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "ignored.js").write_text("", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.py").write_text("", encoding="utf-8")
            (root / "build").mkdir()
            (root / "build" / "ignored.txt").write_text("", encoding="utf-8")

            files = index_project_files(root)

        relative_paths = {file["relative_path"] for file in files}
        self.assertIn("src/app.tsx", relative_paths)
        self.assertNotIn("node_modules/ignored.js", relative_paths)
        self.assertNotIn(".venv/ignored.py", relative_paths)
        self.assertNotIn("build/ignored.txt", relative_paths)

    def test_collect_capabilities_reports_model_diagnostics_and_project_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "main.py").write_text("print('ok')", encoding="utf-8")
            project = {"id": "project-1", "local_path": str(root)}
            raw_models = '{"models":[{"slug":"gpt-test","display_name":"GPT Test","context_window":2048}]}'
            with (
                patch("devlink_cli.codex_process.codex_version", return_value="codex 1"),
                patch("devlink_cli.codex_process.codex_debug_models", return_value=raw_models),
                patch("devlink_cli.codex_process.codex_mcp_list", return_value="[]"),
                patch("devlink_cli.codex_process.codex_features_list", return_value=""),
                patch("devlink_cli.codex_process.codex_login_status", return_value="logged in"),
            ):
                capabilities = collect_capabilities([project])

        self.assertEqual(capabilities["diagnostics"]["models_count"], 1)
        self.assertEqual(capabilities["model_context_windows"]["gpt-test"], 2048)
        self.assertEqual(capabilities["project_files"]["project-1"][0]["relative_path"], "main.py")


class CliDeviceSecurityTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_status_does_not_print_device_token(self):
        config = DevLinkConfig(
            device_id="device-1",
            device_token_fallback="super-secret-token",
            last_device_status="online",
            last_heartbeat_at="2026-05-15T10:00:00Z",
        )

        with patch("devlink_cli.main.load_config", return_value=config):
            result = self.runner.invoke(main.app, ["status"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Device token: present", result.output)
        self.assertNotIn("super-secret-token", result.output)

    def test_api_client_wraps_httpx_timeout_without_traceback(self):
        class TimeoutClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def request(self, *args, **kwargs):
                raise httpx.ReadTimeout("read timed out")

        async def run():
            config = DevLinkConfig(api_url="http://127.0.0.1:8000/api", device_id="device-1", device_token_fallback="token")
            client = DevLinkApiClient(config, timeout=0.01)
            with patch("devlink_cli.api_client.httpx.AsyncClient", TimeoutClient):
                await client.heartbeat()

        with self.assertRaises(DevLinkApiError) as ctx:
            asyncio.run(run())

        self.assertIn("API timeout during POST http://127.0.0.1:8000/api/cli/heartbeat/", str(ctx.exception))
        self.assertIsNone(ctx.exception.status_code)

    def test_connect_reports_revoked_device(self):
        async def fake_run_daemon(*args, **kwargs):
            raise DevLinkApiError("forbidden", status_code=403)

        config = DevLinkConfig(device_id="device-1", device_token_fallback="token")

        with (
            patch("devlink_cli.main.load_config", return_value=config),
            patch("devlink_cli.main.run_daemon", side_effect=fake_run_daemon),
        ):
            result = self.runner.invoke(main.app, ["connect", "--interval", "0.01"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Ten token jest stary", result.output)
        self.assertIn("devlink pair --force", result.output)
        self.assertIn("devlink projects add --path", result.output)

    def test_connect_accepts_api_url_override(self):
        called = {}

        async def fake_run_daemon(client, *args, **kwargs):
            called["api_url"] = client.config.api_url
            raise KeyboardInterrupt()

        config = DevLinkConfig(device_id="device-1", device_token_fallback="token", api_url="http://192.168.0.238:8000/api")

        with (
            patch("devlink_cli.main.load_config", return_value=config),
            patch("devlink_cli.main.run_daemon", side_effect=fake_run_daemon),
        ):
            result = self.runner.invoke(main.app, ["connect", "--api-url", "http://192.168.0.238:8000/api", "--interval", "0.01"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(called["api_url"], "http://192.168.0.238:8000/api")

    def test_pair_saves_device_token(self):
        saved = {}

        class FakeClient:
            def __init__(self, config):
                self.config = config

            async def pair(self, **kwargs):
                return {
                    "device": {"id": "device-1", "name": kwargs["name"]},
                    "device_token": "device-token",
                    "project_id": None,
                }

        def fake_store_device_token(device_id, token, config):
            saved["device_id"] = device_id
            saved["token"] = token
            saved["api_url"] = config.api_url
            return config

        with (
            patch("devlink_cli.main.load_config", return_value=DevLinkConfig()),
            patch("devlink_cli.main.DevLinkApiClient", FakeClient),
            patch("devlink_cli.main.store_device_token", side_effect=fake_store_device_token),
        ):
            result = self.runner.invoke(main.app, ["pair", "--code", "ABC123", "--name", "Laptop"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(saved["device_id"], "device-1")
        self.assertEqual(saved["token"], "device-token")
        self.assertIn("Paired device: Laptop", result.output)
        self.assertIn("Sparowano samo urzadzenie", result.output)

    def test_pair_force_replaces_existing_device_token(self):
        saved = {}

        class FakeClient:
            def __init__(self, config):
                self.config = config

            async def pair(self, **kwargs):
                return {
                    "device": {"id": "device-2", "name": kwargs["name"]},
                    "device_token": "new-device-token",
                    "project_id": None,
                }

        def fake_store_device_token(device_id, token, config):
            saved["device_id"] = device_id
            saved["token"] = token
            return config

        with (
            patch("devlink_cli.main.load_config", return_value=DevLinkConfig(device_id="old-device", device_token_fallback="old-token")),
            patch("devlink_cli.main.clear_config") as clear_config_mock,
            patch("devlink_cli.main.DevLinkApiClient", FakeClient),
            patch("devlink_cli.main.store_device_token", side_effect=fake_store_device_token),
        ):
            result = self.runner.invoke(main.app, ["pair", "--force", "--code", "ABC123", "--name", "Laptop"])

        self.assertEqual(result.exit_code, 0)
        clear_config_mock.assert_called_once()
        self.assertEqual(saved["device_id"], "device-2")
        self.assertEqual(saved["token"], "new-device-token")

    def test_projects_add_rejects_directory_without_git_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("devlink_cli.main.load_config", return_value=DevLinkConfig(device_id="device-1", device_token_fallback="token")):
                result = self.runner.invoke(main.app, ["projects", "add", "--path", tmp])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("repozytorium Git", result.output)

    def test_projects_add_existing_project_does_not_traceback(self):
        class FakeClient:
            def __init__(self, config):
                self.config = config

            async def register_project(self, *args, **kwargs):
                raise DevLinkApiError(
                    "API error 400: Ten katalog jest juz zarejestrowany dla tego urzadzenia.",
                    status_code=400,
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            with (
                patch("devlink_cli.main.load_config", return_value=DevLinkConfig(device_id="device-1", device_token_fallback="token")),
                patch("devlink_cli.main.DevLinkApiClient", FakeClient),
            ):
                result = self.runner.invoke(main.app, ["projects", "add", "--path", str(root), "--name", "Repo"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("already registered", result.output)
        self.assertNotIn("Traceback", result.output)

    def test_is_git_repository_accepts_git_directory_and_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            self.assertTrue(is_git_repository(str(root)))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").write_text("gitdir: ../actual.git", encoding="utf-8")
            self.assertTrue(is_git_repository(str(root)))

    def test_discover_codex_skills_reads_skill_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "react-patterns"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: react-patterns\ndescription: React guidance\n---\nUse React well.\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"DEVLINK_CODEX_SKILL_ROOTS": str(root)}):
                skills = discover_codex_skills(limit=5)

        self.assertEqual(skills[0]["id"], "react-patterns")
        self.assertEqual(skills[0]["description"], "React guidance")

    def test_projects_remove_calls_api(self):
        removed = {}

        class FakeClient:
            def __init__(self, config):
                self.config = config

            async def remove_project(self, project_id):
                removed["project_id"] = project_id

        with (
            patch("devlink_cli.main.load_config", return_value=DevLinkConfig(device_id="device-1", device_token_fallback="token")),
            patch("devlink_cli.main.DevLinkApiClient", FakeClient),
        ):
            result = self.runner.invoke(main.app, ["projects", "remove", "project-1"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(removed["project_id"], "project-1")
        self.assertIn("Project deactivated", result.output)

    def test_projects_list_prints_workspace_settings(self):
        class FakeClient:
            def __init__(self, config):
                self.config = config

            async def list_projects(self):
                return [
                    {
                        "id": "project-1",
                        "name": "Repo",
                        "local_path": "C:\\repo",
                        "is_active": True,
                        "default_sandbox": "workspace-write",
                        "default_approval_policy": "on-request",
                    }
                ]

        with (
            patch("devlink_cli.main.load_config", return_value=DevLinkConfig(device_id="device-1", device_token_fallback="token")),
            patch("devlink_cli.main.DevLinkApiClient", FakeClient),
        ):
            result = self.runner.invoke(main.app, ["projects", "list"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("sandbox=workspace-write", result.output)
        self.assertIn("approval=on-request", result.output)


if __name__ == "__main__":
    unittest.main()
