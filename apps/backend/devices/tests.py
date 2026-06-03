from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from agents.models import ApprovalRequest
from projects.models import Project
from sessions.models import AgentSession

from .models import Device, PairingCode


class DevicePairingSecurityTests(APITestCase):
    def create_user(self, username: str):
        return get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="devlinkpass123",
        )

    def create_pairing_code(self, user):
        self.client.force_authenticate(user=user)
        response = self.client.post("/api/pairing-codes/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        return response.data

    def pair_with_code(self, code: str, name: str = "Laptop", include_project: bool = True):
        self.client.force_authenticate(user=None)
        payload = {
            "code": code,
            "name": name,
            "platform": "Windows",
        }
        if include_project:
            payload.update(
                {
                    "project_path": f"C:\\repo\\{name}",
                    "project_name": f"{name} Repo",
                }
            )
        return self.client.post("/api/cli/pair/", payload, format="json")

    def test_pairing_code_expires_and_cannot_pair_device(self):
        user = self.create_user("expired_pairing")
        pairing = self.create_pairing_code(user)
        PairingCode.objects.filter(code=pairing["code"]).update(expires_at=timezone.now() - timedelta(minutes=1))

        response = self.pair_with_code(pairing["code"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Device.objects.count(), 0)

    def test_pairing_code_is_single_use(self):
        user = self.create_user("single_use_pairing")
        pairing = self.create_pairing_code(user)

        first_response = self.pair_with_code(pairing["code"], name="First")
        second_response = self.pair_with_code(pairing["code"], name="Second")

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(Device.objects.count(), 1)

    def test_new_pairing_code_invalidates_previous_active_code(self):
        user = self.create_user("rotated_pairing")
        first_pairing = self.create_pairing_code(user)
        second_pairing = self.create_pairing_code(user)

        first_response = self.pair_with_code(first_pairing["code"], name="Old")
        second_response = self.pair_with_code(second_pairing["code"], name="New")

        self.assertEqual(first_response.status_code, 400)
        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(Device.objects.count(), 1)

    def test_pairing_with_project_creates_project_for_same_owner_and_device(self):
        user = self.create_user("project_pairing")
        pairing = self.create_pairing_code(user)

        response = self.pair_with_code(pairing["code"])

        self.assertEqual(response.status_code, 201)
        device = Device.objects.get()
        project = device.projects.get()
        self.assertEqual(device.owner, user)
        self.assertEqual(project.owner, user)
        self.assertEqual(response.data["project_id"], str(project.id))

    def test_pairing_without_project_creates_device_only(self):
        user = self.create_user("device_only_pairing")
        pairing = self.create_pairing_code(user)

        response = self.pair_with_code(pairing["code"], include_project=False)

        self.assertEqual(response.status_code, 201)
        device = Device.objects.get()
        self.assertEqual(device.owner, user)
        self.assertEqual(device.projects.count(), 0)
        self.assertIsNone(response.data["project_id"])

    def test_user_cannot_see_or_revoke_other_users_device(self):
        owner = self.create_user("device_owner")
        stranger = self.create_user("device_stranger")
        pairing = self.create_pairing_code(owner)
        pair_response = self.pair_with_code(pairing["code"])
        device_id = pair_response.data["device"]["id"]

        self.client.force_authenticate(user=stranger)
        detail_response = self.client.get(f"/api/devices/{device_id}/")
        delete_response = self.client.delete(f"/api/devices/{device_id}/")

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertNotEqual(Device.objects.get(pk=device_id).status, Device.Status.REVOKED)

    def test_delete_revokes_device_and_cli_endpoints_reject_it(self):
        user = self.create_user("revoked_pairing")
        pairing = self.create_pairing_code(user)
        pair_response = self.pair_with_code(pairing["code"])
        device_id = pair_response.data["device"]["id"]
        device_token = pair_response.data["device_token"]

        self.client.force_authenticate(user=user)
        delete_response = self.client.delete(f"/api/devices/{device_id}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertEqual(Device.objects.get(pk=device_id).status, Device.Status.REVOKED)

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {device_token}")
        heartbeat_response = self.client.post("/api/cli/heartbeat/", {"busy": False}, format="json")
        tasks_response = self.client.get("/api/cli/tasks/next/")
        projects_response = self.client.post(
            "/api/cli/projects/",
            {"name": "Blocked", "local_path": "C:\\repo\\blocked"},
            format="json",
        )

        self.assertIn(heartbeat_response.status_code, [401, 403])
        self.assertIn(tasks_response.status_code, [401, 403])
        self.assertIn(projects_response.status_code, [401, 403])
        self.assertEqual(Device.objects.get(pk=device_id).status, Device.Status.REVOKED)

    def test_device_detail_contains_active_projects_and_project_count(self):
        user = self.create_user("device_detail")
        pairing = self.create_pairing_code(user)
        pair_response = self.pair_with_code(pairing["code"])
        device_id = pair_response.data["device"]["id"]

        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/devices/{device_id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["project_count"], 1)
        self.assertEqual(len(response.data["projects"]), 1)
        self.assertEqual(response.data["projects"][0]["name"], "Laptop Repo")

    def test_cli_can_sync_capabilities_and_user_can_read_them(self):
        user = self.create_user("capabilities_user")
        pairing = self.create_pairing_code(user)
        pair_response = self.pair_with_code(pairing["code"])
        device_id = pair_response.data["device"]["id"]
        device_token = pair_response.data["device_token"]

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {device_token}")
        sync_response = self.client.post(
            "/api/cli/capabilities/",
            {
                "codex": {"available": True, "version": "codex-cli 0.130.0"},
                "skills": [{"id": "skill-one", "name": "skill-one", "description": "Test skill"}],
            },
            format="json",
        )
        self.assertEqual(sync_response.status_code, 200)
        self.assertIsNotNone(sync_response.data["capabilities_updated_at"])

        self.client.force_authenticate(user=user)
        self.client.credentials()
        read_response = self.client.get(f"/api/devices/{device_id}/capabilities/")

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.data["capabilities"]["codex"]["version"], "codex-cli 0.130.0")
        self.assertEqual(read_response.data["capabilities"]["skills"][0]["id"], "skill-one")

    def test_heartbeat_reattaches_projects_from_stale_duplicate_pairing(self):
        user = self.create_user("reattach_projects")
        old_device = Device.objects.create(
            owner=user,
            name="Laptop",
            platform="Windows-11",
            status=Device.Status.ONLINE,
            token_hash="old-token",
            last_seen_at=timezone.now() - timedelta(minutes=10),
        )
        project = Project.objects.create(
            owner=user,
            device=old_device,
            name="Repo",
            local_path="C:\\repo\\app",
        )
        session = AgentSession.objects.create(
            owner=user,
            device=old_device,
            project=project,
            title="Repo chat",
        )
        pairing = self.create_pairing_code(user)
        pair_response = self.pair_with_code(pairing["code"], name="Laptop", include_project=False)
        new_device_id = pair_response.data["device"]["id"]
        device_token = pair_response.data["device_token"]

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {device_token}")
        response = self.client.post("/api/cli/heartbeat/", {"busy": False}, format="json")

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(str(project.device_id), new_device_id)
        self.assertEqual(str(session.device_id), new_device_id)

    def test_user_can_queue_capabilities_refresh(self):
        user = self.create_user("capabilities_refresh_user")
        pairing = self.create_pairing_code(user)
        pair_response = self.pair_with_code(pairing["code"])
        device_id = pair_response.data["device"]["id"]

        self.client.force_authenticate(user=user)
        response = self.client.post(f"/api/devices/{device_id}/capabilities/refresh/", {}, format="json")

        self.assertEqual(response.status_code, 201)
        approval = ApprovalRequest.objects.get(device_id=device_id)
        self.assertEqual(approval.command_id, "codex.capabilities.refresh")
        self.assertEqual(approval.status, ApprovalRequest.Status.APPROVED)
