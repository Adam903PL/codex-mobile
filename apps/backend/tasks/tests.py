from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from devices.models import Device
from projects.models import Project
from tasks.models import Task


class DevLinkApiFlowTests(APITestCase):
    def create_user(self, username: str):
        return get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="devlinkpass123",
        )

    def pair_device(self, user, name="Test Laptop"):
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
        self.assertGreaterEqual(len(projects_response.data), 1)

        return {
            "device_token": pair_response.data["device_token"],
            "device_id": pair_response.data["device"]["id"],
            "project": projects_response.data[0],
        }

    def create_task(self, user, project_id, prompt="uruchom testy", agent_type="shell"):
        self.client.force_authenticate(user=user)
        response = self.client.post(
            "/api/tasks/",
            {"project": project_id, "prompt": prompt, "agent_type": agent_type},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.data

    def test_mobile_creates_task_and_cli_finishes_it(self):
        user = self.create_user("devlink_flow")
        paired = self.pair_device(user)
        Project.objects.filter(pk=paired["project"]["id"]).update(
            default_model="gpt-test",
            default_profile="school",
            default_sandbox="read-only",
            default_approval_policy="untrusted",
        )
        task = self.create_task(user, paired["project"]["id"])

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        next_task_response = self.client.get("/api/cli/tasks/next/")
        self.assertEqual(next_task_response.status_code, 200)
        self.assertEqual(next_task_response.data["status"], "claimed")
        self.assertEqual(next_task_response.data["default_model"], "gpt-test")
        self.assertEqual(next_task_response.data["default_profile"], "school")
        self.assertEqual(next_task_response.data["default_sandbox"], "read-only")
        self.assertEqual(next_task_response.data["default_approval_policy"], "untrusted")

        task_id = next_task_response.data["id"]
        status_response = self.client.get(f"/api/cli/tasks/{task_id}/")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.data["status"], "claimed")

        start_response = self.client.post(f"/api/cli/tasks/{task_id}/start/", {}, format="json")
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(start_response.data["status"], "running")

        event_response = self.client.post(
            f"/api/cli/tasks/{task_id}/events/",
            {"event_type": "stdout", "message": "test output", "payload": {"source": "test"}},
            format="json",
        )
        self.assertEqual(event_response.status_code, 201)

        finish_response = self.client.post(
            f"/api/cli/tasks/{task_id}/finish/",
            {"status": "succeeded", "final_output": "done", "exit_code": 0},
            format="json",
        )
        self.assertEqual(finish_response.status_code, 200)
        self.assertEqual(finish_response.data["status"], "succeeded")

        self.client.credentials()
        self.client.force_authenticate(user=user)
        events_response = self.client.get(f"/api/tasks/{task_id}/events/")
        self.assertEqual(events_response.status_code, 200)
        sequences = [event["sequence"] for event in events_response.data]
        self.assertEqual(sequences, list(range(1, len(sequences) + 1)))
        self.assertEqual(len(sequences), 5)

        saved_task = Task.objects.get(pk=task["id"])
        self.assertEqual(saved_task.status, Task.Status.SUCCEEDED)
        self.assertEqual(saved_task.final_output, "done")

    def test_usage_limits_event_updates_device_capabilities(self):
        user = self.create_user("usage_limits_user")
        paired = self.pair_device(user)
        task = self.create_task(user, paired["project"]["id"], agent_type="codex")

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        next_task_response = self.client.get("/api/cli/tasks/next/")
        self.assertEqual(next_task_response.status_code, 200)
        task_id = next_task_response.data["id"]
        usage_limits = {
            "five_hour": {"used_percent": 19, "remaining_percent": 81, "window_minutes": 300, "resets_at": "2026-05-16T21:00:00+00:00"},
            "weekly": {"used_percent": 87, "remaining_percent": 13, "window_minutes": 10080, "resets_at": "2026-05-23T21:00:00+00:00"},
            "source": "live_event",
            "observed_at": "2026-05-16T20:00:00+00:00",
            "plan_type": "plus",
            "rate_limit_reached_type": None,
        }

        event_response = self.client.post(
            f"/api/cli/tasks/{task_id}/events/",
            {"event_type": "agent_event", "message": "Usage limits updated", "payload": {"kind": "usage_limits", "codex_usage_limits": usage_limits}},
            format="json",
        )

        self.assertEqual(event_response.status_code, 201)
        device = Device.objects.get(pk=paired["device_id"])
        self.assertEqual(device.capabilities["codex_usage_limits"]["five_hour"]["used_percent"], 19)
        self.assertEqual(device.capabilities["codex_usage_limits"]["weekly"]["used_percent"], 87)
        self.assertEqual(device.capabilities["diagnostics"]["usage_limits_source"], "live_event")

    def test_cli_can_fetch_status_only_for_own_device_task(self):
        user = self.create_user("cli_status_owner")
        first = self.pair_device(user, name="First Device")
        second = self.pair_device(user, name="Second Device")
        task = self.create_task(user, first["project"]["id"])

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {second['device_token']}")
        other_device_response = self.client.get(f"/api/cli/tasks/{task['id']}/")
        self.assertEqual(other_device_response.status_code, 404)

        self.client.credentials(HTTP_AUTHORIZATION=f"Device {first['device_token']}")
        own_device_response = self.client.get(f"/api/cli/tasks/{task['id']}/")
        self.assertEqual(own_device_response.status_code, 200)
        self.assertEqual(own_device_response.data["status"], "queued")

    def test_user_cannot_see_other_users_tasks(self):
        owner = self.create_user("task_owner")
        stranger = self.create_user("task_stranger")
        paired_owner = self.pair_device(owner, name="Owner Laptop")
        paired_stranger = self.pair_device(stranger, name="Stranger Laptop")
        owner_task = self.create_task(owner, paired_owner["project"]["id"], prompt="owner task")
        stranger_task = self.create_task(stranger, paired_stranger["project"]["id"], prompt="stranger task")

        self.client.force_authenticate(user=owner)
        list_response = self.client.get("/api/tasks/")
        self.assertEqual(list_response.status_code, 200)
        listed_ids = {task["id"] for task in list_response.data["results"]}
        self.assertIn(owner_task["id"], listed_ids)
        self.assertNotIn(stranger_task["id"], listed_ids)

        detail_response = self.client.get(f"/api/tasks/{stranger_task['id']}/")
        self.assertEqual(detail_response.status_code, 404)

    def test_cli_with_invalid_token_cannot_fetch_tasks(self):
        self.client.credentials(HTTP_AUTHORIZATION="Device invalid-token")
        response = self.client.get("/api/cli/tasks/next/")
        self.assertIn(response.status_code, [401, 403])

    def test_revoked_device_cannot_use_cli_endpoints(self):
        user = self.create_user("revoked_user")
        paired = self.pair_device(user)
        Device.objects.filter(pk=paired["device_id"]).update(status=Device.Status.REVOKED)

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        response = self.client.get("/api/cli/tasks/next/")
        self.assertIn(response.status_code, [401, 403])

    def test_invalid_status_transition_returns_400(self):
        user = self.create_user("invalid_transition")
        paired = self.pair_device(user)
        task = self.create_task(user, paired["project"]["id"])

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        response = self.client.post(f"/api/cli/tasks/{task['id']}/start/", {}, format="json")
        self.assertEqual(response.status_code, 400)

        saved_task = Task.objects.get(pk=task["id"])
        self.assertEqual(saved_task.status, Task.Status.QUEUED)
        self.assertEqual(saved_task.events.count(), 0)

    def test_cancel_allowed_before_terminal_state_but_not_after_finish(self):
        user = self.create_user("cancel_user")
        paired = self.pair_device(user)
        queued_task = self.create_task(user, paired["project"]["id"], prompt="cancel queued")

        self.client.force_authenticate(user=user)
        cancel_response = self.client.post(f"/api/tasks/{queued_task['id']}/cancel/", {}, format="json")
        self.assertEqual(cancel_response.status_code, 200)
        self.assertEqual(cancel_response.data["status"], "canceled")

        running_task = self.create_task(user, paired["project"]["id"], prompt="finish then cancel")
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        next_task_response = self.client.get("/api/cli/tasks/next/")
        self.assertEqual(next_task_response.status_code, 200)
        self.assertEqual(next_task_response.data["id"], running_task["id"])
        self.client.post(f"/api/cli/tasks/{running_task['id']}/start/", {}, format="json")
        finish_response = self.client.post(
            f"/api/cli/tasks/{running_task['id']}/finish/",
            {"status": "succeeded", "final_output": "done", "exit_code": 0},
            format="json",
        )
        self.assertEqual(finish_response.status_code, 200)

        self.client.credentials()
        self.client.force_authenticate(user=user)
        second_cancel_response = self.client.post(f"/api/tasks/{running_task['id']}/cancel/", {}, format="json")
        self.assertEqual(second_cancel_response.status_code, 400)

    def test_mobile_can_cancel_running_task_and_cli_finish_is_rejected(self):
        user = self.create_user("running_cancel")
        paired = self.pair_device(user)
        task = self.create_task(user, paired["project"]["id"])

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        next_task_response = self.client.get("/api/cli/tasks/next/")
        self.assertEqual(next_task_response.status_code, 200)
        self.client.post(f"/api/cli/tasks/{task['id']}/start/", {}, format="json")

        self.client.credentials()
        self.client.force_authenticate(user=user)
        cancel_response = self.client.post(f"/api/tasks/{task['id']}/cancel/", {}, format="json")
        self.assertEqual(cancel_response.status_code, 200)
        self.assertEqual(cancel_response.data["status"], "canceled")

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        finish_response = self.client.post(
            f"/api/cli/tasks/{task['id']}/finish/",
            {"status": "succeeded", "final_output": "done", "exit_code": 0},
            format="json",
        )
        self.assertEqual(finish_response.status_code, 400)

        events_response = self.client.get(f"/api/cli/tasks/{task['id']}/")
        self.assertEqual(events_response.status_code, 200)
        saved_task = Task.objects.get(pk=task["id"])
        self.assertEqual(saved_task.status, Task.Status.CANCELED)

    def test_task_list_is_paginated_and_filterable(self):
        user = self.create_user("filter_user")
        paired = self.pair_device(user)
        project_id = paired["project"]["id"]
        project = Project.objects.get(pk=project_id)

        for index in range(21):
            Task.objects.create(
                owner=user,
                device=project.device,
                project=project,
                prompt=f"queued {index}",
                agent_type=Task.AgentType.SHELL,
            )
        Task.objects.create(
            owner=user,
            device=project.device,
            project=project,
            prompt="failed task",
            agent_type=Task.AgentType.SHELL,
            status=Task.Status.FAILED,
        )

        self.client.force_authenticate(user=user)
        list_response = self.client.get("/api/tasks/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 22)
        self.assertEqual(len(list_response.data["results"]), 20)

        filter_response = self.client.get("/api/tasks/?status=failed&ordering=status")
        self.assertEqual(filter_response.status_code, 200)
        self.assertEqual(filter_response.data["count"], 1)
        self.assertEqual(filter_response.data["results"][0]["status"], "failed")
