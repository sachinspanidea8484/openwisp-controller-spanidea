import json
import uuid
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now, timedelta
from packaging.version import parse as parse_version
from rest_framework import VERSION as REST_FRAMEWORK_VERSION
from rest_framework.exceptions import ErrorDetail
from swapper import load_model

from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_users.tests.test_api import AuthenticationMixin

from .. import settings as app_settings
from ..api.views import ListViewPagination
from ..commands import ORGANIZATION_ENABLED_COMMANDS
from .utils import CreateCommandMixin, CreateConnectionsMixin

Command = load_model("connection", "Command")
DeviceConnection = load_model("connection", "DeviceConnection")
command_qs = Command.objects.order_by("-created")
OrganizationUser = load_model("openwisp_users", "OrganizationUser")
Group = load_model("openwisp_users", "Group")


class TestCommandsAPI(TestCase, AuthenticationMixin, CreateCommandMixin):
    url_namespace = "connection_api"

    def setUp(self):
        self.admin = self._get_admin()
        self.client.force_login(self.admin)
        self.device_conn = self._create_device_connection()
        self.device_id = self.device_conn.device.id

    def _get_path(self, url_name, *args, **kwargs):
        path = reverse(f"{self.url_namespace}:{url_name}", args=args)
        if not kwargs:
            return path
        query_params = []
        for key, value in kwargs.items():
            query_params.append(f"{key}={value}")
        query_string = "&".join(query_params)
        return f"{path}?{query_string}"

    def _get_device_not_found_error(self, device_id):
        return {"detail": ErrorDetail("Not found.", code="not_found")}

    @patch.object(ListViewPagination, "page_size", 3)
    def test_command_list_api(self):
        number_of_commands = 6
        url = self._get_path("device_command_list", self.device_id)
        for _ in range(number_of_commands):
            self._create_command(device_conn=self.device_conn)
        self.assertEqual(command_qs.count(), number_of_commands)

        response = self.client.get(url)

        with self.subTest('Test "page" query in object notification list view'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], number_of_commands)
            self.assertIn(
                self._get_path("device_command_list", self.device_id, page=2),
                response.data["next"],
            )
            self.assertEqual(response.data["previous"], None)
            self.assertEqual(len(response.data["results"]), 3)

            next_response = self.client.get(response.data["next"])
            self.assertEqual(next_response.status_code, 200)
            self.assertEqual(next_response.data["count"], number_of_commands)
            self.assertEqual(
                next_response.data["next"],
                None,
            )
            self.assertIn(
                self._get_path("device_command_list", self.device_id),
                next_response.data["previous"],
            )
            self.assertEqual(len(next_response.data["results"]), 3)

        with self.subTest('Test "page_size" query'):
            page_size = 3
            url = f"{url}?page_size={page_size}"
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], number_of_commands)
            self.assertIn(
                self._get_path(
                    "device_command_list",
                    self.device_id,
                    page=2,
                    page_size=page_size,
                ),
                response.data["next"],
            )
            self.assertEqual(response.data["previous"], None)
            self.assertEqual(len(response.data["results"]), page_size)

            next_response = self.client.get(response.data["next"])
            self.assertEqual(next_response.status_code, 200)
            self.assertEqual(next_response.data["count"], number_of_commands)
            self.assertEqual(next_response.data["next"], None)
            self.assertIn(
                self._get_path(
                    "device_command_list",
                    self.device_id,
                    page_size=page_size,
                ),
                next_response.data["previous"],
            )
            self.assertEqual(len(next_response.data["results"]), page_size)

        with self.subTest("Test individual result object"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            command_obj = response.data["results"][0]
            self.assertIn("id", command_obj)
            self.assertIn("status", command_obj)
            self.assertIn("type", command_obj)
            self.assertIn("input", command_obj)
            self.assertIn("output", command_obj)
            self.assertIn("device", command_obj)
            self.assertIn("connection", command_obj)

        with self.subTest("Test results ordering, recent first"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            created_list = [cmd["created"] for cmd in response.data["results"]]
            sorted_created_list = sorted(created_list, reverse=True)
            self.assertEqual(created_list, sorted_created_list)

    def test_command_create_api(self):
        def test_command_attributes(self, payload):
            self.assertEqual(command_qs.count(), 1)
            command_obj = command_qs.first()
            self.assertEqual(command_obj.device_id, self.device_id)
            self.assertEqual(command_obj.type, payload["type"])
            self.assertEqual(command_obj.input, payload["input"])
            command_qs.delete()

        url = self._get_path("device_command_list", self.device_id)

        with self.subTest('Test "reboot" command'):
            payload = {
                "type": "reboot",
                "input": None,
            }
            response = self.client.post(
                url,
                data=payload,
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            test_command_attributes(self, payload)

        with self.subTest('Test "reset_password" command'):
            payload = {
                "type": "change_password",
                "input": {"password": "ass@1234", "confirm_password": "Pass@1234"},
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            test_command_attributes(self, payload)

        with self.subTest('Test "custom" command'):
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            test_command_attributes(self, payload)

    # for ensuring that only related connections are shown
    def test_available_connections(self):
        device = self._create_device(
            name="default.test.device2", mac_address="12:23:34:45:56:67"
        )
        self._create_config(device=device)
        credentials_2 = self._create_credentials(name="Test Credentials 2")
        device_conn2 = self._create_device_connection(
            device=device, credentials=credentials_2
        )
        url = self._get_path("device_command_list", self.device_id)
        response = self.client.get(url, {"format": "api"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.device_conn.id))
        self.assertNotContains(response, device_conn2.id)

    def test_command_details_api(self):
        command_obj = self._create_command(device_conn=self.device_conn)
        url = self._get_path("device_command_details", self.device_id, command_obj.id)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(command_obj.id))
        self.assertEqual(response.data["status"], command_obj.status)
        self.assertEqual(response.data["input"], command_obj.input_data)
        self.assertEqual(response.data["output"], command_obj.output)
        self.assertEqual(response.data["device"], str(command_obj.device_id))
        self.assertEqual(response.data["connection"], str(command_obj.connection_id))
        # These are hard coded because API reverts more verbose response
        self.assertEqual(response.data["type"], "Custom commands")

    def test_bearer_authentication(self):
        self.client.logout()
        command_obj = self._create_command(device_conn=self.device_conn)
        token = self._obtain_auth_token(username="admin", password="tester")

        with self.subTest("Test creating command"):
            url = self._get_path("device_command_list", self.device_id)
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url,
                data=payload,
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("id", response.data)

        with self.subTest("Test retrieving command"):
            url = self._get_path(
                "device_command_details", self.device_id, command_obj.id
            )
            response = self.client.get(
                url,
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("id", response.data)

        with self.subTest("Test listing command"):
            url = self._get_path("device_command_list", self.device_id)
            response = self.client.get(
                url,
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data["results"]), 2)

    def test_endpoints_for_non_existent_device(self):
        device_id = uuid.uuid4()
        device_not_found = self._get_device_not_found_error(device_id)

        with self.subTest("Test listing commands"):
            url = self._get_path("device_command_list", device_id)
            response = self.client.get(
                url,
            )
            self.assertEqual(response.status_code, 404)
            self.assertDictEqual(response.data, device_not_found)

        with self.subTest("Test creating commands"):
            url = self._get_path("device_command_list", device_id)
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url, data=payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 404)
            self.assertDictEqual(response.data, device_not_found)

        with self.subTest("Test retrieving commands"):
            url = self._get_path("device_command_details", device_id, uuid.uuid4())
            response = self.client.get(
                url,
            )
            self.assertEqual(response.status_code, 404)
            self.assertDictEqual(response.data, device_not_found)

    def test_endpoints_for_deactivated_device(self):
        self.device_conn.device.deactivate()

        with self.subTest("Test listing commands"):
            url = self._get_path("device_command_list", self.device_id)
            response = self.client.get(
                url,
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test creating commands"):
            url = self._get_path("device_command_list", self.device_id)
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url, data=payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test retrieving commands"):
            command = self._create_command(device_conn=self.device_conn)
            url = self._get_path("device_command_details", self.device_id, command.id)
            response = self.client.get(
                url,
            )
            self.assertEqual(response.status_code, 200)

    def test_non_superuser(self):
        list_url = self._get_path("device_command_list", self.device_id)
        command = self._create_command(device_conn=self.device_conn)
        device = command.device

        with self.subTest("Test with unauthenticated user"):
            self.client.logout()
            response = self.client.get(list_url)
            self.assertEqual(response.status_code, 401)

        with self.subTest("Test with organization member"):
            org_user = self._create_org_user(is_admin=True)
            org_user.user.groups.add(Group.objects.get(name="Operator"))
            self.client.force_login(org_user.user)
            self.assertEqual(device.organization, org_user.organization)

            response = self.client.get(list_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)

        with self.subTest("Test with org member of different org"):
            org2 = self._create_org(name="org2", slug="org2")
            org2_user = self._create_user(username="org2user", email="user@org2.com")
            self._create_org_user(organization=org2, user=org2_user, is_admin=True)
            self.client.force_login(org2_user)
            org2_user.groups.add(Group.objects.get(name="Operator"))

            response = self.client.get(list_url)
            self.assertEqual(response.status_code, 404)

    def test_non_existent_command(self):
        url = self._get_path("device_command_list", self.device_id)
        with patch.dict(
            ORGANIZATION_ENABLED_COMMANDS,
            {str(self.device_conn.device.organization_id): ("reboot",)},
        ):
            payload = {
                "type": "custom",
                "input": {"command": "echo test"},
            }
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                '"custom" is not a valid choice.',
                response.data["type"][0],
            )

    def test_create_command_without_connection(self):
        device = self._create_device(
            name="default.test.device2", mac_address="11:22:33:44:55:66"
        )
        url = self._get_path("device_command_list", device.pk)
        payload = {
            "type": "custom",
            "input": {"command": "echo test"},
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Device has no credentials assigned.",
            response.data["device"][0],
        )


class TestConnectionApi(
    TestAdminMixin, AuthenticationMixin, TestCase, CreateConnectionsMixin
):
    def setUp(self):
        super().setUp()
        self._login()

    def test_get_credentials_list(self):
        self._create_credentials()
        path = reverse("connection_api:credential_list")
        with self.assertNumQueries(4):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        with self.subTest("Check ordering of credentials"):
            cred_old = self._create_credentials(name="Old Credential")
            cred_old.created = now() - timedelta(days=1)
            cred_old.save()
            self._create_credentials(name="Newest Credential")
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            created_list = [cred["created"] for cred in response.data["results"]]
            sorted_created = sorted(created_list, reverse=True)
            self.assertEqual(created_list, sorted_created)

    def test_filter_credentials_list(self):
        cred_1 = self._create_credentials(name="Credential One")
        org1 = self._create_org(name="org1")
        cred_2 = self._create_credentials(name="Credential Two", organization=org1)
        change_perm = Permission.objects.filter(codename="change_credentials")
        user = self._get_user()
        user.user_permissions.add(*change_perm)
        OrganizationUser.objects.create(user=user, organization=org1, is_admin=True)
        self.client.force_login(user)
        path = reverse("connection_api:credential_list")
        with self.assertNumQueries(6):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertContains(response, cred_2.id)
        self.assertNotContains(response, cred_1.id)

    def test_post_credential_list(self):
        path = reverse("connection_api:credential_list")
        data = {
            "connector": "openwisp_controller.connection.connectors.ssh.Ssh",
            "name": "Change Test credentials",
            "organization": self._get_org().pk,
            "auto_add": False,
            "params": {"username": "roOT", "password": "Pa$$w0Rd", "port": 22},
        }
        with self.assertNumQueries(8):
            response = self.client.post(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_get_credential_detail(self):
        cred = self._create_credentials()
        path = reverse("connection_api:credential_detail", args=(cred.pk,))
        with self.assertNumQueries(3):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_put_credential_detail(self):
        org1 = self._get_org()
        cred = self._create_credentials()
        path = reverse("connection_api:credential_detail", args=(cred.pk,))
        data = {
            "connector": "openwisp_controller.connection.connectors.ssh.Ssh",
            "name": "Change Test credentials",
            "organization": org1.pk,
            "auto_add": False,
            "params": {
                "username": "root_change",
                "password": "passwordchange",
                "port": 22,
            },
        }
        expected_queries = (
            9 if parse_version(REST_FRAMEWORK_VERSION) >= parse_version("3.15") else 8
        )
        with self.assertNumQueries(expected_queries):
            response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], data["name"])
        self.assertEqual(response.data["organization"], data["organization"])
        self.assertEqual(
            response.data["params"]["username"], data["params"]["username"]
        )
        self.assertEqual(
            response.data["params"]["password"], data["params"]["password"]
        )

    def test_patch_credential_detail(self):
        cred = self._create_credentials()
        path = reverse("connection_api:credential_detail", args=(cred.pk,))
        data = {"name": "Change Test credentials"}
        with self.assertNumQueries(8):
            response = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Change Test credentials")

    def test_delete_credential_detail(self):
        cred = self._create_credentials()
        path = reverse("connection_api:credential_detail", args=(cred.pk,))
        with self.assertNumQueries(5):
            response = self.client.delete(path)
        self.assertEqual(response.status_code, 204)

    def test_get_deviceconnection_list(self):
        d1 = self._create_device()
        path = reverse("connection_api:deviceconnection_list", args=(d1.pk,))
        with self.assertNumQueries(4):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        with self.subTest("Check ordering of device connections"):
            self._create_config(device=d1)
            creds = [self._create_credentials(name=f"Cred {i}") for i in range(3)]
            creds[0].created = now() - timedelta(days=1)
            creds[0].save()
            for cred in creds:
                DeviceConnection.objects.create(device=d1, credentials=cred)
            response = self.client.get(path)
            print(response.data)
            self.assertEqual(response.status_code, 200)
            created_list = [conn["created"] for conn in response.data["results"]]
            sorted_created = sorted(created_list, reverse=True)
            self.assertEqual(created_list, sorted_created)

    def test_post_deviceconnection_list(self):
        d1 = self._create_device()
        self._create_config(device=d1)
        path = reverse("connection_api:deviceconnection_list", args=(d1.pk,))
        data = {
            "credentials": self._get_credentials().pk,
            "update_strategy": app_settings.UPDATE_STRATEGIES[0][0],
            "enabled": True,
            "failure_reason": "",
        }
        with self.assertNumQueries(13):
            response = self.client.post(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_post_deviceconenction_with_no_config_device(self):
        d1 = self._create_device()
        path = reverse("connection_api:deviceconnection_list", args=(d1.pk,))
        data = {
            "credentials": self._get_credentials().pk,
            "update_strategy": "",
            "enabled": True,
            "failure_reason": "",
        }
        with self.assertNumQueries(13):
            response = self.client.post(path, data, content_type="application/json")
        error_msg = """
            the update strategy can be determined automatically only if
            the device has a configuration specified, because it is
            inferred from the configuration backend. Please select
            the update strategy manually.
        """
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            " ".join(error_msg.split()), response.data["update_strategy"][0].title()
        )

    def test_get_deviceconnection_detail(self):
        dc = self._create_device_connection()
        d1 = dc.device.id
        path = reverse("connection_api:deviceconnection_detail", args=(d1, dc.pk))
        with self.assertNumQueries(5):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

    def test_put_devceconnection_detail(self):
        dc = self._create_device_connection()
        d1 = dc.device.id
        path = reverse("connection_api:deviceconnection_detail", args=(d1, dc.pk))
        self.assertEqual(dc.update_strategy, app_settings.UPDATE_STRATEGIES[0][0])
        data = {
            "credentials": self._get_credentials().pk,
            "update_strategy": app_settings.UPDATE_STRATEGIES[1][0],
            "enabled": False,
            "failure_reason": "",
        }
        with self.assertNumQueries(14):
            response = self.client.put(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["update_strategy"], app_settings.UPDATE_STRATEGIES[1][0]
        )
        self.assertEqual(response.data["credentials"], self._get_credentials().pk)

    def test_patch_deviceconnectoin_detail(self):
        dc = self._create_device_connection()
        d1 = dc.device.id
        path = reverse("connection_api:deviceconnection_detail", args=(d1, dc.pk))
        self.assertEqual(dc.update_strategy, app_settings.UPDATE_STRATEGIES[0][0])
        data = {"update_strategy": app_settings.UPDATE_STRATEGIES[1][0]}
        with self.assertNumQueries(13):
            response = self.client.patch(path, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["update_strategy"], app_settings.UPDATE_STRATEGIES[1][0]
        )

    def test_delete_deviceconnection_detail(self):
        dc = self._create_device_connection()
        d1 = dc.device.id
        path = reverse("connection_api:deviceconnection_detail", args=(d1, dc.pk))
        with self.assertNumQueries(10):
            response = self.client.delete(path)
        self.assertEqual(response.status_code, 204)

    def test_bearer_authentication(self):
        self.client.logout()
        token = self._obtain_auth_token(username="admin", password="tester")
        credentials = self._create_credentials(auto_add=True)
        device = self._create_config(organization=credentials.organization).device
        device_conn = device.deviceconnection_set.first()

        with self.subTest("Test CredentialListCreateView"):
            response = self.client.get(
                reverse("connection_api:credential_list"),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test CredentialDetailView"):
            response = self.client.get(
                reverse("connection_api:credential_detail", args=[credentials.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DeviceConnenctionListCreateView"):
            response = self.client.get(
                reverse("connection_api:deviceconnection_list", args=[device.id]),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test DeviceConnectionDetailView"):
            response = self.client.get(
                reverse(
                    "connection_api:deviceconnection_detail",
                    args=[device.id, device_conn.id],
                ),
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 200)

    def test_deactivated_device(self):
        credentials = self._create_credentials(auto_add=True)
        device = self._create_config(organization=credentials.organization).device
        device_conn = device.deviceconnection_set.first()
        create_api_path = reverse(
            "connection_api:deviceconnection_list", args=(device.pk,)
        )
        detail_api_path = reverse(
            "connection_api:deviceconnection_detail",
            args=[device.id, device_conn.id],
        )
        device.deactivate()

        with self.subTest("Test creating DeviceConnection"):
            response = self.client.post(
                create_api_path,
                data={
                    "credentials": credentials.pk,
                    "update_strategy": app_settings.UPDATE_STRATEGIES[0][0],
                    "enabled": True,
                    "failure_reason": "",
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test listing DeviceConnection"):
            response = self.client.get(
                create_api_path,
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test retrieving DeviceConnection detail"):
            response = self.client.get(
                detail_api_path,
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest("Test updating DeviceConnection"):
            response = self.client.put(
                detail_api_path,
                {
                    "credentials": credentials.pk,
                    "update_strategy": app_settings.UPDATE_STRATEGIES[1][0],
                    "enabled": False,
                    "failure_reason": "",
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 403)

            response = self.client.patch(
                detail_api_path, {"enabled": False}, content_type="application/json"
            )
            self.assertEqual(response.status_code, 403)

        with self.subTest("Test deleting DeviceConnection"):
            response = self.client.delete(
                detail_api_path,
            )
            self.assertEqual(response.status_code, 403)
