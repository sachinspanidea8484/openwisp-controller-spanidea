from django.urls import include, path

from . import executor_views

app_name = "test_management"

urlpatterns = [
    path(
        "test-management/",
        include([
            # Test Category endpoints
            # path(
            #     "category/",
            #     executor_views.test_category_list,
            #     name="api_test_category_list",
            # ),
            # path(
            #     "category/<uuid:pk>/",
            #     executor_views.test_category_detail,
            #     name="api_test_category_detail",
            # ),
            # path(
            #     "category/<uuid:category_id>/test-cases/",
            #     executor_views.get_category_test_cases,
            #     name="api_category_test_cases",
            # ),
            path(
                "category/get-test-cases/",
                executor_views.get_categories_test_cases,
                name="api_categories_test_cases",  # Fixed typo: cateogries -> categories
            ),
            
            # Test Case endpoints
            # path(
            #     "test-case/",
            #     executor_views.test_case_list,
            #     name="api_test_case_list",
            # ),
            # path(
            #     "test-case/<uuid:pk>/",
            #     executor_views.test_case_detail,
            #     name="api_test_case_detail",
            # ),
            
            # Test Suite endpoints
            # path(
            #     "test-suite/",
            #     executor_views.test_suite_list,
            #     name="api_test_suite_list",
            # ),
            # path(
            #     "test-suite/<uuid:pk>/",
            #     executor_views.test_suite_detail,
            #     name="api_test_suite_detail",
            # ),
            # path(
            #     "test-suite/<uuid:suite_id>/details/",
            #     executor_views.get_test_suite_details,
            #     name="api_test_suite_details",
            # ),
            
            # Test Suite Execution endpoints
            # path(
            #     "execution/",
            #     executor_views.test_suite_execution_list,
            #     name="api_test_suite_execution_list",
            # ),
            # path(
            #     "execution/<uuid:pk>/",
            #     executor_views.test_suite_execution_detail,
            #     name="api_test_suite_execution_detail",
            # ),
            path(
                "execution/available-devices/",
                executor_views.available_devices,
                name="api_available_devices",
            ),
            path(
                "execution/<uuid:execution_id>/history/",
                executor_views.test_execution_history,
                name="api_test_execution_history",
            ),
            path(
                "execution/<uuid:execution_id>/all-history/",
                executor_views.test_execution_all_history,
                name="api_test_execution_all_history",
            ),
            path(
                "execution/<uuid:execution_id>/history/export/",
                executor_views.test_execution_history_export,
                name="api_test_execution_history_export",
            ),
            path(
                "execution-details/",
                executor_views.get_execution_details,
                name="api_get_execution_details",
            ),
            path(
                "execution/<uuid:execution_id>/abort-execution/",
                executor_views.test_execution_abort,
                name="api_test_execution_abort",
            ),
            
            # Test Case Execution endpoints
            path(
                "test-case-execution/result/",
                executor_views.TestCaseExecutionResultView.as_view(),
                name="api_test_case_execution_result",
            ),
            path(
                "test-case-execution/<uuid:execution_id>/download-log/",
                executor_views.download_test_log,
                name="api_download_test_log",
            ),
            path(
                "test-case-execution/<uuid:execution_id>/retry/",
                executor_views.retry_test_execution,
                name="api_retry_test_execution",
            ),
            path(
                "test-case-execution/<uuid:execution_id>/abort/",
                executor_views.abort_test_execution,
                name="api_abort_test_execution",
            ),
            
            # Robot Test Result endpoints
            #old
            # path(
            #     "robot-test-result/",
            #     executor_views.RobotTestResultView.as_view(),
            #     name="api_robot_test_result",
            # ),
            # #new
            path(
                "test-result/",
                executor_views.TestResultView.as_view(),
                name="api_test_result",
            ),
            

            # path(
            #     "robot-test-result/running/",
            #     executor_views.RobotTestRunningResultView.as_view(),
            #     name="api_robot_test_running_result",
            # ),

                        path(
                "test-result/running/",
                executor_views.TestRunningResultView.as_view(),
                name="api_test_running_result",
            ),
            
            # Device Test Result endpoints
            # path(
            #     "device-test-result/",
            #     executor_views.DeviceTestResultView.as_view(),
            #     name="api_device_test_result",
            # ),
            path(
                "device-execution/<uuid:test_group_execution_id>/<uuid:dev_id>/upload-allure-report/",
                executor_views.upload_allure_report,
                name="api_upload_allure_report",
            ),
            
            # Test Suite Execution Management
            # path(
            #     "test-suite-execution/<uuid:pk>/delete-all/",
            #     executor_views.TestSuiteExecutionDeleteAllView.as_view(),
            #     name="api_test_suite_execution_delete_all",
            # ),
            
            # Device Management endpoints
            path(
                "devices/",
                executor_views.get_available_devices,
                name="api_get_available_devices",  # Made name more specific to avoid conflicts
            ),
            path(
                "get-organization-devices/",
                executor_views.get_organization_devices,
                name="api_get_organization_devices",
            ),
            # path(
            #     "device-groups/<uuid:group_id>/devices/<uuid:execution_id>",
            #     executor_views.get_device_group_devices,
            #     name="api_device_group_devices",
            # ),
            # path(
            #     "device-groups/<uuid:group_id>/devices/",
            #     executor_views.get_device_group_devices,
            #     name="api_device_group_devices",
            # ),
            # path(
            #     "device-groups/",
            #     executor_views.TestDeviceGroupexecutor_viewset.as_view({
            #         "get": "list",      # GET /device-groups/
            #         "post": "create"    # POST /device-groups/
            #     }),
            #     name="device-group-list",
            # ),

            # Detail endpoint: retrieve + update + delete
            path(
                "device-groups/<uuid:pk>/",
                executor_views.TestDeviceGroupexecutor_viewset.as_view({
                    "get": "retrieve",           # GET /device-groups/{id}/
                    "patch": "partial_update",   # PATCH /device-groups/{id}/
                    "delete": "destroy",          # DELETE /device-groups/{id}/
                    "put": "update",
                }),
                name="device-group-detail",
            ),
            path(
                "devices/configuration-push",
                executor_views.ConfigurationPushOnDevice,
                name="configuration_push_on_device",
            ),

            path(
                "test-suite-execution/<uuid:execution_id>/re-execute/",
                executor_views.re_execute_view,
                name="re-execute-execution"
            ),
            path(
                "test-suite-execution/<uuid:execution_id>/re-execute-selected/",
                executor_views.re_execute_selected_view,
                name="re-execute-selected-execution"
            ),
            

            path(
                "test-case/check-test-case-id/",
                executor_views.check_test_case_id_unique,
                name="api_check_test_case_id_unique",
            ),
            
            # Commented out endpoints (kept for reference)
            # path(
            #     "delete-all-test-data/",
            #     executor_views.delete_all_test_data,
            #     name="api_delete_all_test_data",
            # ),
            # path(
            #     "device-execution/<uuid:device_execution_id>/retry-all/",
            #     executor_views.retry_device_tests,
            #     name="api_retry_device_tests",
            # ),
        ]),
    ),
]
