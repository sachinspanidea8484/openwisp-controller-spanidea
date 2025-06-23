from django.urls import include, path

from . import views

app_name = "test_management"

urlpatterns = [
    path(
        "test-management/",
        include([
            # Test Category endpoints
            path(
                "category/",
                views.test_category_list,
                name="api_test_category_list",
            ),
            path(
                "category/<uuid:pk>/",
                views.test_category_detail,
                name="api_test_category_detail",
            ),
            # Test Case endpoints
            path(
                "test-case/",
                views.test_case_list,
                name="api_test_case_list",
            ),
            path(
                "test-case/<uuid:pk>/",
                views.test_case_detail,
                name="api_test_case_detail",
            ),
            # Future endpoints will be added here:
            # test-suite/
            # mass-execution/
        ]),
    ),
]