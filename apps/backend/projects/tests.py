from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from unittest.mock import patch

from devices.models import Device
from projects.models import Project
from tasks.models import Task


class ProjectWorkspaceTests(APITestCase):
    def create_user(self, username: str):
        return get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="devlinkpass123",
        )

    def pair_device(self, user, name="Laptop", project_path=None):
        self.client.force_authenticate(user=user)
        pairing_response = self.client.post("/api/pairing-codes/", {}, format="json")
        self.assertEqual(pairing_response.status_code, 201)

        self.client.force_authenticate(user=None)
        path = project_path or f"C:\\repo\\{name}"
        pair_response = self.client.post(
            "/api/cli/pair/",
            {
                "code": pairing_response.data["code"],
                "name": name,
                "platform": "Windows",
                "project_path": path,
                "project_name": f"{name} Repo",
            },
            format="json",
        )
        self.assertEqual(pair_response.status_code, 201)
        return {
            "device_token": pair_response.data["device_token"],
            "device_id": pair_response.data["device"]["id"],
            "project_id": pair_response.data["project_id"],
        }

    def test_project_defaults_are_safe(self):
        user = self.create_user("project_defaults")
        paired = self.pair_device(user)

        project = Project.objects.get(pk=paired["project_id"])

        self.assertEqual(project.default_model, "")
        self.assertEqual(project.default_profile, "")
        self.assertEqual(project.default_sandbox, Project.SandboxMode.WORKSPACE_WRITE)
        self.assertEqual(project.default_approval_policy, Project.ApprovalPolicy.ON_REQUEST)

    def test_user_cannot_see_other_users_project(self):
        owner = self.create_user("project_owner")
        stranger = self.create_user("project_stranger")
        paired = self.pair_device(owner)

        self.client.force_authenticate(user=stranger)
        list_response = self.client.get("/api/projects/")
        detail_response = self.client.get(f"/api/projects/{paired['project_id']}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data, [])
        self.assertEqual(detail_response.status_code, 404)

    def test_cli_only_sees_projects_for_its_device(self):
        user = self.create_user("two_devices")
        first = self.pair_device(user, name="First", project_path="C:\\repo\\first")
        second = self.pair_device(user, name="Second", project_path="C:\\repo\\second")

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {first['device_token']}")
        response = self.client.get("/api/cli/projects/")

        self.assertEqual(response.status_code, 200)
        listed_ids = {project["id"] for project in response.data}
        self.assertIn(first["project_id"], listed_ids)
        self.assertNotIn(second["project_id"], listed_ids)

    def test_cli_project_delete_deactivates_project(self):
        user = self.create_user("project_remove")
        paired = self.pair_device(user)

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        delete_response = self.client.delete(f"/api/cli/projects/{paired['project_id']}/")

        self.assertEqual(delete_response.status_code, 204)
        project = Project.objects.get(pk=paired["project_id"])
        self.assertFalse(project.is_active)

    def test_inactive_project_cannot_receive_mobile_or_cli_tasks(self):
        user = self.create_user("inactive_task")
        paired = self.pair_device(user)
        Project.objects.filter(pk=paired["project_id"]).update(is_active=False)

        self.client.force_authenticate(user=user)
        task_response = self.client.post(
            "/api/tasks/",
            {"project": paired["project_id"], "prompt": "run tests", "agent_type": Task.AgentType.SHELL},
            format="json",
        )

        self.assertEqual(task_response.status_code, 400)

    def test_project_api_rejects_dangerous_defaults(self):
        user = self.create_user("dangerous_defaults")
        paired = self.pair_device(user)

        self.client.force_authenticate(user=user)
        mobile_response = self.client.patch(
            f"/api/projects/{paired['project_id']}/",
            {"default_sandbox": "danger-full-access"},
            format="json",
        )

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        cli_response = self.client.patch(
            f"/api/cli/projects/{paired['project_id']}/",
            {"default_approval_policy": "never"},
            format="json",
        )

        self.assertEqual(mobile_response.status_code, 400)
        self.assertEqual(cli_response.status_code, 400)

    def test_duplicate_local_path_for_device_returns_400(self):
        user = self.create_user("duplicate_path")
        paired = self.pair_device(user, project_path="C:\\repo\\duplicate")

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        response = self.client.post(
            "/api/cli/projects/",
            {"name": "Duplicate", "local_path": "C:\\repo\\duplicate"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Project.objects.filter(device_id=paired["device_id"], local_path="C:\\repo\\duplicate").count(), 1)

    def test_cli_project_create_broadcasts_workspace_update(self):
        user = self.create_user("project_broadcast")
        paired = self.pair_device(user, project_path="C:\\repo\\initial")

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {paired['device_token']}")
        with patch("projects.views.broadcast_workspace_updated_for_device") as broadcast:
            response = self.client.post(
                "/api/cli/projects/",
                {"name": "Fizyka", "local_path": "C:\\repo\\fizyka"},
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        broadcast.assert_called_once()
        self.assertEqual(broadcast.call_args.kwargs["reason"], "project.created")

    def test_mobile_can_update_safe_project_settings_but_not_local_path(self):
        user = self.create_user("mobile_project_update")
        paired = self.pair_device(user, project_path="C:\\repo\\safe")

        self.client.force_authenticate(user=user)
        response = self.client.patch(
            f"/api/projects/{paired['project_id']}/",
            {
                "name": "Renamed",
                "local_path": "C:\\repo\\ignored",
                "default_sandbox": "read-only",
                "default_approval_policy": "untrusted",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        project = Project.objects.get(pk=paired["project_id"])
        self.assertEqual(project.name, "Renamed")
        self.assertEqual(project.local_path, "C:\\repo\\safe")
        self.assertEqual(project.default_sandbox, Project.SandboxMode.READ_ONLY)
        self.assertEqual(project.default_approval_policy, Project.ApprovalPolicy.UNTRUSTED)
