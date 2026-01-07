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
            path(
                "category/get-test-cases/",
                views.get_categories_test_cases,
                name="api_categories_test_cases",  # Fixed typo: cateogries -> categories
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
            path(
                "test-suite/<uuid:suite_id>/details/",
                views.get_test_suite_details,
                name="api_test_suite_details",
            ),
            
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
            path(
                "execution/available-devices/",
                views.available_devices,
                name="api_available_devices",
            ),
            path(
                "execution/<uuid:execution_id>/history/",
                views.test_execution_history,
                name="api_test_execution_history",
            ),
            path(
                "execution/<uuid:execution_id>/all-history/",
                views.test_execution_all_history,
                name="api_test_execution_all_history",
            ),
            path(
                "execution-details/",
                views.get_execution_details,
                name="api_get_execution_details",
            ),
            path(
                "execution/<uuid:execution_id>/abort-execution/",
                views.test_execution_abort,
                name="api_test_execution_history",
            ),
            
            # Test Case Execution endpoints
            path(
                "test-case-execution/result/",
                views.TestCaseExecutionResultView.as_view(),
                name="api_test_case_execution_result",
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
                "test-case-execution/<uuid:execution_id>/abort/",
                views.abort_test_execution,
                name="api_abort_test_execution",
            ),
            
            # Robot Test Result endpoints
            #old
            path(
                "robot-test-result/",
                views.RobotTestResultView.as_view(),
                name="api_robot_test_result",
            ),
            #new
            path(
                "test-result/",
                views.TestResultView.as_view(),
                name="api_test_result",
            ),
            

            path(
                "robot-test-result/running/",
                views.RobotTestRunningResultView.as_view(),
                name="api_robot_test_running_result",
            ),

                        path(
                "test-result/running/",
                views.TestRunningResultView.as_view(),
                name="api_test_running_result",
            ),
            
            # Device Test Result endpoints
            path(
                "device-test-result/",
                views.DeviceTestResultView.as_view(),
                name="api_device_test_result",
            ),
            path(
                "device-execution/<uuid:test_group_execution_id>/<uuid:dev_id>/upload-allure-report/",
                views.upload_allure_report,
                name="api_upload_allure_report",
            ),
            
            # Test Suite Execution Management
            path(
                "test-suite-execution/<uuid:pk>/delete-all/",
                views.TestSuiteExecutionDeleteAllView.as_view(),
                name="api_test_suite_execution_delete_all",
            ),
            
            # Device Management endpoints
            path(
                "devices/",
                views.get_available_devices,
                name="api_get_available_devices",  # Made name more specific to avoid conflicts
            ),
            path(
                "get-organization-devices/",
                views.get_organization_devices,
                name="api_get_organization_devices",
            ),
            path(
                "device-groups/<uuid:group_id>/devices/<uuid:execution_id>",
                views.get_device_group_devices,
                name="api_device_group_devices",
            ),
            path(
                "device-groups/<uuid:group_id>/devices/",
                views.get_device_group_devices,
                name="api_device_group_devices",
            ),
            path(
                "device-groups/",
                views.TestDeviceGroupViewSet.as_view({
                    "get": "list",      # GET /device-groups/
                    "post": "create"    # POST /device-groups/
                }),
                name="device-group-list",
            ),

            # Detail endpoint: retrieve + update + delete
            path(
                "device-groups/<uuid:pk>/",
                views.TestDeviceGroupViewSet.as_view({
                    "get": "retrieve",           # GET /device-groups/{id}/
                    "patch": "partial_update",   # PATCH /device-groups/{id}/
                    "delete": "destroy",          # DELETE /device-groups/{id}/
                    "put": "update",
                }),
                name="device-group-detail",
            ),
            path(
                "devices/configuration-push",
                views.ConfigurationPushOnDevice,
                name="configuration_push_on_device",
            ),
            path(
                "test-suite-execution/<uuid:execution_id>/re-execute/",
                views.re_execute_view,
                name="re-execute-execution"
            )

            
            # Commented out endpoints (kept for reference)
            # path(
            #     "delete-all-test-data/",
            #     views.delete_all_test_data,
            #     name="api_delete_all_test_data",
            # ),
            # path(
            #     "device-execution/<uuid:device_execution_id>/retry-all/",
            #     views.retry_device_tests,
            #     name="api_retry_device_tests",
            # ),
        ]),
    ),
]
