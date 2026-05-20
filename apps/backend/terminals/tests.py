from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from terminals.models import TerminalSession


class TerminalApiTests(APITestCase):
    def create_user(self, username: str):
        return get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="devlinkpass123",
        )

    def pair_device(self, user, name="Laptop", project_path="C:\\repo\\devlink"):
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
                "project_path": project_path,
                "project_name": name,
            },
            format="json",
        )
        self.assertEqual(pair_response.status_code, 201)

        self.client.force_authenticate(user=user)
        projects_response = self.client.get("/api/projects/")
        self.assertEqual(projects_response.status_code, 200)
        project_id = pair_response.data.get("project_id")
        project = next(project for project in projects_response.data if project["id"] == project_id)
        return {
            "device_token": pair_response.data["device_token"],
            "device_id": pair_response.data["device"]["id"],
            "project": project,
        }

    def test_terminal_create_rejects_foreign_project(self):
        owner = self.create_user("terminal_owner")
        other = self.create_user("terminal_other")
        paired = self.pair_device(owner)

        self.client.force_authenticate(user=other)
        response = self.client.post(
            "/api/terminal/sessions/",
            {"project_id": paired["project"]["id"]},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_terminal_create_rejects_cwd_outside_workspace(self):
        user = self.create_user("terminal_cwd")
        paired = self.pair_device(user)

        self.client.force_authenticate(user=user)
        response = self.client.post(
            "/api/terminal/sessions/",
            {"project_id": paired["project"]["id"], "cwd": "C:\\other"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_cli_claims_only_own_device_terminal(self):
        user = self.create_user("terminal_claim")
        paired = self.pair_device(user, name="Laptop A", project_path="C:\\repo\\a")
        other = self.pair_device(user, name="Laptop B", project_path="C:\\repo\\b")

        self.client.force_authenticate(user=user)
        create_response = self.client.post(
            "/api/terminal/sessions/",
            {"project_id": paired["project"]["id"]},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {other['device_token']}")
        wrong_device_response = self.client.get("/api/cli/terminal/sessions/next/")
        self.assertEqual(wrong_device_response.status_code, 204)

        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        claim_response = self.client.get("/api/cli/terminal/sessions/next/")
        self.assertEqual(claim_response.status_code, 200)
        self.assertEqual(claim_response.data["status"], "claimed")

    def test_terminal_input_events_and_kill_lifecycle(self):
        user = self.create_user("terminal_lifecycle")
        paired = self.pair_device(user)

        self.client.force_authenticate(user=user)
        create_response = self.client.post(
            "/api/terminal/sessions/",
            {"project_id": paired["project"]["id"], "cols": 100, "rows": 30},
            format="json",
        )
        terminal_id = create_response.data["id"]

        input_response = self.client.post(
            f"/api/terminal/sessions/{terminal_id}/input/",
            {"data": "pwd\r"},
            format="json",
        )
        self.assertEqual(input_response.status_code, 201)
        resize_response = self.client.post(
            f"/api/terminal/sessions/{terminal_id}/resize/",
            {"cols": 120, "rows": 32},
            format="json",
        )
        self.assertEqual(resize_response.status_code, 201)

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        inputs_response = self.client.get(f"/api/cli/terminal/sessions/{terminal_id}/input/")
        self.assertEqual(inputs_response.status_code, 200)
        self.assertEqual([item["kind"] for item in inputs_response.data], ["stdin", "resize"])

        event_response = self.client.post(
            f"/api/cli/terminal/sessions/{terminal_id}/events/",
            {"kind": "status", "data": "running", "payload": {"status": "running"}},
            format="json",
        )
        self.assertEqual(event_response.status_code, 201)
        output_response = self.client.post(
            f"/api/cli/terminal/sessions/{terminal_id}/events/",
            {"kind": "output", "data": "C:\\repo\\devlink", "stream": "stdout"},
            format="json",
        )
        self.assertEqual(output_response.status_code, 201)

        self.client.credentials()
        self.client.force_authenticate(user=user)
        kill_response = self.client.post(f"/api/terminal/sessions/{terminal_id}/kill/", {}, format="json")
        self.assertEqual(kill_response.status_code, 200)

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        exit_response = self.client.post(
            f"/api/cli/terminal/sessions/{terminal_id}/events/",
            {"kind": "exit", "data": "done", "exit_code": 0, "payload": {"status": "exited"}},
            format="json",
        )
        self.assertEqual(exit_response.status_code, 201)
        self.assertEqual(TerminalSession.objects.get(pk=terminal_id).status, TerminalSession.Status.KILLED)
