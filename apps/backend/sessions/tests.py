from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from devices.models import Device
from sessions.models import AgentSession, SessionMessage
from agents.models import ApprovalRequest
from tasks.models import Task, TaskEvent
from terminals.models import TerminalSession


class AgentSessionApiTests(APITestCase):
    def create_user(self, username: str):
        return get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="devlinkpass123",
        )

    def pair_device(self, user, name="Session Laptop"):
        self.client.force_authenticate(user=user)
        pairing_response = self.client.post("/api/pairing-codes/", {}, format="json")
        self.assertEqual(pairing_response.status_code, 201)

        self.client.force_authenticate(user=None)
        pair_response = self.client.post(
            "/api/cli/pair/",
            {
                "code": pairing_response.data["code"],
                "name": name,
                "platform": "Windows",
                "project_path": f"C:\\repo\\{name}",
                "project_name": f"{name} Repo",
            },
            format="json",
        )
        self.assertEqual(pair_response.status_code, 201)

        self.client.force_authenticate(user=user)
        projects_response = self.client.get("/api/projects/")
        self.assertEqual(projects_response.status_code, 200)
        return {
            "device_token": pair_response.data["device_token"],
            "device_id": pair_response.data["device"]["id"],
            "project": projects_response.data[0],
        }

    def create_session(self, user, project_id, title="Login work"):
        self.client.force_authenticate(user=user)
        response = self.client.post(
            "/api/sessions/",
            {"project": project_id, "title": title},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.data

    def test_user_cannot_see_other_users_sessions(self):
        owner = self.create_user("session_owner")
        stranger = self.create_user("session_stranger")
        owner_project = self.pair_device(owner, "Owner Session Laptop")["project"]
        stranger_project = self.pair_device(stranger, "Stranger Session Laptop")["project"]
        owner_session = self.create_session(owner, owner_project["id"])
        stranger_session = self.create_session(stranger, stranger_project["id"])

        self.client.force_authenticate(user=owner)
        list_response = self.client.get("/api/sessions/")
        self.assertEqual(list_response.status_code, 200)
        listed_ids = {session["id"] for session in list_response.data["results"]}
        self.assertIn(owner_session["id"], listed_ids)
        self.assertNotIn(stranger_session["id"], listed_ids)

        detail_response = self.client.get(f"/api/sessions/{stranger_session['id']}/")
        self.assertEqual(detail_response.status_code, 404)

    def test_workspace_bootstrap_includes_account_and_project_owner_context(self):
        user = self.create_user("bootstrap_context")
        paired = self.pair_device(user)

        self.client.force_authenticate(user=user)
        response = self.client.get("/api/workspace/bootstrap/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["account"]["username"], "bootstrap_context")
        self.assertEqual(response.data["devices"][0]["owner_username"], "bootstrap_context")
        self.assertEqual(response.data["projects"][0]["owner_username"], "bootstrap_context")
        self.assertEqual(response.data["projects"][0]["id"], paired["project"]["id"])

    def test_workspace_bootstrap_prefers_connected_project_over_offline_latest_session(self):
        user = self.create_user("bootstrap_connected_project")
        old_pair = self.pair_device(user, "Old Laptop")
        old_session = self.create_session(user, old_pair["project"]["id"], title="Old chat")
        Device.objects.filter(pk=old_pair["device_id"]).update(
            status=Device.Status.ONLINE,
            last_seen_at=timezone.now() - timedelta(minutes=10),
        )
        AgentSession.objects.filter(pk=old_session["id"]).update(last_activity_at=timezone.now())
        new_pair = self.pair_device(user, "Current Laptop")

        self.client.force_authenticate(user=user)
        response = self.client.get("/api/workspace/bootstrap/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["latest_session"])
        self.assertEqual(response.data["projects"][0]["id"], new_pair["project"]["id"])

    def test_closed_session_blocks_new_tasks(self):
        user = self.create_user("closed_session_user")
        project = self.pair_device(user)["project"]
        session = self.create_session(user, project["id"])

        close_response = self.client.post(f"/api/sessions/{session['id']}/close/", {}, format="json")
        self.assertEqual(close_response.status_code, 200)
        self.assertEqual(close_response.data["status"], "closed")

        task_response = self.client.post(
            "/api/tasks/",
            {"project": project["id"], "session": session["id"], "prompt": "continue", "agent_type": "codex"},
            format="json",
        )
        self.assertEqual(task_response.status_code, 400)

    def test_task_list_filters_by_session(self):
        user = self.create_user("session_filter_user")
        project = self.pair_device(user)["project"]
        first_session = self.create_session(user, project["id"], title="First")
        second_session = self.create_session(user, project["id"], title="Second")

        self.client.post(
            "/api/tasks/",
            {"project": project["id"], "session": first_session["id"], "prompt": "first", "agent_type": "codex"},
            format="json",
        )
        self.client.post(
            "/api/tasks/",
            {"project": project["id"], "session": second_session["id"], "prompt": "second", "agent_type": "codex"},
            format="json",
        )

        response = self.client.get(f"/api/tasks/?session={first_session['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(str(response.data["results"][0]["session"]), first_session["id"])

    def test_cli_next_payload_includes_session_resume_fields(self):
        user = self.create_user("resume_payload_user")
        paired = self.pair_device(user)
        session = self.create_session(user, paired["project"]["id"])
        AgentSession.objects.filter(pk=session["id"]).update(codex_session_id="codex-thread-1")

        self.client.post(
            "/api/tasks/",
            {"project": paired["project"]["id"], "session": session["id"], "prompt": "continue", "agent_type": "codex"},
            format="json",
        )

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        response = self.client.get("/api/cli/tasks/next/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["session"]), session["id"])
        self.assertEqual(response.data["codex_session_id"], "codex-thread-1")
        self.assertTrue(response.data["resume_mode"])

    def test_agent_event_updates_session_codex_id(self):
        user = self.create_user("event_session_user")
        paired = self.pair_device(user)
        session = self.create_session(user, paired["project"]["id"])
        task_response = self.client.post(
            "/api/tasks/",
            {"project": paired["project"]["id"], "session": session["id"], "prompt": "start", "agent_type": "codex"},
            format="json",
        )

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        event_response = self.client.post(
            f"/api/cli/tasks/{task_response.data['id']}/events/",
            {
                "event_type": "agent_event",
                "message": "thread started",
                "payload": {"type": "thread.started", "thread_id": "codex-thread-2"},
            },
            format="json",
        )
        self.assertEqual(event_response.status_code, 201)

        saved_session = AgentSession.objects.get(pk=session["id"])
        self.assertEqual(saved_session.codex_session_id, "codex-thread-2")

    def test_agent_message_item_id_does_not_replace_codex_thread_id(self):
        user = self.create_user("event_item_id_user")
        paired = self.pair_device(user)
        session = self.create_session(user, paired["project"]["id"])
        AgentSession.objects.filter(pk=session["id"]).update(codex_session_id="codex-thread-1")
        task_response = self.client.post(
            "/api/tasks/",
            {"project": paired["project"]["id"], "session": session["id"], "prompt": "ping", "agent_type": "codex"},
            format="json",
        )

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        event_response = self.client.post(
            f"/api/cli/tasks/{task_response.data['id']}/events/",
            {
                "event_type": "agent_event",
                "message": "Pong",
                "payload": {
                    "type": "item.completed",
                    "codex_session_id": "item_0",
                    "item": {"id": "item_0", "type": "agent_message", "text": "Pong"},
                },
            },
            format="json",
        )
        self.assertEqual(event_response.status_code, 201)

        saved_session = AgentSession.objects.get(pk=session["id"])
        self.assertEqual(saved_session.codex_session_id, "codex-thread-1")

    def test_fork_creates_child_session_without_copying_codex_id(self):
        user = self.create_user("fork_session_user")
        project = self.pair_device(user)["project"]
        parent = self.create_session(user, project["id"], title="Parent")
        AgentSession.objects.filter(pk=parent["id"]).update(codex_session_id="codex-thread-parent")

        response = self.client.post(f"/api/sessions/{parent['id']}/fork/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data["parent_session"]), parent["id"])
        self.assertEqual(str(response.data["project"]), project["id"])
        self.assertEqual(response.data["codex_session_id"], "")

    def test_session_message_endpoint_creates_user_message_and_task(self):
        user = self.create_user("chat_message_user")
        project = self.pair_device(user)["project"]
        session = self.create_session(user, project["id"])

        response = self.client.post(
            f"/api/sessions/{session['id']}/messages/",
            {
                "content": "napraw logowanie",
                "settings_overrides": {"model": "gpt-test", "sandbox": "read-only"},
                "selected_skill_ids": ["react-patterns"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"]["role"], "user")
        self.assertEqual(response.data["task"]["prompt"], "napraw logowanie")
        self.assertEqual(response.data["task"]["status"], "queued")
        saved_session = AgentSession.objects.get(pk=session["id"])
        self.assertEqual(saved_session.model, "gpt-test")
        self.assertEqual(saved_session.sandbox, "read-only")
        self.assertEqual(saved_session.selected_skills, ["react-patterns"])
        self.assertEqual(SessionMessage.objects.filter(session=saved_session, role="user").count(), 1)
        self.assertEqual(Task.objects.filter(session=saved_session).count(), 1)

    def test_session_message_endpoint_rejects_offline_device(self):
        user = self.create_user("offline_chat_user")
        paired = self.pair_device(user)
        session = self.create_session(user, paired["project"]["id"])
        Device.objects.filter(pk=paired["device_id"]).update(status=Device.Status.OFFLINE)

        response = self.client.post(
            f"/api/sessions/{session['id']}/messages/",
            {"content": "ping"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("device", response.data["details"])
        self.assertEqual(Task.objects.filter(session_id=session["id"]).count(), 0)

    def test_session_message_endpoint_rejects_stale_online_device(self):
        user = self.create_user("stale_chat_user")
        paired = self.pair_device(user)
        session = self.create_session(user, paired["project"]["id"])
        Device.objects.filter(pk=paired["device_id"]).update(
            status=Device.Status.ONLINE,
            last_seen_at=timezone.now() - timedelta(minutes=10),
        )

        response = self.client.post(
            f"/api/sessions/{session['id']}/messages/",
            {"content": "ping"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("device", response.data["details"])
        self.assertEqual(Task.objects.filter(session_id=session["id"]).count(), 0)

    def test_emergency_stop_cancels_active_tasks_and_kills_terminal(self):
        user = self.create_user("emergency_stop_user")
        paired = self.pair_device(user)
        session = self.create_session(user, paired["project"]["id"])

        message_response = self.client.post(
            f"/api/sessions/{session['id']}/messages/",
            {"content": "dlugi run"},
            format="json",
        )
        task_id = message_response.data["task"]["id"]

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        self.client.get("/api/cli/tasks/next/")
        self.client.post(f"/api/cli/tasks/{task_id}/start/", {}, format="json")

        self.client.credentials()
        self.client.force_authenticate(user=user)
        terminal_response = self.client.post(
            "/api/terminal/sessions/",
            {"project_id": paired["project"]["id"]},
            format="json",
        )
        terminal_id = terminal_response.data["id"]

        response = self.client.post(f"/api/sessions/{session['id']}/emergency-stop/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "stopped")
        self.assertIn(task_id, response.data["canceled_tasks"])
        self.assertIn(terminal_id, response.data["killed_terminals"])
        self.assertEqual(Task.objects.get(pk=task_id).status, Task.Status.CANCELED)
        self.assertEqual(TerminalSession.objects.get(pk=terminal_id).status, TerminalSession.Status.KILLED)

        second_response = self.client.post(f"/api/sessions/{session['id']}/emergency-stop/", {}, format="json")
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data["canceled_tasks"], [])

    def test_emergency_stop_rejects_foreign_session(self):
        owner = self.create_user("emergency_owner")
        stranger = self.create_user("emergency_stranger")
        project = self.pair_device(owner)["project"]
        session = self.create_session(owner, project["id"])

        self.client.force_authenticate(user=stranger)
        response = self.client.post(f"/api/sessions/{session['id']}/emergency-stop/", {}, format="json")

        self.assertEqual(response.status_code, 404)

    def test_session_settings_reject_dangerous_sandbox(self):
        user = self.create_user("dangerous_settings_user")
        project = self.pair_device(user)["project"]
        session = self.create_session(user, project["id"])

        response = self.client.patch(
            f"/api/sessions/{session['id']}/settings/",
            {"sandbox": "danger-full-access"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_session_attachment_endpoint_tracks_image_paths(self):
        user = self.create_user("attachment_user")
        project = self.pair_device(user)["project"]
        session = self.create_session(user, project["id"])

        response = self.client.post(
            f"/api/sessions/{session['id']}/attachments/",
            {"path": "C:\\repo\\shot.png", "type": "image"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("C:\\repo\\shot.png", response.data["images"])
        saved = AgentSession.objects.get(pk=session["id"])
        self.assertIn("C:\\repo\\shot.png", saved.tool_settings["images"])

    def test_branch_action_creates_approval_request(self):
        user = self.create_user("branch_approval_user")
        project = self.pair_device(user)["project"]

        response = self.client.post(
            f"/api/projects/{project['id']}/git/branch/",
            {"action": "switch", "branch": "codex/test", "dirty": True},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["action_type"], "git.branch.switch")
        self.assertEqual(response.data["risk_level"], "high")
        self.assertEqual(ApprovalRequest.objects.filter(project_id=project["id"]).count(), 1)

    def test_timeline_combines_messages_and_task_events(self):
        user = self.create_user("timeline_user")
        paired = self.pair_device(user)
        session = self.create_session(user, paired["project"]["id"])
        message_response = self.client.post(
            f"/api/sessions/{session['id']}/messages/",
            {"content": "uruchom testy"},
            format="json",
        )

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        event_response = self.client.post(
            f"/api/cli/tasks/{message_response.data['task']['id']}/events/",
            {"event_type": "stdout", "message": "pytest ok", "payload": {"line": "pytest ok"}},
            format="json",
        )
        self.assertEqual(event_response.status_code, 201)

        self.client.force_authenticate(user=user)
        self.client.credentials()
        timeline_response = self.client.get(f"/api/sessions/{session['id']}/timeline/")

        self.assertEqual(timeline_response.status_code, 200)
        kinds = [item["kind"] for item in timeline_response.data]
        self.assertIn("user_message", kinds)
        self.assertIn("queued", kinds)
        self.assertIn("terminal_stdout", kinds)

    def test_finish_creates_assistant_message(self):
        user = self.create_user("assistant_message_user")
        paired = self.pair_device(user)
        session = self.create_session(user, paired["project"]["id"])
        message_response = self.client.post(
            f"/api/sessions/{session['id']}/messages/",
            {"content": "dodaj endpoint"},
            format="json",
        )
        task_id = message_response.data["task"]["id"]

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        next_response = self.client.get("/api/cli/tasks/next/")
        self.assertEqual(next_response.status_code, 200)
        start_response = self.client.post(f"/api/cli/tasks/{task_id}/start/", {}, format="json")
        self.assertEqual(start_response.status_code, 200)
        finish_response = self.client.post(
            f"/api/cli/tasks/{task_id}/finish/",
            {"status": "succeeded", "final_output": "Gotowe.", "exit_code": 0},
            format="json",
        )

        self.assertEqual(finish_response.status_code, 200)
        assistant = SessionMessage.objects.get(session_id=session["id"], role="assistant")
        self.assertEqual(assistant.content, "Gotowe.")
        self.assertEqual(TaskEvent.objects.filter(task_id=task_id, event_type="final").count(), 1)

    def test_cli_next_payload_includes_session_settings_and_selected_skills(self):
        user = self.create_user("selected_skills_user")
        paired = self.pair_device(user)
        session = self.create_session(user, paired["project"]["id"])
        AgentSession.objects.filter(pk=session["id"]).update(
            model="gpt-test",
            sandbox="read-only",
            selected_skills=["skill-one"],
            web_search_enabled=True,
        )

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        capabilities_response = self.client.post(
            "/api/cli/capabilities/",
            {"skills": [{"id": "skill-one", "name": "skill-one", "description": "Test skill"}]},
            format="json",
        )
        self.assertEqual(capabilities_response.status_code, 200)

        self.client.force_authenticate(user=user)
        self.client.credentials()
        self.client.post(
            f"/api/sessions/{session['id']}/messages/",
            {"content": "uzyj skill"},
            format="json",
        )

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        response = self.client.get("/api/cli/tasks/next/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["default_model"], "gpt-test")
        self.assertEqual(response.data["default_sandbox"], "read-only")
        self.assertTrue(response.data["web_search_enabled"])
        self.assertEqual(response.data["selected_skills"][0]["id"], "skill-one")
