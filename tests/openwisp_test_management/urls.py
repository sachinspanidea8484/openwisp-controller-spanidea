from django.urls import include, path

from . import settings as app_settings

urlpatterns = []

if app_settings.TEST_MANAGEMENT_API_ENABLED:
    urlpatterns += [
        path("api/v1/", include("openwisp_test_management.api.urls")),
    ]