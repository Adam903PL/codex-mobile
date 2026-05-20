from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from agents.models import ApprovalRequest


class CodexActionApiTests(APITestCase):
    def create_user(self, username: str):
        return get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="devlinkpass123",
        )

    def pair_device(self, user):
        self.client.force_authenticate(user=user)
        pairing_response = self.client.post("/api/pairing-codes/", {}, format="json")
        self.assertEqual(pairing_response.status_code, 201)
        self.client.force_authenticate(user=None)
        pair_response = self.client.post(
            "/api/cli/pair/",
            {
                "code": pairing_response.data["code"],
                "name": "Laptop",
                "platform": "Windows",
                "project_path": "C:\\repo\\app",
                "project_name": "App",
            },
            format="json",
        )
        self.assertEqual(pair_response.status_code, 201)
        self.client.force_authenticate(user=user)
        project_response = self.client.get("/api/projects/")
        return pair_response.data["device_token"], pair_response.data["device"]["id"], project_response.data[0]["id"]

    def test_command_catalog_contains_mcp_and_plugin_commands(self):
        user = self.create_user("catalog_user")
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/codex/command-catalog/")

        self.assertEqual(response.status_code, 200)
        command_ids = {command["id"] for command in response.data["commands"]}
        self.assertIn("codex.mcp.list", command_ids)
        self.assertIn("codex.plugin.marketplace.add", command_ids)
        self.assertIn("codex.remote-control", command_ids)
        self.assertIn("codex.exec-server", command_ids)
        self.assertIn("codex.session.settings.update", command_ids)
        exec_command = next(command for command in response.data["commands"] if command["id"] == "codex.exec")
        arg_names = {arg["name"] for arg in exec_command["args_schema"]}
        self.assertIn("local_provider", arg_names)
        self.assertIn("output_last_message", arg_names)
        self.assertIn("enable", arg_names)
        self.assertTrue(response.data["slash_commands"])

    def test_safe_action_is_auto_approved_for_cli(self):
        user = self.create_user("safe_action_user")
        device_token, device_id, _project_id = self.pair_device(user)

        response = self.client.post(
            "/api/codex/actions/",
            {"command_id": "codex.mcp.list", "device": device_id, "arguments": {"json": True}},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "approved")
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {device_token}")
        next_response = self.client.get("/api/cli/actions/next/")
        self.assertEqual(next_response.status_code, 200)
        self.assertEqual(next_response.data["command_id"], "codex.mcp.list")

    def test_risky_action_requires_user_approval(self):
        user = self.create_user("risky_action_user")
        _device_token, device_id, _project_id = self.pair_device(user)

        response = self.client.post(
            "/api/codex/actions/",
            {"command_id": "codex.logout", "device": device_id},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(ApprovalRequest.objects.get(pk=response.data["id"]).command_id, "codex.logout")
