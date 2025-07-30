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
            path(
                "category/<uuid:category_id>/test-cases/",
                views.get_category_test_cases,
                name="api_category_test_cases",
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
        "test-suite/<uuid:suite_id>/details/",
        views.get_test_suite_details,
        name="api_test_suite_details",
    ),
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
path(
    "robot-test-result/",
    views.RobotTestResultView.as_view(),
    name="api_robot_test_result",
),
path(
    "device-test-result/",
    views.DeviceTestResultView.as_view(),
    name="api_device_test_result",
),




           path(
                "execution/<uuid:execution_id>/history/",
                views.test_execution_history,
                name="api_test_execution_history",
            ),
            path(
                "test-case-execution/<uuid:execution_id>/download-log/",
                views.download_test_log,
                name="api_download_test_log",
            ),
            path(
                "test-case-execution/<uuid:execution_id>/retry/",
                views.retry_test_execution,
                name="api_retry_test_execution",
            ),
            path(
                "device-execution/<uuid:device_execution_id>/retry-all/",
                views.retry_device_tests,
                name="api_retry_device_tests",
            ),









path(
    "add-logging-test-data/",
    views.AddLoggingDeviceTestDataView.as_view(),    
    name="api_add_logging_test_data", 
),
path(
    "add-5g-test-data/",
    views.AddFiveGDeviceTestDataView.as_view(),    
    name="api_add_5g_test_data", 
),

path(
    "add-wifi-test-data/",
    views.AddWifiGDeviceTestDataView.as_view(),    
    name="api_add_wifi_test_data", 
),

path(
    "add-firewall-test-data/",
    views.AddFireWallGDeviceTestDataView.as_view(),    
    name="api_add_firewall_test_data", 
),


# urls.py
# path(
#     "test-suite-execution/<uuid:pk>/delete/",
#     views.TestSuiteExecutionDeleteView.as_view(),
#     name="api_test_suite_execution_delete",
# ),

# urls.py
path(
    "test-suite-execution/<uuid:pk>/delete-all/",
    views.TestSuiteExecutionDeleteAllView.as_view(),
    name="api_test_suite_execution_delete_all",
),

path(
    "bulk-test-data/",
    views.BulkTestDataCreationView.as_view(),
    name="api_bulk_test_data_creation",
),


            path(
                "devices/",
                views.get_available_devices,
                name="api_available_devices",
            ),



        ]),
    ),


]