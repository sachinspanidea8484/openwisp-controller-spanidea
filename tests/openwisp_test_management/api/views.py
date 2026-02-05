from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, pagination, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from django.utils import timezone
from django.http import HttpResponse
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.urls import reverse
import logging
import csv

from tablib import Dataset

from openwisp_users.api.mixins import (
    ProtectedAPIMixin as BaseProtectedAPIMixin,
    FilterByOrganizationManaged,
)
from openwisp_users.api.permissions import (
    DjangoModelPermissions,
    IsOrganizationManager,
)

from openwisp_controller.config.models import Device
from openwisp_controller.connection.models import DeviceConnection
from openwisp_monitoring.monitoring.models import Metric

from openwisp_test_management.utils import build_all_testcases_zip
from ..swapper import load_model
from ..settings import OPENWISP_SERVER_IP

from .filters import (
    TestCategoryFilter,
    TestSuiteFilter,
    TestSuiteExecutionFilter,
    TestCaseFilter,
    TestDeviceGroupFilter,
    DeviceFilterForGroup,
)

from .serializers import (
    TestCategorySerializer,
    TestCategoryDetailSerializer,
    TestCaseSerializer,
    TestCaseMinimalSerializer,
    TestCaseDetailSerializer,
    TestSuiteSerializer,
    TestSuiteDetailSerializer,
    TestDeviceGroupCreateSerializer,
    TestDeviceGroupListSerializer,
    TestDeviceGroupDetailSerializer,
    DeviceForGroupSerializer,
    TestCaseListSerializer,
    TestSuiteExecutionSerializer,
    TestSuiteExecutionCreateSerializer,
    TestSuiteExecutionListSerializer,
    ReExecuteSelectedTestsSerializer,
    TestCaseImportSerializer,
)

from .utilities import TestCasesResource

logger = logging.getLogger(__name__)


# =========================
# Models
# =========================
TestCategory = load_model("TestCategory")
TestExecution = load_model("TestSuiteExecution")
TestSuite = load_model("TestSuite")
TestCase = load_model("TestCase")
TestSuiteCase = load_model("TestSuiteCase")
TestDeviceGroup = load_model("TestDeviceGroup")
TestCaseExecution = load_model("TestCaseExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
ScheduledExecution = load_model("ScheduledExecution")

class ListViewPagination(pagination.PageNumberPagination):
    """Pagination configuration for list views"""
    page_size = 10                    # Default items per page
    page_size_query_param = "page_size"  # Allow user to set page size
    max_page_size = 100               # Maximum allowed page size


class ProtectedAPIMixin(BaseProtectedAPIMixin, FilterByOrganizationManaged):
    """
    Base mixin for all test management API views
    
    Features:
    - Authentication: Bearer token + Session
    - Permissions: IsAuthenticated + DjangoModelPermissions
    - Organization Filtering: Automatic filtering by user's managed orgs
    - Throttling: Rate limiting per scope
    """
    permission_classes = (
        IsAuthenticated,
        DjangoModelPermissions,
        IsOrganizationManager,  # User must manage at least 1 org
    )
    throttle_scope = "test_management"
    organization_field = "organization"  # Field to filter by

class ProtectedExternalAPIMixin(BaseProtectedAPIMixin):
    """
    Base mixin for all test management API views
    Adds authentication and permission requirements
    """
    permission_classes = (
        IsAuthenticated,           # Must be logged in
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

class TestExecutionStartView(ProtectedExternalAPIMixin, APIView):
    """
    API endpoint for starting a test execution
    
    POST /api/v1/test-management/execution/<uuid:pk>/start-execution/
    - Start a test execution
    """

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

class TestExecutionReExecuteView(ProtectedExternalAPIMixin, APIView):
    """
    API endpoint for re-executing a test execution
    
    POST /api/v1/test-management/execution/<uuid:pk>/re-execute/
    - Re-execute a test execution
    """

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

class TestExecutionReExecuteSelectedView(ProtectedExternalAPIMixin, APIView):
    """
    API endpoint for re-executing selected tests in a test execution
    
    POST /api/v1/test-management/execution/<uuid:pk>/re-execute-selected/
    - Re-execute selected tests in a test execution
    """
    serializer_class = ReExecuteSelectedTestsSerializer

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

class TestExecutionAbortView(ProtectedExternalAPIMixin, APIView):
    """
    API endpoint for aborting a test execution
    
    POST /api/v1/test-management/execution/<uuid:pk>/abort-execution/
    - Abort a test execution
    """

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

class TestExecutionHistoryExportView(ProtectedExternalAPIMixin, APIView):
    """
    API endpoint for exporting a test execution history
    
    GET /api/v1/test-management/execution/<uuid:pk>/history/export/
    - Export test execution history
    """

    def get(self, request, execution_id):
        execution = get_object_or_404(TestExecution, id=execution_id)

        # Optional: permission check
        if execution.created_by != request.user:
            return Response(
                {"detail": "Not allowed to export history for this execution."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = (
                f'attachment; filename="execution_{execution_id}_history.csv"'
            )

            writer = csv.writer(response)
            writer.writerow([
                'Test Execution ID',
                'Device Name',
                'Test Case Name',
                'Test Case ID',
                'Test Case Type',
                'Status',
                'Duration',
                'Stdout',
                'Stderr'
            ])

            # Get all execution devices
            execution_devices = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution=execution
            ).select_related('device').order_by('device__name')
            
            print("device_exec>>>>>",execution_devices)
            
            test_case_executions = TestCaseExecution.objects.filter(
                test_suite_execution=execution
            ).select_related('device', 'test_case')
            print("<<<test_case_executions>>>",test_case_executions)
            
            for device_exec in execution_devices:
                device = device_exec.device
                device_test_cases = test_case_executions.filter(device=device)
                
                for test_exec in device_test_cases:
                    # Calculate execution duration
                    execution_duration_seconds = None
                    
                    if test_exec.started_at and test_exec.completed_at:
                        duration = test_exec.completed_at - test_exec.started_at
                        execution_duration_seconds = duration.total_seconds()
                    
                    writer.writerow([
                        str(test_exec.pk),
                        device.name,
                        test_exec.test_case.name,
                        test_exec.test_case.test_case_id,
                        test_exec.test_case.get_test_type_display(),
                        test_exec.status,
                        execution_duration_seconds,
                        test_exec.stdout,
                        test_exec.stderr
                    ])

            return response
        except TestExecution.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test execution not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error exporting test execution data: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to export test execution data',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TestExecutionHistoryView(ProtectedExternalAPIMixin, APIView):
    """
    API endpoint for getting test execution history with enhanced statistics
    
    GET /api/v1/test-management/execution/<uuid:pk>/history/
    - Get test execution data
    """

    def get(self, request, execution_id):
        execution = get_object_or_404(TestExecution, id=execution_id)

        # Optional: permission check
        if execution.created_by != request.user:
            return Response(
                {"detail": "Not allowed to get history for this execution."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:        
            # Get all execution devices
            execution_devices = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution=execution
            ).order_by('device__name')
            
            print("device_exec>>>>>",execution_devices)
            device_ids = execution_devices.values_list('device_id', flat=True)

            devices_map = {
                d.id: d
                for d in Device.all_objects.filter(id__in=device_ids)
            }
            # Get all test case executions
            test_case_executions = TestCaseExecution.objects.filter(
                test_suite_execution=execution
            ).select_related('device', 'test_case')
            print("<<<test_case_executions>>>",test_case_executions)
            
            # Build response data
            devices_data = []
            for device_exec in execution_devices:
                device = devices_map.get(device_exec.device_id)
                device_test_cases = test_case_executions.filter(device_id=device_exec.device_id).order_by("created")
                
                # Calculate statistics
                total = device_test_cases.count()
                success = device_test_cases.filter(status='success').count()
                failed = device_test_cases.filter(status='failed').count()
                completed = success + failed
                
                # Determine overall status
                if total == 0:
                    overall_status = 'pending'
                    percentage = 0
                elif completed == 0:
                    overall_status = 'pending'
                    percentage = 0
                elif failed == 0 and success == total:
                    overall_status = 'success'
                    percentage = 100
                else:
                    overall_status = 'failed'
                    percentage = (success / total * 100) if total > 0 else 0
                
                # Build test cases data
                test_cases_data = []
                for test_exec in device_test_cases:
                    # Calculate execution duration
                    execution_duration = None
                    execution_duration_seconds = None
                    execution_duration_formatted = None
                    
                    if test_exec.started_at and test_exec.completed_at:
                        duration = test_exec.completed_at - test_exec.started_at
                        execution_duration_seconds = duration.total_seconds()
                        
                        # Format duration as human-readable string
                        hours, remainder = divmod(int(execution_duration_seconds), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        
                        if hours > 0:
                            execution_duration_formatted = f"{hours}h {minutes}m {seconds}s"
                        elif minutes > 0:
                            execution_duration_formatted = f"{minutes}m {seconds}s"
                        else:
                            execution_duration_formatted = f"{seconds}s"
                    
                    test_cases_data.append({
                        'id': str(test_exec.pk),
                        'test_case_name': test_exec.test_case.name,
                        'test_case_id': test_exec.test_case.test_case_id,
                        'test_type': test_exec.test_case.get_test_type_display(),
                        'status': test_exec.status,
                        'status_display': test_exec.get_status_display(),
                        'has_log': bool(test_exec.stdout),
                        'can_retry': test_exec.status == 'failed',
                        'started_at': test_exec.started_at.isoformat() if test_exec.started_at else None,
                        'completed_at': test_exec.completed_at.isoformat() if test_exec.completed_at else None,
                        'execution_duration': {
                            'seconds': execution_duration_seconds,
                            'formatted': execution_duration_formatted
                        } if execution_duration_seconds else None,
                        'error_message': test_exec.error_message if test_exec.status == 'failed' else None,
                        'exit_code': test_exec.exit_code,
                        'retry_count': test_exec.retry_count,
                    })
                
                # Calculate device execution duration
                device_duration = None
                device_duration_seconds = None
                device_duration_formatted = None
                
                if device_exec.started_at and device_exec.completed_at:
                    duration = device_exec.completed_at - device_exec.started_at
                    device_duration_seconds = duration.total_seconds()
                    
                    # Format duration as human-readable string
                    hours, remainder = divmod(int(device_duration_seconds), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    if hours > 0:
                        device_duration_formatted = f"{hours}h {minutes}m {seconds}s"
                    elif minutes > 0:
                        device_duration_formatted = f"{minutes}m {seconds}s"
                    else:
                        device_duration_formatted = f"{seconds}s"

                openwisp_base_url = OPENWISP_SERVER_IP

                has_allure_report = bool(device_exec.allure_report_path)  
                connection_protocol = device_exec.connection_protocol  

                allure_report_full_path = f"{openwisp_base_url}/media/{device_exec.allure_report_path}"
                device_status = "Online"
                ping_metric = Metric.objects.filter(
                            object_id=str(device.id),
                            configuration='ping',
                            key='ping',
                    ).first()

                device_status = "Online" if ping_metric and ping_metric.is_healthy else "Offline"
                if device and device.is_deleted:
                    device_status= "Deleted"

                
                device_data = {
                    'device_id': str(device.id),
                    'device_name': device.name,
                    'device_execution_id': str(device_exec.pk),
                    'allure_report_path': device_exec.allure_report_path,
                    'has_allure_report': has_allure_report,
                    'connection_protocol': connection_protocol,''
                    'allure_report_full_path': allure_report_full_path,
                    "device_status" : device_status,
                    "is_deleted" : device.is_deleted,
                    'device_execution_status': device_exec.status,
                    'error_message': device_exec.output if device_exec.status == 'failed' else None,
                    'started_at': device_exec.started_at.isoformat() if device_exec.started_at else None,
                    'completed_at': device_exec.completed_at.isoformat() if device_exec.completed_at else None,
                    'execution_duration': {
                        'seconds': device_duration_seconds,
                        'formatted': device_duration_formatted
                    } if device_duration_seconds else None,
                    'statistics': {
                        'total': total,
                        'success': success,
                        'failed': failed,
                        'completed': completed,
                        'percentage': round(percentage, 2),
                        'overall_status': overall_status
                    },
                    'test_cases': test_cases_data
                }
                
                devices_data.append(device_data)
            
            # Calculate overall execution duration
            overall_start = None
            overall_end = None
            
            # Get earliest start time from all device executions
            for device_exec in execution_devices:
                if device_exec.started_at:
                    if overall_start is None or device_exec.started_at < overall_start:
                        overall_start = device_exec.started_at
            
            # Get latest completion time from all device executions
            for device_exec in execution_devices:
                if device_exec.completed_at:
                    if overall_end is None or device_exec.completed_at > overall_end:
                        overall_end = device_exec.completed_at
            
            overall_duration = None
            overall_duration_seconds = None
            overall_duration_formatted = None
            
            if overall_start and overall_end:
                duration = overall_end - overall_start
                overall_duration_seconds = duration.total_seconds()
                
                # Format duration as human-readable string
                hours, remainder = divmod(int(overall_duration_seconds), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    overall_duration_formatted = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    overall_duration_formatted = f"{minutes}m {seconds}s"
                else:
                    overall_duration_formatted = f"{seconds}s"

            # Build execution summary
            if execution.test_selection_type == 1:
                test_suite_name= execution.test_suite.name
                test_suite_id =str(execution.test_suite.pk)
                total_test_cases= execution.test_suite.test_case_count
            elif execution.test_selection_type ==0 :
                test_suite_name= "individual execution"
                test_suite_id = None
                total_test_cases= len(execution.individual_test_cases.all())

            scheduled_time=None
            try:
                is_scheduled_execution= ScheduledExecution.objects.filter(execution=execution).first()
                if is_scheduled_execution:
                    scheduled_time= is_scheduled_execution.scheduled_time
                    
            except ScheduledExecution.DoesNotExist:
                is_scheduled_execution = None
                scheduled_time = None
            execution_data = {
                'execution_id': str(execution.pk),
                'execution_start_time' : execution.execution_start_time,
                'execution_name' : execution.name,
                'test_suite_name': test_suite_name,
                'test_suite_id': test_suite_id,
                'total_devices': execution.device_count,
                'total_test_cases': total_test_cases,
                'is_executed': execution.is_executed,
                'created': execution.created.isoformat() if execution.created else None,
                'started_at': overall_start.isoformat() if overall_start else None,
                'completed_at': overall_end.isoformat() if overall_end else None,
                'status_display': execution.status_display,  # <-- added
                'status': execution.status,  # <-- added
                'scheduled_time': scheduled_time,
                'device_count': execution.device_count,  # <-- added
                'testcase_count': execution.testcase_count,  # <-- added

                'overall_execution_duration': {
                    'seconds': overall_duration_seconds,
                    'formatted': overall_duration_formatted
                } if overall_duration_seconds else None,
                'summary_statistics': {
                    'total_test_runs': sum(d['statistics']['total'] for d in devices_data),
                    'total_success': sum(d['statistics']['success'] for d in devices_data),
                    'total_failed': sum(d['statistics']['failed'] for d in devices_data),
                    'total_completed': sum(d['statistics']['completed'] for d in devices_data),
                    'devices_success': sum(1 for d in devices_data if d['statistics']['overall_status'] == 'success'),
                    'devices_failed': sum(1 for d in devices_data if d['statistics']['overall_status'] == 'failed'),
                    'devices_pending': sum(1 for d in devices_data if d['statistics']['overall_status'] == 'pending'),
                },
                'devices': devices_data
            }
            
            # Add average execution time for test cases
            all_durations = []
            for device_data in devices_data:
                for test_case in device_data['test_cases']:
                    if test_case.get('execution_duration') and test_case['execution_duration'].get('seconds'):
                        all_durations.append(test_case['execution_duration']['seconds'])
            
            if all_durations:
                avg_duration = sum(all_durations) / len(all_durations)
                hours, remainder = divmod(int(avg_duration), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    avg_duration_formatted = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    avg_duration_formatted = f"{minutes}m {seconds}s"
                else:
                    avg_duration_formatted = f"{seconds}s"
                    
                execution_data['average_test_duration'] = {
                    'seconds': round(avg_duration, 2),
                    'formatted': avg_duration_formatted
                }
            
            re_execution_data = []
            for r in execution.re_executions.all().order_by("re_execution_index", "created"):
                re_execution_data.append({
                    "id": r.id,
                    "name": r.name,
                    "created": r.created.isoformat() if r.created else None,
                    "history_url": reverse("admin:test_management_testsuiteexecution_history", args=[r.id]),
                })
            execution_data["re_execution_data"]= re_execution_data
            
            return Response({
                'success': True,
                'data': execution_data
            }, status=status.HTTP_200_OK)
        except TestExecution.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test execution not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error getting test execution history: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve test execution history',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TestExecutionAllHistoryView(ProtectedExternalAPIMixin, APIView):
    """
    API endpoint to get test execution history for all child test executions
    
    GET /api/v1/test-management/execution/<uuid:pk>/all-history/
    - Get history for all child test executions
    """

    def get(self, request, execution_id):
        current_execution = get_object_or_404(TestExecution, id=execution_id)

        # Optional: permission check
        if current_execution.created_by != request.user:
            return Response(
                {"detail": "Not allowed to get history for this execution."},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            execution = current_execution.parent_execution or current_execution
            
            if execution.test_selection_type == 1:
                test_suite_name= execution.test_suite.name
                test_suite_id =str(execution.test_suite.pk)
                total_test_cases= execution.test_suite.test_case_count
            elif execution.test_selection_type ==0 :
                test_suite_name= "individual execution"
                test_suite_id = None
                total_test_cases= len(execution.individual_test_cases.all())

            scheduled_time=None
            try:
                is_scheduled_execution= ScheduledExecution.objects.filter(execution=execution).first()
                if is_scheduled_execution:
                    scheduled_time= is_scheduled_execution.scheduled_time
                    
            except ScheduledExecution.DoesNotExist:
                is_scheduled_execution = None
                scheduled_time = None
            execution_data = {
                'execution_id': str(execution.pk),
                'execution_name' : execution.name,
                'test_suite_name': test_suite_name,
                'test_suite_id': test_suite_id,
                'created': execution.created.isoformat() if execution.created else None,
                'execution_start_time' : execution.execution_start_time
            }
            
            re_execution_data = []
            
            for r in execution.re_executions.all().order_by("-re_execution_index", "created"):
                re_execution_data.append({
                    "id": r.id,
                    "name": r.name,
                    "status_display": r.status_display,
                    "created": r.created.isoformat() if r.created else None,
                    'execution_start_time' : r.execution_start_time.isoformat() if r.execution_start_time else None,
                    "history_url": reverse("admin:test_management_testsuiteexecution_history", args=[r.id]),
                })
            re_execution_data.append({
                "id": str(execution.pk),
                "name": execution.name,
                "status_display": execution.status_display,
                "created": execution.created.isoformat() if execution.created else None,
                'execution_start_time' : execution.execution_start_time.isoformat() if execution.execution_start_time else None,
                "history_url": reverse("admin:test_management_testsuiteexecution_history", args=[execution.pk]),
            })
            execution_data["re_execution_data"]= re_execution_data
            
            return Response({
                'success': True,
                'data': execution_data
            }, status=status.HTTP_200_OK)
        except TestExecution.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test execution not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error getting execution history: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve execution history',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class TestExecutionAvailableDevicesView(ProtectedExternalAPIMixin, APIView):
    """
    API endpoint to Get devices with working connections
    
    GET /api/v1/test-management/execution/available-devices/
    - Get devices with working connections
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

    def get(self, request):
        try:
            working_device_ids = DeviceConnection.objects.filter(
                is_working=True,
                enabled=True
            ).values_list('device_id', flat=True)
            
            devices = Device.objects.filter(
                id__in=working_device_ids
            ).select_related('organization')
            
            # Simple serialization
            data = [
                {
                    'id': str(device.id),
                    'name': device.name,
                    'organization': device.organization.name
                }
                for device in devices
            ]
            if not data or data == []:
                return Response({
                    'data': data,
                    'details' : "No working device found."
                })
            return Response(data)
        except Exception as e:
            logger.error(f"Error getting available devices: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to get available devices',
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


class TestCaseExportApiView(ProtectedAPIMixin, APIView):
    SUPPORTED_FORMATS= ("xlsx", "csv")
   
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return TestCase.objects.all()
        return TestCase.objects.filter(created_by= user)
    
  
    def get(self, request, export_format):
       

        export_format = export_format.lower()
        if export_format not in self.SUPPORTED_FORMATS : 
            raise ValidationError(
                f"Invalid format. Supported Formats:{', '.join(self.SUPPORTED_FORMATS)}"
            )
        try:
            queryset= self.get_queryset()
            print("queryset", queryset)
            if not queryset.exists():
                return HttpResponse(
                    "No test case available for export.",
                    status=status.HTTP_204_NO_CONTENT,
                    content_type="text/plain",
                )
            
            resource = TestCasesResource()
            dataset= resource.export(queryset)
        
            file_map = {
                "xlsx": (
                    dataset.xlsx,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                "csv": (dataset.csv, "text/csv"),
            
            }
        
            file_data, content_type = file_map[export_format]
        
            response = HttpResponse(file_data, content_type=content_type)
        
            response["Content-Disposition"] = (
                f'attachment; filename="test_cases.{export_format}"'
            )
            return response
        except Exception as e:
            return HttpResponse(
                "An error occurred while exporting test cases.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content_type="text/plain",
            )

class TestCaseImportApiView(ProtectedAPIMixin, generics.CreateAPIView):
    serializer_class= TestCaseImportSerializer
    parser_classes = (MultiPartParser, FormParser)
    queryset = TestCase.objects.none()
    def create(self, request , *args, **kwargs):
        serializer = TestCaseImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file = serializer.validated_data["file"]
        filename= file.name.lower()
        resource = TestCasesResource()

        dataset = Dataset()
        
        if filename.endswith(".xlsx"):
            file.seek(0)
            dataset.xlsx = file.read()
        elif filename.endswith(".csv"):
            file.seek(0)
            text= file.read().decode("utf-8")
            dataset.load(text,format="csv")
        try:

            result = resource.import_data(
                dataset,
                dry_run=False,
                raise_errors=True,
            )
        except Exception as e:
            return Response(
                {"message": "Import failed", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "message": "Import completed successfully",
                "created": result.totals["new"],
                "updated": result.totals["update"],
                "errors": result.totals["error"],
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================================
# TEST SUITE (GROUP) VIEWS
# ============================================================================
class TestSuiteListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    GET  → list test groups 
    POST → create test group
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
    queryset = TestSuite.objects.all()


class TestSuiteDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    GET    → detail with test_cases_detail 
    PUT/PATCH → update accepts test_case_ids[]
    Delete test case (only if deletable)
    """
    queryset = TestSuite.objects.all()

    def get_serializer_class(self):
        if self.request.method == "GET":
            return TestSuiteDetailSerializer
        return TestSuiteSerializer

    def perform_destroy(self, instance):
        if not instance.is_deletable:
            raise ValidationError({
                "detail": _(
                    f"Cannot delete test group '{instance.name}' because it has executions."
                )
            })
        super().perform_destroy(instance)


# ============================================================================
# TEST CASES BY CATEGORY (supports multiple category IDs)
# ============================================================================
class TestCasesByCategoryView(ProtectedAPIMixin, generics.ListAPIView):
    """
    GET /test-management/test-cases-by-category/?category_ids=<uuid>,<uuid>
    - If no category_ids provided → returns all test cases
    """
    serializer_class = TestCaseMinimalSerializer

    def get_queryset(self):
        qs = TestCase.objects.select_related("category").all()
        # Scope by user
        if not self.request.user.is_superuser:
            qs = qs.filter(created_by=self.request.user)
        # Filter by category_ids if provided
        category_ids = self.request.query_params.get("category_ids", "").strip()
        if category_ids:
            id_list = [cid.strip() for cid in category_ids.split(",") if cid.strip()]
            if id_list:
                qs = qs.filter(category__id__in=id_list)
        return qs


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



# ============================================================================
# TEST DEVICE GROUP VIEWS
# ============================================================================

class TestDeviceGroupListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    API endpoint for listing and creating test device groups
    GET  /api/test-management/device-group/
    POST /api/test-management/device-group/
    """
    queryset = TestDeviceGroup.objects.all().select_related("organization")
    pagination_class = ListViewPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = TestDeviceGroupFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "organization", "created", "modified"]
    ordering = ["-created"]

    def get_serializer_class(self):
        """
        Use different serializer for different actions:
        - POST (create): TestDeviceGroupCreateSerializer
        - GET (list): TestDeviceGroupListSerializer
        """
        if self.request.method == "POST":
            return TestDeviceGroupCreateSerializer
        return TestDeviceGroupListSerializer

    def perform_create(self, serializer):
        """
        Hook called after serializer validation
        Can add custom logic here if needed
        """
        serializer.save()


class TestDeviceGroupDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, and deleting a device group
    
    GET /api/test-management/device-group/{id}/
    - Get detailed info about a device group
    - Includes list of all devices in the group
    PUT /api/test-management/device-group/{id}/
    - Update device group (full update)
    - Can update devices by sending device_ids array
    PATCH /api/test-management/device-group/{id}/
    - Partial update
    - Only fields sent will be updated
    DELETE /api/test-management/device-group/{id}/
    - Delete device group
    """
    queryset = TestDeviceGroup.objects.all().select_related("organization")
    lookup_field = "pk"

    def get_serializer_class(self):
        """
        Use different serializer based on HTTP method:
        - GET: TestDeviceGroupDetailSerializer (includes devices_detail)
        - PUT/PATCH: TestDeviceGroupDetailSerializer (accepts device_ids)
        - DELETE: doesn't use serializer
        """
        return TestDeviceGroupDetailSerializer

    def perform_destroy(self, instance):
        """
        Hook before deletion
        Can add checks here if needed (e.g., prevent deletion if in use)
        """
        super().perform_destroy(instance)


# ============================================================================
# DEVICE LISTING API (FOR ADDING TO GROUPS)
# ============================================================================

class DeviceListByOrganizationView(ProtectedAPIMixin, generics.ListAPIView):
    """
    API endpoint to get devices available for adding to a group
    
    GET /api/test-management/devices-by-organization/?organization={org_id}
    Returns all devices from specified organization that user has access to
    """
    serializer_class = DeviceForGroupSerializer
    pagination_class = ListViewPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = DeviceFilterForGroup
    search_fields = ["name", "model"]
    ordering_fields = ["name", "model", "organization"]
    ordering = ["name"]

    def get_queryset(self):
        """
        Return devices from specified organization
        Apply user permission filtering
        """
        # Start with all devices
        qs = Device.objects.select_related("organization").filter(
            is_deleted=False
        )
        
        # Superusers see all devices
        if self.request.user.is_superuser:
            return qs
        
        # Non-superusers only see devices from their managed organizations
        return qs.filter(
            organization_id__in=self.request.user.organizations_managed
        )

# Export view functions for urls.py
test_suite_list = TestSuiteListView.as_view()
test_suite_detail = TestSuiteDetailView.as_view()

test_case_list = TestCaseListView.as_view()
test_case_detail = TestCaseDetailView.as_view()
test_cases_by_category = TestCasesByCategoryView.as_view()

test_category_list = TestCategoryListView.as_view()
test_category_detail = TestCategoryDetailView.as_view()

test_execution_list = TestExecutionListView.as_view()
test_execution_detail = TestExecutionDetailView.as_view()
test_execution_start = TestExecutionStartView.as_view()
test_execution_re_execute = TestExecutionReExecuteView.as_view()
test_execution_re_execute_selected = TestExecutionReExecuteSelectedView.as_view()
test_execution_abort_view = TestExecutionAbortView.as_view()
test_execution_history_export = TestExecutionHistoryExportView.as_view()
test_execution_history = TestExecutionHistoryView.as_view()
test_execution_all_history = TestExecutionAllHistoryView.as_view()
test_execution_available_devices = TestExecutionAvailableDevicesView.as_view()

export_all_scripts = ExportAllTestCaseScriptsView.as_view()

device_group_list = TestDeviceGroupListView.as_view()
device_group_detail = TestDeviceGroupDetailView.as_view()
devices_by_organization = DeviceListByOrganizationView.as_view()

test_case_export = TestCaseExportApiView.as_view()
test_case_import = TestCaseImportApiView.as_view()
