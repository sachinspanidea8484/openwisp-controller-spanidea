from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, pagination ,status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from django.utils import timezone


from django.http import HttpResponse
from rest_framework.generics import GenericAPIView

from openwisp_users.api.mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
from openwisp_users.api.permissions import DjangoModelPermissions
from rest_framework.permissions import IsAuthenticated
from openwisp_test_management.utils import build_all_testcases_zip
from ..swapper import load_model

import logging
logger = logging.getLogger(__name__)

from .filters import TestCategoryFilter ,TestSuiteFilter, TestSuiteExecutionFilter, TestCaseFilter

from .serializers import (
    TestCategorySerializer,
    TestCategoryDetailSerializer,
    TestCaseSerializer,
    TestCaseDetailSerializer,
    TestSuiteSerializer,
    TestSuiteDetailSerializer,
    TestCaseListSerializer,
    TestSuiteExecutionSerializer,
    TestSuiteExecutionCreateSerializer,
    TestSuiteExecutionListSerializer,
    ReExecuteSelectedTestsSerializer,
)
from openwisp_controller.config.models import Device
from rest_framework.parsers import MultiPartParser, FormParser

TestCategory = load_model("TestCategory")
TestExecution = load_model("TestSuiteExecution")
TestSuite = load_model("TestSuite")
TestCase = load_model("TestCase")
TestSuiteCase = load_model("TestSuiteCase")
TestCaseExecution = load_model("TestCaseExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")

class ListViewPagination(pagination.PageNumberPagination):
    """Pagination configuration for list views"""
    page_size = 10                    # Default items per page
    page_size_query_param = "page_size"  # Allow user to set page size
    max_page_size = 100               # Maximum allowed page size


class ProtectedAPIMixin(BaseProtectedAPIMixin):
    """
    Base mixin for all test management API views
    Adds authentication and permission requirements
    """
    permission_classes = (
        IsAuthenticated,           # Must be logged in
        DjangoModelPermissions,    # Must have model permissions
    )
    throttle_scope = "test_management"


def create_test_execution_clone(execution, request):
    """
    Creates a full re-execution with identical configuration.
    """
    Execution = type(execution)
    root = execution.parent_execution or execution

    with transaction.atomic():
        
        retry_count = Execution.objects.filter(
            parent_execution=root
        ).count()

        new_execution = Execution.objects.create(
            parent_execution=root,
            re_execution_index=retry_count + 1,
            test_case_execution_order= execution.test_case_execution_order,
            name=root.name + f"_{retry_count+1}",
            test_selection_type=execution.test_selection_type,
            test_suite=execution.test_suite,
            device_selection=execution.device_selection,
            device_group=execution.device_group,
            notification_emails= execution.notification_emails,
            execution_start_time= timezone.now(),
            created_by= request.user,
        )
        
        if execution.test_selection_type == 0:
            new_execution.individual_test_cases.set(
                execution.individual_test_cases.all()
            )

        old_devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        )

        TestSuiteExecutionDevice.objects.bulk_create([
            TestSuiteExecutionDevice(
                test_suite_execution=new_execution,
                device=ed.device,
                connection_protocol= ed.connection_protocol,
                status="pending",
            )
            for ed in old_devices
        ])

        new_execution.device_count = execution.device_count

        new_execution.testcase_count= execution.testcase_count
        new_execution.save(update_fields=["device_count", "testcase_count"])

    return new_execution

def create_test_execution_clone_for_selected_tests(execution, device_tests_info_list, request):
    """
    Creates a full re-execution with identical configuration.
    """
    Execution = type(execution)
    root = execution.parent_execution or execution

    with transaction.atomic():
        
        retry_count = Execution.objects.filter(
            parent_execution=root
        ).count()

        new_execution = Execution.objects.create(
            parent_execution=root,
            re_execution_index=retry_count + 1,
            test_case_execution_order= execution.test_case_execution_order,
            name=root.name + f"_{retry_count+1}",
            test_selection_type=execution.test_selection_type,
            test_suite=execution.test_suite,
            device_selection=execution.device_selection,
            device_group=execution.device_group,
            notification_emails= execution.notification_emails,
            execution_start_time= timezone.now(),
            created_by= request.user,
        )

        if execution.test_selection_type == 0:
            new_execution.individual_test_cases.set(
                execution.individual_test_cases.all()
            )

        old_devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        )
        selected_devices = []
        for dev in old_devices:
            if len(device_tests_info_list.get(str(dev.device.id), [])) > 0:
                selected_devices.append(dev)

        TestSuiteExecutionDevice.objects.bulk_create([
            TestSuiteExecutionDevice(
                test_suite_execution=new_execution,
                device=ed.device,
                connection_protocol= ed.connection_protocol,
                status="pending",
            )
            for ed in selected_devices
        ])

        new_execution.device_count = len(selected_devices)

        new_execution.testcase_count= execution.testcase_count
        new_execution.save(update_fields=["device_count", "testcase_count"])

    return new_execution


# ============================================================================
# TEST CATEGORY VIEWS
# ============================================================================
class TestCategoryListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    API endpoint for listing and creating test categories
    
    GET  → List all categories (with filters, search, pagination)
    POST → Create new category
    """
    # Basic configuration
    # SQL: SELECT * FROM test_category
    queryset = TestCategory.objects.all()

    # Model instance → JSON (for response)
    # JSON → Model instance (for creation)
    serializer_class = TestCategorySerializer

    # Instead of returning 1000 categories
    # Return 10 at a time
    pagination_class = ListViewPagination
    
    # Filtering and ordering configuration
    filter_backends = [
        DjangoFilterBackend,    # Apply filters from filters.py
        filters.OrderingFilter,  # Enable ?ordering=name
        filters.SearchFilter,    # Enable ?search=keyword
    ]
    filterset_class = TestCategoryFilter
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "created", "modified"]
    ordering = ["-created"]  # Default: newest first


class TestCategoryDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, and deleting a test category
    
    GET /api/v1/test-management/test-category/<uuid:pk>/
    - Retrieve detailed information about a test category
    - Includes related test cases (filtered by user permissions)
    - Superusers see all test cases
    - users see only test cases they created
    
    PUT /api/v1/test-management/test-category/<uuid:pk>/
    - Update a test category (full update)
    
    PATCH /api/v1/test-management/test-category/<uuid:pk>/
    - Partially update a test category
    
    DELETE /api/v1/test-management/test-category/<uuid:pk>/
    - Delete a test category
    - Only allowed if category has no test cases
    """
    queryset = TestCategory.objects.all()
    lookup_field = "pk"
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions:
        - Retrieve: TestCategoryDetailSerializer (includes test cases)
        - Update/Delete: TestCategorySerializer (basic fields only)
        """
        if self.request.method == "GET":
            return TestCategoryDetailSerializer
        return TestCategorySerializer
    
    def perform_destroy(self, instance):
        """
        Custom delete logic
        Prevent deletion if category has test cases
        """
        if not instance.is_deletable:
            from django.utils.translation import gettext_lazy as _
            
            raise ValidationError({
                "detail": _(
                    f"Cannot delete category '{instance.name}' because it has "
                    f"{instance.test_case_count} test case(s). "
                    f"Please delete or reassign the test cases first."
                )
            })
        
        super().perform_destroy(instance)

# ============================================================================
# TEST EXECUTIONS VIEWS
# ============================================================================
class TestExecutionListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    API endpoint for listing and creating test executions
    
    GET  → List all test executions (with filters, search, pagination)
    - Superusers see all test executions
    - Regular users see only test executions they created
    POST → Create new test execution
    """
    parser_classes = (MultiPartParser, FormParser)
 
    # Basic configuration

    def get_queryset(self):
        #Only list test executions created by requesting user
        qs = TestExecution.objects.all().select_related("test_suite")

        user = self.request.user
        if user.is_authenticated:
            if user and not user.is_superuser:
                qs = qs.filter(created_by=user)
        else:
            qs = qs.none()

        return qs

    # Model instance → JSON (for response)
    # JSON → Model instance (for creation)
    serializer_class = TestSuiteExecutionSerializer

    # Instead of returning 1000 test executions
    # Return 10 at a time
    pagination_class = ListViewPagination
    
    # Filtering and ordering configuration
    filter_backends = [
        DjangoFilterBackend,    # Apply filters from filters.py
        filters.OrderingFilter,  # Enable ?ordering=name
        filters.SearchFilter,    # Enable ?search=keyword
    ]
    filterset_class = TestSuiteExecutionFilter
    search_fields = ["test_suite__name"]
    ordering_fields = ["created", "test_suite__name"]
    ordering = ["-created"]  # Default: newest first

    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.request.method == "GET":
            return TestSuiteExecutionListSerializer
        return TestSuiteExecutionCreateSerializer


class TestExecutionDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, and deleting a test execution
    
    GET /api/v1/test-management/execution/<uuid:pk>/
    - Retrieve detailed information about a test execution
    
    PUT /api/v1/test-management/execution/<uuid:pk>/
    - Update a test execution (full update)
    
    PATCH /api/v1/test-management/execution/<uuid:pk>/
    - Partially update a test execution
    
    DELETE /api/v1/test-management/execution/<uuid:pk>/
    - Delete a test execution
    """
    parser_classes = (MultiPartParser, FormParser)
    lookup_field = "pk"

    def get_queryset(self):
        #Only list test executions created by requesting user
        qs = TestExecution.objects.all().select_related("test_suite")

        user = self.request.user
        if user.is_authenticated:
            if user and not user.is_superuser:
                qs = qs.filter(created_by=user)
        else:
            qs = qs.none()

        return qs

    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.request.method == "GET" or self.request.method == "DELETE":
            return TestSuiteExecutionSerializer
        return TestSuiteExecutionCreateSerializer

    def perform_destroy(self, instance):
        """Prevent deletion of executed test executions"""
        
        if instance.is_executed:
            from rest_framework.exceptions import ValidationError
            from django.utils.translation import gettext_lazy as _

            raise ValidationError({
                "detail": _(
                    f"Cannot delete executed test executions"
                )
            })
        
        return super().perform_destroy(instance)

class TestExecutionStartView(ProtectedAPIMixin, APIView):
    """
    API endpoint for starting a test execution
    
    POST /api/v1/test-management/execution/<uuid:pk>/start-execution/
    - Start a test execution
    """

    def get_queryset(self):
        #Only list test executions created by requesting user
        qs = TestExecution.objects.all().select_related("test_suite")

        user = self.request.user
        if user.is_authenticated:
            if user and not user.is_superuser:
                qs = qs.filter(created_by=user)
        else:
            qs = qs.none()

        return qs

    def post(self, request, execution_id):
        from ..tasks import execute_test_suite as execute_test_suite_task
        execution = get_object_or_404(TestExecution, id=execution_id)

        # 🔒 Safety checks
        if execution.is_executed:
            return Response(
                {"detail": "Test Execution is already executed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Optional: permission check
        if execution.created_by != request.user:
            return Response(
                {"detail": "Not allowed to start this execution."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update status
        execution.is_executed = True
        execution.save(update_fields=['is_executed'])

        # 🚀 Trigger async execution
        execute_test_suite_task.delay(str(execution.id))

        return Response(
            {
                "execution_id": execution.id,
                "status": execution.status,
                "message": "Execution started successfully"
            },
            status=status.HTTP_202_ACCEPTED
        )

class TestExecutionReExecuteView(ProtectedAPIMixin, APIView):
    """
    API endpoint for re-executing a test execution
    
    POST /api/v1/test-management/execution/<uuid:pk>/re-execute/
    - Re-execute a test execution
    """

    def get_queryset(self):
        #Only list test executions created by requesting user
        qs = TestExecution.objects.all().select_related("test_suite")

        user = self.request.user
        if user.is_authenticated:
            if user and not user.is_superuser:
                qs = qs.filter(created_by=user)
        else:
            qs = qs.none()

        return qs

    def post(self, request, execution_id):
        from ..tasks import execute_test_suite as execute_test_suite_task
        execution = get_object_or_404(TestExecution, pk=execution_id)
        # Optional: permission check
        if execution.created_by != request.user:
            return Response(
                {"detail": "Not allowed to start this execution."},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            new_execution = create_test_execution_clone(execution, request)

            new_execution.is_executed= True
            new_execution.save()

            execute_test_suite_task.delay(str(new_execution.pk))

            return Response(
                {
                    "execution_id": new_execution.pk,
                    "status": new_execution.status,
                    "message": "Execution started successfully"
                },
                status=status.HTTP_202_ACCEPTED
            )
        except Exception as e:
            return Response({"Error": f"{str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TestExecutionReExecuteSelectedView(ProtectedAPIMixin, APIView):
    """
    API endpoint for re-executing selected tests in a test execution
    
    POST /api/v1/test-management/execution/<uuid:pk>/re-execute-selected/
    - Re-execute selected tests in a test execution
    """
    serializer_class = ReExecuteSelectedTestsSerializer
    def get_queryset(self):
        #Only list test executions created by requesting user
        qs = TestExecution.objects.all().select_related("test_suite")

        user = self.request.user
        if user.is_authenticated:
            if user and not user.is_superuser:
                qs = qs.filter(created_by=user)
        else:
            qs = qs.none()

        return qs

    from drf_yasg.utils import swagger_auto_schema
    @swagger_auto_schema(
        request_body=ReExecuteSelectedTestsSerializer
    )
    def post(self, request, execution_id):
        from ..tasks import execute_selected_tests_in_test_execution as start_selected_tests_execution
        execution = get_object_or_404(TestExecution, pk=execution_id)
        # Optional: permission check
        if execution.created_by != request.user:
            return Response(
                {"detail": f"Not allowed to start this execution. As its created by: {execution.created_by}"},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = ReExecuteSelectedTestsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_tests_info = serializer.validated_data["device_tests_info"]

        with transaction.atomic():
            # 🔁 Create new test execution
            new_execution = create_test_execution_clone_for_selected_tests(execution, device_tests_info, request)
            new_execution.is_executed= True
            new_execution.save()
        start_selected_tests_execution.delay(str(new_execution.pk), device_tests_info)
            

        return Response(
            {
                "new_execution_id": new_execution.id,
                "message": "Re-execution for selected tests started successfully"
            },
            status=status.HTTP_202_ACCEPTED
        )

class TestExecutionAbortView(ProtectedAPIMixin, APIView):
    """
    API endpoint for aborting a test execution
    
    POST /api/v1/test-management/execution/<uuid:pk>/abort-execution/
    - Abort a test execution
    """

    def get_queryset(self):
        #Only list test executions created by requesting user
        qs = TestExecution.objects.all().select_related("test_suite")

        user = self.request.user
        if user.is_authenticated:
            if user and not user.is_superuser:
                qs = qs.filter(created_by=user)
        else:
            qs = qs.none()

        return qs

    def post(self, request, execution_id):
        from ..tasks import execute_test_suite as execute_test_suite_task
        execution = get_object_or_404(TestExecution, id=execution_id)

        # Optional: permission check
        if execution.created_by != request.user:
            return Response(
                {"detail": "Not allowed to abort this execution."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            # Get all execution devices
            execution_devices = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution=execution
            ).select_related('device').order_by('device__name')

            print("device_exec>>>>>",execution_devices)
            from ..tasks import abort_test_execution as abort_task
            from ..tasks import abort_device_pending_tests as abort_pending_tests_task

            # Get the device execution
            for device_execution in execution_devices:
                device = device_execution.device
                #First abort all pending tests
                abort_pending_tests_task(execution_id, str(device.id))
                # Get all running test executions for this device
                running_tests = TestCaseExecution.objects.filter(
                    test_suite_execution=device_execution.test_suite_execution,
                    device=device_execution.device,
                    status='running'
                )
                #Abort running tests for this device
                for test in running_tests:
                    abort_task.delay(str(test.pk))

            return Response({
                'success': True,
                'message': f'Aborting running and pending tests for test execution',
                'test_group_execution_id': str(execution_id)
            }, status=status.HTTP_200_OK)

        except TestExecution.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test execution not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error aborting test execution: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to abort test execution',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ============================================================================
# TEST CASE VIEWS
# ============================================================================

class TestCaseListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    GET  → List test cases
    POST → Create test case
    """
    serializer_class = TestCaseSerializer
    pagination_class = ListViewPagination
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = TestCaseFilter
    search_fields = ["name", "test_case_id", "description"]
    ordering_fields = ["name", "created", "modified"]
    ordering = ["-created"]

    def get_queryset(self):
        qs = TestCase.objects.select_related("category")

        # Superusers see all test cases
        if self.request.user.is_superuser:
            return qs

        # Normal users see only their own test cases
        return qs.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TestCaseDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    GET    → Retrieve test case details
    PUT    → Update test case
    PATCH  → Partial update
    DELETE → Delete test case (only if deletable)
    """
    lookup_field = "pk"
    parser_classes = (MultiPartParser, FormParser)
    def get_queryset(self):
        qs = TestCase.objects.select_related("category")

        if self.request.user.is_superuser:
            return qs

        return qs.filter(created_by=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "GET":
            return TestCaseDetailSerializer
        return TestCaseSerializer

    def perform_destroy(self, instance):
        """
        Match admin delete behavior
        """
        if not instance.is_deletable:
            raise ValidationError({
                "detail": (
                    "This test case cannot be deleted because it is part of "
                    "a test suite or has executions."
                )
            })

        instance.delete()


# ============================================================================
# TEST SUITE (TEST GROUP) VIEWS
# ============================================================================
class TestSuiteListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    API endpoint for listing and creating test groups
    
    GET  /api/v1/test-management/test-group/
    - List all test groups (paginated)
    - Superusers see all groups
    - Users see only groups they created
    - Supports filtering by name, is_active, created_by
    - Supports search and ordering
    
    POST /api/v1/test-management/test-group/
    - Create a new test group
    - Automatically sets created_by to request user
    """
    serializer_class = TestSuiteSerializer
    pagination_class = ListViewPagination
    
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = TestSuiteFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created", "modified"]
    ordering = ["-created"]
    
    def get_queryset(self):
        """
        Superusers see all test groups
        Users see only test groups they created
        """
        user = self.request.user
        qs = TestSuite.objects.all().select_related('created_by')
        
        if not user.is_superuser:
            # Users see only their own test groups
            qs = qs.filter(created_by=user)
        
        return qs


class TestSuiteDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, and deleting a test group
    
    GET    /api/v1/test-management/test-group/<uuid:pk>/
    - Retrieve detailed information about a test group
    - Includes list of test cases with ordering
    
    PUT    /api/v1/test-management/test-group/<uuid:pk>/
    - Full update of test group
    - Can update test_case_ids to replace all test cases
    
    PATCH  /api/v1/test-management/test-group/<uuid:pk>/
    - Partial update of test group
    
    DELETE /api/v1/test-management/test-group/<uuid:pk>/
    - Delete test group
    - Only allowed if group has no executions
    """
    lookup_field = "pk"
    
    def get_queryset(self):
        """
        Superusers see all test groups
        Users see only test groups they created
        """
        user = self.request.user
        qs = TestSuite.objects.all().select_related('created_by')
        
        if not user.is_superuser:
            qs = qs.filter(created_by=user)
        
        return qs
    
    def get_serializer_class(self):
        """Use detailed serializer for GET, basic for updates"""
        if self.request.method == "GET":
            return TestSuiteDetailSerializer
        return TestSuiteSerializer
    
    def perform_destroy(self, instance):
        """Custom delete logic - prevent deletion if has executions"""
        if not instance.is_deletable:
            raise ValidationError({
                "detail": _(
                    f"Cannot delete test group '{instance.name}' because it has "
                    f"{instance.execution_count} execution(s). "
                    f"Please delete the executions first."
                )
            })
        
        super().perform_destroy(instance)


# ============================================================================
# TEST CASE LISTING VIEW (WITH CATEGORY FILTER)
# ============================================================================

# class TestCaseListView(ProtectedAPIMixin, generics.ListAPIView):
#     """
#     API endpoint for listing test cases with category filter
    
#     GET /api/v1/test-management/test-cases/
#     - List all test cases (paginated)
#     - Superusers see all test cases
#     - Users see only test cases they created
#     - Filter by category (multiple): ?category=uuid1,uuid2
#     - Filter by test_type, is_active, etc.
#     - Search by name, test_case_id
    
#     Examples:
#     - All test cases: /test-cases/
#     - By category: /test-cases/?category=uuid1&category=uuid2
#     - Active only: /test-cases/?is_active=true
#     - By type: /test-cases/?test_type=1
#     - Search: /test-cases/?search=ping
#     """
#     serializer_class = TestCaseListSerializer
#     pagination_class = ListViewPagination
    
#     filter_backends = [
#         DjangoFilterBackend,
#         filters.OrderingFilter,
#         filters.SearchFilter,
#     ]
#     filterset_class = TestCaseListFilter
#     search_fields = ["name", "test_case_id", "description"]
#     ordering_fields = ["name", "test_case_id", "created", "modified"]
#     ordering = ["-created"]
    
#     def get_queryset(self):
#         """
#         Superusers see all test cases
#         Users see only test cases they created
#         """
#         user = self.request.user
#         qs = TestCase.objects.all().select_related('category', 'created_by')
        
#         if not user.is_superuser:
#             # Users see only their own test cases
#             qs = qs.filter(created_by=user)
        
#         return qs

class ExportAllTestCaseScriptsView(ProtectedAPIMixin,GenericAPIView):
    """
    Export all test case scripts as a ZIP file
    """

    queryset = TestCase.objects.all()

    def get_queryset(self):
        """
        Match admin visibility rules
        """
        qs = super().get_queryset()

        if self.request.user.is_superuser:
            return qs

        return qs.filter(created_by=self.request.user)
    
    def get(self, request, *args, **kwargs):
        # ✅ Match admin queryset behavior
        queryset= self.get_queryset()

        if not queryset.exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {"detail": "No test cases available for export."}
            )

        zip_buffer = build_all_testcases_zip(queryset)

        response = HttpResponse(
            zip_buffer,
            content_type="application/zip",
        )
        response["Content-Disposition"] = (
            'attachment; filename="all_testcase_scripts.zip"'
        )
        return response

# Export view functions for urls.py
test_suite_list = TestSuiteListView.as_view()
test_suite_detail = TestSuiteDetailView.as_view()
# test_case_list_view = TestCaseListView.as_view()
test_category_list = TestCategoryListView.as_view()
test_category_detail = TestCategoryDetailView.as_view()
test_execution_list = TestExecutionListView.as_view()
test_execution_detail = TestExecutionDetailView.as_view()
test_execution_start = TestExecutionStartView.as_view()
test_execution_re_execute = TestExecutionReExecuteView.as_view()
test_execution_re_execute_selected = TestExecutionReExecuteSelectedView.as_view()
test_execution_abort_view = TestExecutionAbortView.as_view()
test_case_list = TestCaseListView.as_view()
test_case_detail = TestCaseDetailView.as_view()
export_all_scripts = ExportAllTestCaseScriptsView.as_view()