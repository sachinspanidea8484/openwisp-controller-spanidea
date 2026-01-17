from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name

from openwisp_utils.admin_theme.menu import register_menu_group
from openwisp_utils.api.apps import ApiAppConfig
from openwisp_utils.utils import default_or_test
from openwisp_notifications.types import (
    register_notification_type,
    
)
from swapper import load_model
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
        from . import signals
        super().ready(*args, **kwargs)
        self.register_menu_groups()
        self.register_notification_types()
        self.connect_signals()

    def connect_signals(self):
       
        from . import handlers
        TestSuiteExecution = load_model("test_management", "TestSuiteExecution")

        post_save.connect(
            handlers.testsuite_execution_status_notification,
            sender=TestSuiteExecution,
            dispatch_uid="testsuite_execution_status_notification",
        )
    def register_menu_groups(self):
        register_menu_group(
            position=111,
            config={
                "label": _("Test Management"),
                "items": {
                    1: {
                        "label": _("Test Category"),
                        "model": get_model_name(self.label, "TestCategory"),
                        "name": "changelist",
                        "icon": "ow-category",
                    },
                    2: {
                        "label": _("Test Cases"),
                        "model": get_model_name(self.label, "TestCase"),
                        "name": "changelist",
                        "icon": "ow-template",
                    },
                    3: {
                        "label": _("Test Group"),
                        "model": get_model_name(self.label, "TestSuite"),
                        "name": "changelist",
                        "icon": "ow-test-group",
                    },
                    4: {
                        "label": _("Device Group"),
                        "model": get_model_name(self.label, "TestDeviceGroup"),
                        "name": "changelist",
                        "icon": "ow-device-group",
                    },
                    5: {
                    "label": _("Test Executions"),
                    "model": get_model_name(self.label, "TestSuiteExecution"),
                    "name": "changelist",
                    "icon": "ow-mass-upgrade",
                    },
                  
                },
                "icon": "ow-test-management",
            },
        )

    def register_notification_types(self):

        register_notification_type(
            "test_suite_execution_completed",
            {
                "verbose_name": _("Test Suite Execution"),
                "verb": _("completed"),
                "level": "success",
                "email_subject": _(
                    '[{site.name}] SUCCESS: Test Suite Execution Completed'
                ),
                "message": _(
                    'Execution "{execution_name}" has completed successfully.'
                ),
                "extra_context": ["execution_name"],
            },
            models=[load_model("test_management", "TestSuiteExecution")],
        )
del ApiAppConfig