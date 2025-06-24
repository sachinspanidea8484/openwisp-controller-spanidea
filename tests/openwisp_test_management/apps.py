from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name

from openwisp_utils.admin_theme.menu import register_menu_group
from openwisp_utils.api.apps import ApiAppConfig
from openwisp_utils.utils import default_or_test

from . import settings as app_settings


class TestManagementConfig(ApiAppConfig):
    name = "openwisp_test_management"
    label = "test_management"
    verbose_name = _("Test Management")
    default_auto_field = "django.db.models.AutoField"

    API_ENABLED = app_settings.TEST_MANAGEMENT_API_ENABLED
    REST_FRAMEWORK_SETTINGS = {
        "DEFAULT_THROTTLE_RATES": {
            "test_management": default_or_test("1000/minute", None)
        },
    }

    def ready(self, *args, **kwargs):
        super().ready(*args, **kwargs)
        self.register_menu_groups()

    def register_menu_groups(self):
        register_menu_group(
            position=111,
            config={
                "label": _("Test Management"),
                "items": {
                    1: {
                        "label": _("Categories"),
                        "model": get_model_name(self.label, "TestCategory"),
                        "name": "changelist",
                        "icon": "ow-category",
                    },
                    2: {
                        "label": _("Test Cases"),
                        "model": get_model_name(self.label, "TestCase"),
                        "name": "changelist",
                        "icon": "ow-test-case",
                    },
                    # Future items will be added here:
                    # 3: Suites
                    # 4: Mass Execution
                },
                "icon": "ow-test-management",
            },
        )


del ApiAppConfig