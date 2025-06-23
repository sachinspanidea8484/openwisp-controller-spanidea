from django.conf import settings

TEST_MANAGEMENT_API_ENABLED = getattr(
    settings, "OPENWISP_TEST_MANAGEMENT_API_ENABLED", True
)

# Future settings will be added here for test execution timeouts, etc.