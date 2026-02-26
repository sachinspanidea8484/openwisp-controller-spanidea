from django.conf import settings
from django.utils.module_loading import import_string
from django.core.exceptions import ImproperlyConfigured
from pathlib import Path

CURRENT_DIR= Path(__file__).resolve().parent.parent

EXECUTOR_SERVER_IP = getattr(
    settings, "EXECUTOR_SERVER_IP", "http://172.17.0.1:8080"
)


OPENWISP_SERVER_IP = getattr(
    settings, "OPENWISP_SERVER_IP", "http://172.17.0.1:8000"
)

MEDIA_URL = getattr(
    settings, "MEDIA_URL", "/media/"
)


EMAIL_HOST_USER = getattr(
    settings, "EMAIL_HOST_USER", ""
)

EXECUTION_HISTORY_AUTO_REFRESH_TIME = getattr(
    settings, "EXECUTION_HISTORY_AUTO_REFRESH_TIME", 60
)

TEST_MANAGEMENT_API_ENABLED = getattr(
    settings, "OPENWISP_TEST_MANAGEMENT_API_ENABLED", True
)

MAX_FILE_SIZE = getattr(
    settings, "OPENWISP_FIRMWARE_UPGRADER_MAX_FILE_SIZE", 500 * 1024 * 1024
)
try:
    PRIVATE_STORAGE_INSTANCE = import_string(
        getattr(
            settings,
            "OPENWISP_FIRMWARE_PRIVATE_STORAGE_INSTANCE",
            "openwisp_test_management.private_storage.storage.file_system_private_storage",
        )
    )
except ImportError:
    raise ImproperlyConfigured(
        "Failed to import FIRMWARE_UPGRADER_PRIVATE_STORAGE_INSTANCE"
    )

