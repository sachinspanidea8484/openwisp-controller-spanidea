import csv

import django
from django.core.files.temp import NamedTemporaryFile
from django.core.management import call_command
from django.urls import reverse

from openwisp_users.tests.test_admin import TestBasicUsersIntegration
from openwisp_utils.tests import capture_stdout

from ..utils import load_model
from .mixins import GetEditFormInlineMixin

RadiusToken = load_model("RadiusToken")
RadiusGroup = load_model("RadiusGroup")
RegisteredUser = load_model("RegisteredUser")


class TestUsersIntegration(GetEditFormInlineMixin, TestBasicUsersIntegration):
    """
    tests integration with openwisp_users
    """

    is_integration_test = True

    def test_radiustoken_inline(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        user = self._create_user()
        org = self._get_org()
        self._create_org_user(organization=org, user=user)
        params = user.__dict__
        params.pop("phone_number")
        params.pop("password", None)
        params.pop("_password", None)
        params.pop("bio", None)
        params.pop("last_login", None)
        params.pop("password_updated", None)
        params.pop("birth_date", None)
        params = self._additional_params_pop(params)
        params.update(self._get_user_edit_form_inline_params(user, org))
        url = reverse(f"admin:{self.app_label}_user_change", args=[user.pk])
        response = self.client.get(
            url,
        )
        self.assertContains(response, 'id="id_radius_token-__prefix__-organization"')
        # TODO: Remove this while dropping support for Django 4.2
        if django.VERSION < (5, 1):
            self.assertNotContains(response, 'id="id_radius_token-__prefix__-key"')
        else:
            # On Django 5.1+, the empty form include hidden field for the
            # primary key of the related object ("key" field for RadiusToken).
            self.assertContains(
                response,
                '<input type="hidden" name="radius_token-__prefix__-key"'
                ' id="id_radius_token-__prefix__-key">',
            )

        # Create a radius token
        params.update(
            {
                "radius_token-0-organization": str(org.id),
                "radius_token-0-user": str(user.id),
                "radius_token-0-can_auth": True,
                "radius_token-TOTAL_FORMS": "1",
                "_continue": True,
            }
        )
        response = self.client.post(url, params, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RadiusToken.objects.count(), 1)
        radius_token = user.radius_token.key
        self.assertContains(
            response,
            (
                '<input type="text" name="radius_token-0-key"'
                f' value="{radius_token}"'
                ' class="readonly vTextField" readonly maxlength="40"'
                ' id="id_radius_token-0-key">'
            ),
            html=True,
        )

        # Delete user radius token
        params.update(
            {
                "radius_token-0-DELETE": "on",
                "radius_token-INITIAL_FORMS": "1",
                "radius_token-0-key": radius_token,
            }
        )
        response = self.client.post(url, params, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RadiusToken.objects.count(), 0)

    @capture_stdout()
    def test_export_users_command(self):
        temp_file = NamedTemporaryFile(delete=False)
        user = self._create_org_user().user
        RegisteredUser.objects.create(
            user=user, method="mobile_phone", is_verified=False
        )
        with self.assertNumQueries(1):
            call_command("export_users", filename=temp_file.name)

        with open(temp_file.name, "r") as file:
            csv_reader = csv.reader(file)
            csv_data = list(csv_reader)

        self.assertEqual(len(csv_data), 2)
        self.assertIn("registered_user.method", csv_data[0])
        self.assertIn("registered_user.is_verified", csv_data[0])
        self.assertEqual(csv_data[1][-2], "mobile_phone")
        self.assertEqual(csv_data[1][-1], "False")

    def test_radiususergroup_inline(self):
        """
        Ensures that adding OrganizationUser and default
        RadiusUserGroup (of the same organization) in the same
        transaction does not cause any errors.
        """
        admin = self._create_admin()
        self.client.force_login(admin)
        user = self._create_user()
        org = self._get_org()
        default_radius_group = RadiusGroup.objects.get(organization=org, default=True)
        params = user.__dict__
        params.pop("phone_number")
        params.pop("password", None)
        params.pop("_password", None)
        params.pop("bio", None)
        params.pop("last_login", None)
        params.pop("password_updated", None)
        params.pop("birth_date", None)
        params = self._additional_params_pop(params)
        params.update(self._get_user_edit_form_inline_params(user, org))
        params.update(
            {
                # OrganizationUser inline
                f"{self.app_label}_organizationuser-TOTAL_FORMS": 1,
                f"{self.app_label}_organizationuser-INITIAL_FORMS": 0,
                f"{self.app_label}_organizationuser-MIN_NUM_FORMS": 0,
                f"{self.app_label}_organizationuser-MAX_NUM_FORMS": 1000,
                f"{self.app_label}_organizationuser-0-is_admin": False,
                f"{self.app_label}_organizationuser-0-id": "",
                f"{self.app_label}_organizationuser-0-organization": str(org.pk),
                f"{self.app_label}_organizationuser-0-user": str(user.pk),
                # RadiusUserGroup inline
                "radiususergroup_set-TOTAL_FORMS": 1,
                "radiususergroup_set-INITIAL_FORMS": 0,
                "radiususergroup_set-MIN_NUM_FORMS": 0,
                "radiususergroup_set-MAX_NUM_FORMS": 1000,
                "radiususergroup_set-0-priority": 1,
                "radiususergroup_set-0-id": "",
                "radiususergroup_set-0-group": str(default_radius_group.pk),
                "radiususergroup_set-0-user": str(user.pk),
            }
        )

        url = reverse(f"admin:{self.app_label}_user_change", args=[user.pk])
        response = self.client.post(
            url,
            params,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(user.organizations_dict.keys()), 1)
        self.assertEqual(user.radiususergroup_set.count(), 1)


del TestBasicUsersIntegration
