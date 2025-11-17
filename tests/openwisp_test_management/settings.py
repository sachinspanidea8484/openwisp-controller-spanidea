from django.conf import settings
from django.utils.module_loading import import_string
from django.core.exceptions import ImproperlyConfigured
from pathlib import Path
# EXECUTOR_SERVER_IP = getattr(
#     settings, "EXECUTOR_SERVER_IP", "http://44.199.94.165"
# )


# OPENWISP_SERVER_IP = getattr(
#     settings, "OPENWISP_SERVER_IP", "http://44.193.103.240"
# )
CURRENT_DIR= Path(__file__).resolve().parent.parent

EXECUTOR_SERVER_IP = getattr(
    settings, "EXECUTOR_SERVER_IP", "http://172.17.0.1:8080"
)


OPENWISP_SERVER_IP = getattr(
    settings, "OPENWISP_SERVER_IP", "http://172.17.0.1:8000"
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

