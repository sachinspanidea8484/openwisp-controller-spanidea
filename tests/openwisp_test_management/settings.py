from django.conf import settings

TEST_MANAGEMENT_API_ENABLED = getattr(
    settings, "OPENWISP_TEST_MANAGEMENT_API_ENABLED", True
)

TEST_MANAGEMENT_EXECUTION_TIMEOUT = getattr(
    settings, "OPENWISP_TEST_MANAGEMENT_EXECUTION_TIMEOUT", 300  # 5 minutes
)

TEST_MANAGEMENT_MAX_DEVICES_PER_EXECUTION = getattr(
    settings, "OPENWISP_TEST_MANAGEMENT_MAX_DEVICES_PER_EXECUTION", 100
)

TEST_MANAGEMENT_ENABLE_AUTO_EXECUTION = getattr(
    settings, "OPENWISP_TEST_MANAGEMENT_ENABLE_AUTO_EXECUTION", True
)
# Future settings will be added here for test execution timeouts, etc.