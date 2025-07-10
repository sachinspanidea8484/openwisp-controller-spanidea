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
            # Test Suite endpoints
            path(
                "test-suite/",
                views.test_suite_list,
                name="api_test_suite_list",
            ),
            path(
                "test-suite/<uuid:pk>/",
                views.test_suite_detail,
                name="api_test_suite_detail",
            ),
            # Future endpoints will be added here:
           # Test Suite Execution endpoints
            path(
                "execution/",
                views.test_suite_execution_list,
                name="api_test_suite_execution_list",
            ),
            path(
                "execution/<uuid:pk>/",
                views.test_suite_execution_detail,
                name="api_test_suite_execution_detail",
            ),
             path("execution/available-devices/", views.available_devices, name="api_available_devices"),



# testing-purpose 
            #    path(
            #     "add-all-test-data/",
            #     views.add_all_test_data,
            #     name="api_add_all_test_data",
            # ),
               path(
                "delete-all-test-data/",
                views.delete_all_test_data,
                name="api_delete_all_test_data",
            ),
              path(
                "execution-details/",
                views.get_execution_details,
                name="api_get_execution_details",
            ),
#                 path(
#     "add-device-test-data/",
#     views.add_device_test_data,  
#     name="api_add_device_test_data", 
# ),
# path(
#     "add-robot-test-data/",
#     views.add_robot_test_data,    
#     name="api_add_robot_test_data", 
# ),
path(
    "add-device-test-data/",
    views.AddDeviceTestDataView.as_view(),
    name="api_add_device_test_data",
),
path(
    "add-robot-test-data/",
    views.AddRobotTestDataView.as_view(),    
    name="api_add_robot_test_data", 
),
path(
    "test-case-execution/result/",
    views.TestCaseExecutionResultView.as_view(),
    name="api_test_case_execution_result",
),

        ]),
    ),
]