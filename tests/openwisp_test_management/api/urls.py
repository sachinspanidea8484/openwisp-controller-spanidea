from django.urls import include, path

from . import views

app_name = "test_management"

urlpatterns = [
    path(
        "test-management/",
        include([
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
            # Future endpoints will be added here:
            # test-case/
            # test-suite/
            # mass-execution/
        ]),
    ),
]