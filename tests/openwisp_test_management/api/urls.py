from django.urls import include, path

from . import executor_views
from . import views


app_name = "test_management"

urlpatterns = [
     path(
        "test-management/",
        include([
    # NATIVE APIS

    # ========================================================================
    # TEST CATEGORY ENDPOINTS
    # ========================================================================
    # List all categories OR create new category
    path(
        "test-category/",
        views.test_category_list,
        name="api_test_category_list",
    ),
    # Get/Update/Delete specific category
    path(
        "test-category/<uuid:pk>/",
        views.test_category_detail,
        name="api_test_category_detail",
    ),

    # ========================================================================
    # TEST CASE ENDPOINTS
    # ========================================================================
    # List all Exections OR create new Execution
    path(
        "execution/",
        views.test_execution_list,
        name="api_test_execution_list",
    ),
    # Get/Update/Delete specific Execution
    path(
        "execution/<uuid:pk>/",
        views.test_execution_detail,
        name="api_test_execution_detail",
    ),
    path(
        "test-cases/",
        views.test_case_list,
        name="testcase-list",
    ),
    path(
        "test-cases/<uuid:pk>/",
        views.test_case_detail,
        name="testcase-detail",
    ),
    path(
        "test-cases/export-all_scripts/",
        views.export_all_scripts,
        name="export-all-scripts",
    ),
    path(
        "test-cases/export/<str:export_format>/",
        views.test_case_export,
        name="test-case-export",
    ),
    path(
        "test-cases/import/",
        views.test_case_import,
        name="test-case-import",
    ),


    # ========================================================================
    # TEST SUITE (TEST GROUP) ENDPOINTS
    # ========================================================================
    
    # List and create test groups
    path(
        "test-group/",
        views.test_suite_list,
        name="api_test_group_list",
    ),
    
    # Retrieve, update, delete test group
    path(
        "test-group/<uuid:pk>/",
        views.test_suite_detail,
        name="api_test_group_detail",
    ),
    # ========================================================================
    # TEST CASE LISTING (WITH CATEGORY FILTER)
    # ========================================================================
    
    # List test cases with category filter
    path(
        "test-cases-by-category/",
        views.test_cases_by_category,
        name="api_test_cases_by_category",
    ),


    # ================================================================
    # DEVICE GROUP ENDPOINTS (NEW)
    # ================================================================
    path(
        "device-group/",
        views.device_group_list,
        name="api_device_group_list",
    ),
    path(
        "device-group/<uuid:pk>/",
        views.device_group_detail,
        name="api_device_group_detail",
    ),
    
    # Get devices available for adding to groups
    # Query with: ?organization={org_id}
    path(
        "devices-by-organization/",
        views.devices_by_organization,
        name="api_devices_by_organization",
    ),

    path(
        "test-case-execution/<uuid:execution_id>/download-log/",
        executor_views.download_test_log,
        name="api_download_test_log",
    ),
    path(
        "test-case/check-test-case-id/",
        executor_views.check_test_case_id_unique,
        name="api_check_test_case_id_unique",
    ),


    path(
        "execution/<uuid:execution_id>/start-execution/",
        views.test_execution_start,
        name="api_test_execution_start",
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
        "execution/<uuid:execution_id>/history/export/",
        views.test_execution_history_export,
        name="api_test_execution_history_export",
    ),
    path(
        "execution/<uuid:execution_id>/abort-execution/",
        views.test_execution_abort_view,
        name="api_test_execution_abort",
    ),
    path(
        "execution/<uuid:execution_id>/re-execute/",
        views.test_execution_re_execute,
        name="api_test_execution_re_execute"
    ),
    path(
        "execution/<uuid:execution_id>/re-execute-selected/",
        views.test_execution_re_execute_selected,
        name="api_test_execution_re_execute_selected"
    ),
    


    # Internal APIS  
    path(
        "category/get-test-cases/",
        executor_views.get_categories_test_cases,
        name="api_categories_test_cases",  # Fixed typo: cateogries -> categories
    ),

    path(
        "get-organization-devices/",
        executor_views.get_organization_devices,
        name="api_get_organization_devices",
    ),
    path(
        "device-execution/<uuid:test_group_execution_id>/<uuid:dev_id>/upload-allure-report/",
        executor_views.upload_allure_report,
        name="api_upload_allure_report",
    ),
        # Test Case Execution endpoints
    path(
        "test-result/",
        executor_views.TestResultView.as_view(),
        name="api_test_result",
    ),

    path(
        "test-result/running/",
        executor_views.TestRunningResultView.as_view(),
        name="api_test_running_result",
    ),
    path(
        "test-group/<uuid:suite_id>/details/",
                executor_views.get_test_suite_details,
                name="api_test_suite_details",
    ),
     path(
                "device-groups/<uuid:group_id>/devices/",
                executor_views.get_device_group_devices,
                name="api_device_group_devices",
            ),
    path(
                "devices/",
                executor_views.get_available_devices,
                name="api_get_available_devices",  # Made name more specific to avoid conflicts
            ),


    path(
                "device-groups/",
                executor_views.TestDeviceGroupViewSet.as_view({
                    "get": "list",      # GET /device-groups/
                    "post": "create"    # POST /device-groups/
                }),
                name="device-group-list",
            ),
            path(
                "test-suite/<uuid:suite_id>/details/",
                executor_views.get_test_suite_details,
                name="api_test_suite_details",
            ),
                      path(
                "device-groups/<uuid:group_id>/devices/<uuid:execution_id>",
                executor_views.get_device_group_devices,
                name="api_device_group_devices",
            ),

    # Un Use APIS  
    # path(
    #     "test-case-execution/result/",
    #     executor_views.TestCaseExecutionResultView.as_view(),
    #     name="api_test_case_execution_result",
    # ),
    # path(
    #     "test-case-execution/<uuid:execution_id>/retry/",
    #     executor_views.retry_test_execution,
    #     name="api_retry_test_execution",
    # ),
    # path(
    #     "test-case-execution/<uuid:execution_id>/abort/",
    #     executor_views.abort_test_execution,
    #     name="api_abort_test_execution",
    # ),
    # path(
    #     "execution-details/",
    #     executor_views.get_execution_details,
    #     name="api_get_execution_details",
    # ),
    # path(
    #     "devices/",
    #     executor_views.get_available_devices,
    #     name="api_get_available_devices",  # Made name more specific to avoid conflicts
    # ),
    # path(
    #     "execution/available-devices/",
    #     views.test_execution_available_devices,
    #     name="api_test_execution_available_devices",
    # ),
        ]),
    ),
]
