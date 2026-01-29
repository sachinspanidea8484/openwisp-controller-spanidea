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
        "test-cases/",
        views.test_case_list_view,
        name="api_test_case_list",
    ),



           


       # EXTERNAL APIS  
            path(
                "category/get-test-cases/",
                executor_views.get_categories_test_cases,
                name="api_categories_test_cases",  # Fixed typo: cateogries -> categories
            ),
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
                "device-execution/<uuid:test_group_execution_id>/<uuid:dev_id>/upload-allure-report/",
                executor_views.upload_allure_report,
                name="api_upload_allure_report",
            ),
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
        ]),
    ),
]
