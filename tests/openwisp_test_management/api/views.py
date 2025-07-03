from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status

from rest_framework.decorators import api_view

from django.db import transaction
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated



from rest_framework.decorators import action
from rest_framework.response import Response
from .filters import TestSuiteFilter

from django.utils.translation import gettext_lazy as _
from .serializers import TestSuiteListSerializer
from .filters import TestSuiteFilter

from openwisp_controller.config.models import Device 
from openwisp_controller.connection.models import Credentials

from openwisp_controller.connection.models import DeviceConnection 
from .serializers import (
    TestSuiteExecutionListSerializer,
    TestSuiteExecutionSerializer,
    ExecutionDetailsRequestSerializer
)



from openwisp_users.api.mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
# from openwisp_users.api.pagination import LinkHeaderPagination

from ..swapper import load_model
from .filters import TestCategoryFilter, TestCaseFilter
from .serializers import (
    TestCategoryListSerializer,
    TestCategorySerializer,
    TestCaseListSerializer,
    TestCaseSerializer,
    TestSuiteSerializer ,
    # TestSuiteFilter
)

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteCase = load_model("TestSuiteCase")
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")


class ProtectedAPIMixin(BaseProtectedAPIMixin):
    """Base mixin for protected API views"""
    throttle_scope = "test_management"


class TestCategoryListCreateView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    List all test categories or create a new one.
    
    GET: Returns list of test categories with filtering and search
    POST: Creates a new test category
    """
    queryset = TestCategory.objects.all()
    serializer_class = TestCategorySerializer
    filterset_class = TestCategoryFilter
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created", "modified"]
    ordering = ["name"]

    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.request.method == "GET":
            return TestCategoryListSerializer
        return TestCategorySerializer


class TestCategoryDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a test category.
    
    GET: Returns single test category details
    PUT/PATCH: Updates test category
    DELETE: Deletes test category (if no test cases exist)
    """
    queryset = TestCategory.objects.all()
    serializer_class = TestCategorySerializer
    lookup_field = "pk"

    def destroy(self, request, *args, **kwargs):
        """Custom delete to check if category can be deleted"""
        instance = self.get_object()
        
        if not instance.is_deletable:
            return Response(
                {
                    "detail": _("Cannot delete category containing test cases")
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)


class TestCaseListCreateView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    List all test cases or create a new one.
    
    GET: Returns list of test cases with filtering and search
    POST: Creates a new test case
    """
    queryset = TestCase.objects.all().select_related("category")
    serializer_class = TestCaseSerializer
    filterset_class = TestCaseFilter
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "test_case_id", "description"]
    ordering_fields = ["name", "test_case_id", "category__name", "created", "modified"]
    ordering = ["category__name", "name"]

    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.request.method == "GET":
            return TestCaseListSerializer
        return TestCaseSerializer




class TestCaseDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a test case.
    
    GET: Returns single test case details
    PUT/PATCH: Updates test case
    DELETE: Deletes test case (if not in use)
    """
    queryset = TestCase.objects.all().select_related("category")
    serializer_class = TestCaseSerializer
    lookup_field = "pk"

    def destroy(self, request, *args, **kwargs):
        """Custom delete to check if test case can be deleted"""
        instance = self.get_object()
        
        if not instance.is_deletable:
            return Response(
                {
                    "detail": _("Cannot delete test case that is in use")
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Custom update to prevent changing test_case_id"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Prevent changing test_case_id after creation
        if 'test_case_id' in request.data and instance.test_case_id != request.data['test_case_id']:
            return Response(
                {
                    "test_case_id": _("Test Case ID cannot be changed after creation")
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().update(request, *args, **kwargs)



class TestSuiteListCreateView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    List all test suites or create a new one.
    
    GET: Returns list of test suites with filtering and search
    POST: Creates a new test suite
    """
    queryset = TestSuite.objects.all().select_related("category")
    serializer_class = TestSuiteSerializer
    # filterset_class = []
    filterset_class = TestSuiteFilter

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "category__name", "created", "modified"]
    ordering = ["category__name", "name"]

    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.request.method == "GET":
            return TestSuiteListSerializer
        return TestSuiteSerializer




class TestSuiteDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a test suite.
    
    GET: Returns single test suite details with test cases
    PUT/PATCH: Updates test suite
    DELETE: Deletes test suite (if not executed)
    """
    queryset = TestSuite.objects.all().select_related("category")
    serializer_class = TestSuiteSerializer
    lookup_field = "pk"

    def destroy(self, request, *args, **kwargs):
        """Custom delete to check if test suite can be deleted"""
        instance = self.get_object()
        
        if not instance.is_deletable:
            return Response(
                {
                    "detail": _("Cannot delete test suite that has been executed")
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)



class TestSuiteExecutionListCreateView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    List all test suite executions or create a new one.
    GET: Returns list of test suite executions
    POST: Creates a new test suite execution
    """
    queryset = TestSuiteExecution.objects.all().select_related("test_suite")
    serializer_class = TestSuiteExecutionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["test_suite", "is_executed"]
    search_fields = ["test_suite__name"]
    ordering_fields = ["created", "test_suite__name"]
    ordering = ["-created"]

    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.request.method == "GET":
            return TestSuiteExecutionListSerializer
        return TestSuiteExecutionSerializer


class TestSuiteExecutionDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a test suite execution.
    
    GET: Returns execution details with devices
    PUT/PATCH: Updates execution (limited fields)
    DELETE: Deletes execution (if not executed)
    """
    queryset = TestSuiteExecution.objects.all().select_related("test_suite")
    serializer_class = TestSuiteExecutionSerializer
    lookup_field = "pk"
    
    def destroy(self, request, *args, **kwargs):
        """Prevent deletion of executed test suites"""
        instance = self.get_object()
        
        if instance.is_executed:
            return Response(
                {"detail": _("Cannot delete executed test suite executions")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)


@api_view(["GET"])
def available_devices(request):
    """Get devices with working SSH connections"""
    # Get devices with working connections
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
    
    return Response(data)










# Add this new view function
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_all_test_data(request):
    """
    Create all test data in one request:
    1. TestCategory
    2. Two TestCases
    3. TestSuite with TestSuiteCases
    4. TestSuiteExecution with TestSuiteExecutionDevice
    """
    try:
        with transaction.atomic():
            # 1. Create TestCategory
            category = TestCategory.objects.create(
                name="Traffic",
                code="TRF",
                description="Traffic testing category for network performance and throughput validation"
            )
            
            # 2. Create TestCase 1
            test_case_1 = TestCase.objects.create(
                name="Test Case 1",
                test_case_id="TestCase_001",
                category=category,
                description="Primary traffic validation test for basic connectivity and data flow",
                is_active=True,
                test_type=2  # Device Agent
            )
            
            # 3. Create TestCase 2
            test_case_2 = TestCase.objects.create(
                name="Test Case 2",
                test_case_id="TestCase_002",
                category=category,
                description="Secondary traffic validation test for advanced routing and switching",
                is_active=True,
                test_type=2  # Device Agent
            )
            
            # 4. Create TestSuite
            test_suite = TestSuite.objects.create(
                name="Logging and Reboot",
                category=category,
                description="Comprehensive test suite for system logging and reboot functionality",
                is_active=True
            )
            
            # 5. Create TestSuiteCase entries
            TestSuiteCase.objects.create(
                test_suite=test_suite,
                test_case=test_case_1,
                order=1
            )
            
            TestSuiteCase.objects.create(
                test_suite=test_suite,
                test_case=test_case_2,
                order=2
            )
            
            # 6. Create TestSuiteExecution
            execution = TestSuiteExecution.objects.create(
                test_suite=test_suite,
                is_executed=False
            )
            
            # 7. Create TestSuiteExecutionDevice
            try:
                device = Device.objects.get(id="5ec3b03b-a2c4-484c-a896-0f951770f3f5") # rreplace acc to your device id
                TestSuiteExecutionDevice.objects.create(
                    test_suite_execution=execution,
                    device=device,
                    status='pending'
                )
            except Device.DoesNotExist:
                return Response(
                    {"error": "Device with ID 5ec3b03b-a2c4-484c-a896-0f951770f3f5 not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Return success response with created data
            return Response({
                "success": True,
                "message": "All test data created successfully",
                "data": {
                    "category": {
                        "id": str(category.id),
                        "name": category.name,
                        "code": category.code
                    },
                    "test_cases": [
                        {
                            "id": str(test_case_1.id),
                            "name": test_case_1.name,
                            "test_case_id": test_case_1.test_case_id
                        },
                        {
                            "id": str(test_case_2.id),
                            "name": test_case_2.name,
                            "test_case_id": test_case_2.test_case_id
                        }
                    ],
                    "test_suite": {
                        "id": str(test_suite.id),
                        "name": test_suite.name,
                        "test_case_count": 2
                    },
                    "execution": {
                        "id": str(execution.id),
                        "test_suite_name": test_suite.name,
                        "device_count": 1,
                        "status": "pending"
                    }
                }
            }, status=status.HTTP_201_CREATED)
            
    except ValidationError as e:
        return Response(
            {"error": "Validation error", "details": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": "Failed to create test data", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_all_test_data(request):
    """
    Delete all test management data in correct order:
    1. TestSuiteExecutionDevice
    2. TestSuiteExecution
    3. TestSuiteCase
    4. TestSuite
    5. TestCase
    6. TestCategory
    """
    try:
        with transaction.atomic():
            # Count existing records before deletion
            counts_before = {
                'execution_devices': TestSuiteExecutionDevice.objects.count(),
                'executions': TestSuiteExecution.objects.count(),
                'suite_cases': TestSuiteCase.objects.count(),
                'test_suites': TestSuite.objects.count(),
                'test_cases': TestCase.objects.count(),
                'categories': TestCategory.objects.count(),
            }
            
            # Delete in correct order (reverse dependency order)
            
            # 1. Delete TestSuiteExecutionDevice (depends on TestSuiteExecution)
            deleted_execution_devices = TestSuiteExecutionDevice.objects.all().delete()[0]
            
            # 2. Delete TestSuiteExecution (depends on TestSuite)
            deleted_executions = TestSuiteExecution.objects.all().delete()[0]
            
            # 3. Delete TestSuiteCase (depends on TestSuite and TestCase)
            deleted_suite_cases = TestSuiteCase.objects.all().delete()[0]
            
            # 4. Delete TestSuite (depends on TestCategory)
            deleted_test_suites = TestSuite.objects.all().delete()[0]
            
            # 5. Delete TestCase (depends on TestCategory)
            deleted_test_cases = TestCase.objects.all().delete()[0]
            
            # 6. Delete TestCategory (no dependencies)
            deleted_categories = TestCategory.objects.all().delete()[0]
            
            # Count records after deletion (should all be 0)
            counts_after = {
                'execution_devices': TestSuiteExecutionDevice.objects.count(),
                'executions': TestSuiteExecution.objects.count(),
                'suite_cases': TestSuiteCase.objects.count(),
                'test_suites': TestSuite.objects.count(),
                'test_cases': TestCase.objects.count(),
                'categories': TestCategory.objects.count(),
            }
            
            return Response({
                "success": True,
                "message": "All test management data deleted successfully",
                "deleted_counts": {
                    "execution_devices": deleted_execution_devices,
                    "executions": deleted_executions,
                    "suite_cases": deleted_suite_cases,
                    "test_suites": deleted_test_suites,
                    "test_cases": deleted_test_cases,
                    "categories": deleted_categories,
                    "total_deleted": (
                        deleted_execution_devices + 
                        deleted_executions + 
                        deleted_suite_cases + 
                        deleted_test_suites + 
                        deleted_test_cases + 
                        deleted_categories
                    )
                },
                "counts_before": counts_before,
                "counts_after": counts_after,
                "verification": {
                    "all_tables_empty": all(count == 0 for count in counts_after.values()),
                    "details": counts_after
                }
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        return Response(
            {
                "error": "Failed to delete test management data", 
                "details": str(e),
                "message": "Some data may have been partially deleted. Please check the database state."
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )    


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_execution_details(request):
    """
    Get detailed execution information including devices with SSH details
    and test suite information
    """
    # Use serializer for request validation and Swagger documentation
    # serializer = ExecutionDetailsRequestSerializer(data=request.data)
    # if not serializer.is_valid():
    #     return Response(
    #         {"error": "Invalid request data", "details": serializer.errors},
    #         status=status.HTTP_400_BAD_REQUEST
    #     )
    
    # execution_id = serializer.validated_data['execution_id']
    execution_id = "3542c364-3228-4091-8659-08de26f21f15"



    try:
        # Get the test suite execution
        execution = TestSuiteExecution.objects.select_related(
            'test_suite',
            'test_suite__category'
        ).get(id=execution_id)
        
        # Get all devices for this execution
        execution_devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        ).select_related('device')
        
        # Get all device IDs
        device_ids = [exec_device.device.id for exec_device in execution_devices]
        
        # Get all device connections with credentials in one query
        device_connections = {}
        if device_ids:
            connections = DeviceConnection.objects.filter(
                device_id__in=device_ids
            ).select_related('credentials')
            
            for conn in connections:
                device_connections[conn.device_id] = conn
        
        # Build devices list with SSH details
        devices = []
        for exec_device in execution_devices:
            device = exec_device.device
            ssh_detail = {
                "username": "",
                "password": "",
                "port": 22
            }
            
            # Check if device has connection
            if device.id in device_connections:
                device_connection = device_connections[device.id]
                if device_connection.credentials:
                    params = device_connection.credentials.params or {}
                    ssh_detail = {
                        "username": params.get("username", ""),
                        "password": params.get("password", ""),
                        "port": params.get("port", 22)
                    }
            
            device_info = {
                "id": str(device.id),
                "name": device.name,
                "mac_address": device.mac_address,
                "last_ip": device.last_ip,
                "ssh_detail": ssh_detail
            }
            devices.append(device_info)
        
        # Get test suite details with test cases
        test_suite = execution.test_suite
        
        # Get ordered test cases for the suite
        suite_cases = TestSuiteCase.objects.filter(
            test_suite=test_suite
        ).select_related('test_case').order_by('order')
        
        test_cases = []
        for suite_case in suite_cases:
            test_case = suite_case.test_case
            test_case_info = {
                "name": test_case.name,
                "test_case_id": test_case.test_case_id,
                "test_type": test_case.test_type,
                "test_type_display": test_case.get_test_type_display(),
                "order": suite_case.order
            }
            test_cases.append(test_case_info)
        
        # Build response
        response_data = {
            "success": True,
            "execution_id": str(execution.id),
            "devices": devices,
            "testsuite_detail": {
                "testsuite_name": test_suite.name,
                "testsuite_description": test_suite.description,
                "category_detail": {
                    "name": test_suite.category.name,
                    "code": test_suite.category.code
                },
                "test_cases": test_cases
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except TestSuiteExecution.DoesNotExist:
        return Response(
            {"error": f"TestSuiteExecution with id {execution_id} not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": "Failed to get execution details", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )






# Create view instances
test_category_list = TestCategoryListCreateView.as_view()
test_category_detail = TestCategoryDetailView.as_view()
test_case_list = TestCaseListCreateView.as_view()
test_case_detail = TestCaseDetailView.as_view()
test_suite_list = TestSuiteListCreateView.as_view()
test_suite_detail = TestSuiteDetailView.as_view()
test_suite_execution_list = TestSuiteExecutionListCreateView.as_view()
test_suite_execution_detail = TestSuiteExecutionDetailView.as_view()