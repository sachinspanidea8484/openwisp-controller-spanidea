from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status

from rest_framework.decorators import api_view
from rest_framework.views import APIView
from django.utils import timezone

import logging
logger = logging.getLogger(__name__)

from django.db import transaction
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated



from rest_framework.decorators import action
from rest_framework.response import Response
from .filters import TestSuiteFilter

from django.utils.translation import gettext_lazy as _
from .serializers import TestSuiteListSerializer
from .filters import TestSuiteFilter
from ..base.models import TestExecutionStatus

from openwisp_controller.config.models import Device 
from openwisp_controller.connection.models import Credentials

from openwisp_controller.connection.models import DeviceConnection 
from .serializers import (
    TestSuiteExecutionListSerializer,
    TestSuiteExecutionSerializer,
    ExecutionDetailsRequestSerializer,
    DeviceTestDataRequestSerializer,
    TestCaseExecutionResultSerializer
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
TestCaseExecution = load_model("TestCaseExecution")




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
                test_type=1  # Device Agent
            )
            
            # 3. Create TestCase 2
            test_case_2 = TestCase.objects.create(
                name="Test Case 2",
                test_case_id="TestCase_002",
                category=category,
                description="Secondary traffic validation test for advanced routing and switching",
                is_active=True,
                test_type=1  # Device Agent
            )



            test_case_3 = TestCase.objects.create(
             name="Test Case 3",
             test_case_id="TestCase_003",
             category=category,
             description="Load test to verify device performance under high traffic conditions",
             is_active=True,
             test_type=1  # Device Agent
            )

            test_case_4 = TestCase.objects.create(
    name="Test Case 4",
    test_case_id="TestCase_004",
    category=category,
    description="Failover test to validate automatic recovery mechanisms",
    is_active=True,
    test_type=1  # Device Agent
            )

            test_case_5 = TestCase.objects.create(
    name="Test Case 5",
    test_case_id="TestCase_005",
    category=category,
    description="Security test to evaluate firewall and intrusion prevention functionality",
    is_active=True,
    test_type=1  # Device Agent
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

            TestSuiteCase.objects.create(
                test_suite=test_suite,
                test_case=test_case_3,
                order=3
            )
            
            TestSuiteCase.objects.create(
                test_suite=test_suite,
                test_case=test_case_4,
                order=4
            )
            TestSuiteCase.objects.create(
                test_suite=test_suite,
                test_case=test_case_5,
                order=5
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
                        },
                         {
                            "id": str(test_case_3.id),
                            "name": test_case_3.name,
                            "test_case_id": test_case_3.test_case_id
                        },
                        {
                            "id": str(test_case_4.id),
                            "name": test_case_4.name,
                            "test_case_id": test_case_4.test_case_id
                        },
                         {
                            "id": str(test_case_5.id),
                            "name": test_case_5.name,
                            "test_case_id": test_case_5.test_case_id
                        },

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
    1. TestCaseExecution
    2. TestSuiteExecutionDevice
    3. TestSuiteExecution
    4. TestSuiteCase
    5. TestSuite
    6. TestCase
    7. TestCategory
    """
    try:
        with transaction.atomic():
            # Count existing records before deletion
            counts_before = {
                'test_case_executions': TestCaseExecution.objects.count(),
                'execution_devices': TestSuiteExecutionDevice.objects.count(),
                'executions': TestSuiteExecution.objects.count(),
                'suite_cases': TestSuiteCase.objects.count(),
                'test_suites': TestSuite.objects.count(),
                'test_cases': TestCase.objects.count(),
                'categories': TestCategory.objects.count(),
            }
            
            # Delete in correct order (reverse dependency order)
            
            # 1. Delete TestCaseExecution (depends on TestSuiteExecution, Device, TestCase)
            deleted_test_case_executions = TestCaseExecution.objects.all().delete()[0]
            
            # 2. Delete TestSuiteExecutionDevice (depends on TestSuiteExecution, Device)
            deleted_execution_devices = TestSuiteExecutionDevice.objects.all().delete()[0]
            
            # 3. Delete TestSuiteExecution (depends on TestSuite)
            deleted_executions = TestSuiteExecution.objects.all().delete()[0]
            
            # 4. Delete TestSuiteCase (depends on TestSuite and TestCase)
            deleted_suite_cases = TestSuiteCase.objects.all().delete()[0]
            
            # 5. Delete TestSuite (depends on TestCategory)
            deleted_test_suites = TestSuite.objects.all().delete()[0]
            
            # 6. Delete TestCase (depends on TestCategory)
            deleted_test_cases = TestCase.objects.all().delete()[0]
            
            # 7. Delete TestCategory (no dependencies)
            deleted_categories = TestCategory.objects.all().delete()[0]
            
            # Count records after deletion (should all be 0)
            counts_after = {
                'test_case_executions': TestCaseExecution.objects.count(),
                'execution_devices': TestSuiteExecutionDevice.objects.count(),
                'executions': TestSuiteExecution.objects.count(),
                'suite_cases': TestSuiteCase.objects.count(),
                'test_suites': TestSuite.objects.count(),
                'test_cases': TestCase.objects.count(),
                'categories': TestCategory.objects.count(),
            }
            
            # Calculate total deleted
            total_deleted = (
                deleted_test_case_executions +
                deleted_execution_devices + 
                deleted_executions + 
                deleted_suite_cases + 
                deleted_test_suites + 
                deleted_test_cases + 
                deleted_categories
            )
            
            return Response({
                "success": True,
                "message": "All test management data deleted successfully",
                "deleted_counts": {
                    "test_case_executions": deleted_test_case_executions,
                    "execution_devices": deleted_execution_devices,
                    "executions": deleted_executions,
                    "suite_cases": deleted_suite_cases,
                    "test_suites": deleted_test_suites,
                    "test_cases": deleted_test_cases,
                    "categories": deleted_categories,
                    "total_deleted": total_deleted
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


# Alternative version with force delete (if you want to bypass foreign key constraints)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def force_delete_all_test_data(request):
    """
    Force delete all test management data by disabling foreign key checks
    WARNING: This bypasses all foreign key constraints and should be used with caution
    """
    try:
        with transaction.atomic():
            # Count existing records before deletion
            counts_before = {
                'test_case_executions': TestCaseExecution.objects.count(),
                'execution_devices': TestSuiteExecutionDevice.objects.count(),
                'executions': TestSuiteExecution.objects.count(),
                'suite_cases': TestSuiteCase.objects.count(),
                'test_suites': TestSuite.objects.count(),
                'test_cases': TestCase.objects.count(),
                'categories': TestCategory.objects.count(),
            }
            
            # Force delete all records without checking foreign keys
            from django.db import connection
            cursor = connection.cursor()
            
            # Disable foreign key checks (MySQL/SQLite)
            if connection.vendor == 'mysql':
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            elif connection.vendor == 'sqlite':
                cursor.execute("PRAGMA foreign_keys = OFF")
            
            try:
                # Delete all records
                deleted_counts = {}
                
                # Delete in any order since we disabled FK checks
                deleted_counts['test_case_executions'] = TestCaseExecution.objects.all().delete()[0]
                deleted_counts['execution_devices'] = TestSuiteExecutionDevice.objects.all().delete()[0]
                deleted_counts['executions'] = TestSuiteExecution.objects.all().delete()[0]
                deleted_counts['suite_cases'] = TestSuiteCase.objects.all().delete()[0]
                deleted_counts['test_suites'] = TestSuite.objects.all().delete()[0]
                deleted_counts['test_cases'] = TestCase.objects.all().delete()[0]
                deleted_counts['categories'] = TestCategory.objects.all().delete()[0]
                
            finally:
                # Re-enable foreign key checks
                if connection.vendor == 'mysql':
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                elif connection.vendor == 'sqlite':
                    cursor.execute("PRAGMA foreign_keys = ON")
            
            # Count records after deletion
            counts_after = {
                'test_case_executions': TestCaseExecution.objects.count(),
                'execution_devices': TestSuiteExecutionDevice.objects.count(),
                'executions': TestSuiteExecution.objects.count(),
                'suite_cases': TestSuiteCase.objects.count(),
                'test_suites': TestSuite.objects.count(),
                'test_cases': TestCase.objects.count(),
                'categories': TestCategory.objects.count(),
            }
            
            total_deleted = sum(deleted_counts.values())
            
            return Response({
                "success": True,
                "message": "All test management data force deleted successfully",
                "deleted_counts": {
                    **deleted_counts,
                    "total_deleted": total_deleted
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
                "error": "Failed to force delete test management data", 
                "details": str(e),
                "message": "Some data may have been partially deleted. Please check the database state."
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Additional utility function to check data before deletion
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_test_data_counts(request):
    """
    Check current counts of all test management data
    """
    try:
        counts = {
            'test_case_executions': TestCaseExecution.objects.count(),
            'execution_devices': TestSuiteExecutionDevice.objects.count(),
            'executions': TestSuiteExecution.objects.count(),
            'suite_cases': TestSuiteCase.objects.count(),
            'test_suites': TestSuite.objects.count(),
            'test_cases': TestCase.objects.count(),
            'categories': TestCategory.objects.count(),
        }
        
        total_records = sum(counts.values())
        
        return Response({
            "success": True,
            "message": "Test management data counts retrieved successfully",
            "counts": counts,
            "total_records": total_records,
            "has_data": total_records > 0
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {
                "error": "Failed to retrieve test management data counts", 
                "details": str(e)
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


class AddDeviceTestDataView(ProtectedAPIMixin, generics.CreateAPIView):
    """
    Create device test data in one request:
    1. TestCategory (Traffic)
    2. Two TestCases (Device Agent type)
    3. TestSuite with TestSuiteCases
    4. TestSuiteExecution with TestSuiteExecutionDevice
    """
    serializer_class = DeviceTestDataRequestSerializer
    queryset = TestSuiteExecution.objects.none()  # ← ADD THIS DUMMY QUERYSET
    
    def create(self, request, *args, **kwargs):  # ← CHANGE post TO create
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        device_id = serializer.validated_data['device_id']
        try:
            with transaction.atomic():
                # 1. Create or get TestCategory
                category, created = TestCategory.objects.get_or_create(
                    name="Traffic",
                    defaults={
                        'code': "TRF",
                        'description': "Traffic testing category for network performance and throughput validation"
                    }
                )
                
                # 2. Create TestCase 1
                test_case_1 = TestCase.objects.create(
                    name="Test Case 1",
                    test_case_id="TestCase_001",
                    category=category,
                    description="Primary traffic validation test for basic connectivity and data flow using device agent",
                    is_active=True,
                    test_type=2  # Device Agent
                )
                
                # 3. Create TestCase 2
                test_case_2 = TestCase.objects.create(
                    name="Test Case 2",
                    test_case_id="TestCase_004",
                    category=category,
                    description="Secondary traffic validation test for advanced routing and switching using device agent",
                    is_active=True,
                    test_type=2  # Device Agent
                )
                
                # 4. Create TestSuite
                test_suite = TestSuite.objects.create(
                    name="Logging and Reboot",
                    category=category,
                    description="Comprehensive test suite for system logging and reboot functionality using device agents",
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
                    device = Device.objects.get(id=device_id)
                    TestSuiteExecutionDevice.objects.create(
                        test_suite_execution=execution,
                        device=device,
                        status='pending'
                    )
                except Device.DoesNotExist:
                    return Response(
                        {"error": f"Device with ID {device_id} not found"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Return success response with created data
                return Response({
                    "success": True,
                    "message": "All device test data created successfully",
                    "data": {
                        "category": {
                            "id": str(category.id),
                            "name": category.name,
                            "code": category.code,
                            "created": created
                        },
                        "test_cases": [
                            {
                                "id": str(test_case_1.id),
                                "name": test_case_1.name,
                                "test_case_id": test_case_1.test_case_id,
                                "test_type": "Device Agent"
                            },
                            {
                                "id": str(test_case_2.id),
                                "name": test_case_2.name,
                                "test_case_id": test_case_2.test_case_id,
                                "test_type": "Device Agent"
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
                            "device_id": str(device_id),
                            "device_name": device.name,
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
                {"error": "Failed to create device test data", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AddRobotTestDataView(ProtectedAPIMixin, generics.CreateAPIView):
    """
    Create robot test data in one request:
    1. TestCategory (Wifi)
    2. Two TestCases (Robot Framework type)
    3. TestSuite with TestSuiteCases
    4. TestSuiteExecution with TestSuiteExecutionDevice
    """
    serializer_class = DeviceTestDataRequestSerializer
    queryset = TestSuiteExecution.objects.none()  # ← ADD THIS DUMMY QUERYSET
    
    def create(self, request, *args, **kwargs):  # ← CHANGE post TO create
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        device_id = serializer.validated_data['device_id']
        
        try:
            with transaction.atomic():
                # 1. Create or get TestCategory
                category, created = TestCategory.objects.get_or_create(
                    name="Wifi",
                    defaults={
                        'code': "WF",
                        'description': "Wireless networking and connectivity testing category for WiFi interfaces, bridging, and WAN connectivity validation"
                    }
                )
                
                # 2. Create TestCase 1
                test_case_1 = TestCase.objects.create(
                    name="Ethernet (LAN) Bridging",
                    test_case_id="BB-TRF-BRG-001",
                    category=category,
                    description="Validates Ethernet LAN bridging functionality, including bridge configuration, traffic forwarding, and network connectivity across bridge interfaces",
                    is_active=True,
                    test_type=1  # Robot Framework
                )
                
                # 3. Create TestCase 2
                test_case_2 = TestCase.objects.create(
                    name="Wifi Wan Interface",
                    test_case_id="BB-INT-WWAN-001",
                    category=category,
                    description="Comprehensive testing of WiFi WAN interface functionality including connection establishment, authentication, data transmission, and failover scenarios",
                    is_active=True,
                    test_type=1  # Robot Framework
                )
                
                # 4. Create TestSuite
                test_suite = TestSuite.objects.create(
                    name="Ether and Wifi For Robot",
                    category=category,
                    description="Comprehensive Robot Framework test suite covering Ethernet bridging and WiFi WAN interface validation for network connectivity and performance testing",
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
                    device = Device.objects.get(id=device_id)
                    TestSuiteExecutionDevice.objects.create(
                        test_suite_execution=execution,
                        device=device,
                        status='pending'
                    )
                except Device.DoesNotExist:
                    return Response(
                        {"error": f"Device with ID {device_id} not found"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Return success response with created data
                return Response({
                    "success": True,
                    "message": "All robot test data created successfully",
                    "data": {
                        "category": {
                            "id": str(category.id),
                            "name": category.name,
                            "code": category.code,
                            "created": created
                        },
                        "test_cases": [
                            {
                                "id": str(test_case_1.id),
                                "name": test_case_1.name,
                                "test_case_id": test_case_1.test_case_id,
                                "test_type": "Robot Framework"
                            },
                            {
                                "id": str(test_case_2.id),
                                "name": test_case_2.name,
                                "test_case_id": test_case_2.test_case_id,
                                "test_type": "Robot Framework"
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
                            "device_id": str(device_id),
                            "device_name": device.name,
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
                {"error": "Failed to create robot test data", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )        


        
# First API - Device Test Data
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_device_test_data(request):
    """
    Create device test data in one request:
    1. TestCategory (Traffic)
    2. Two TestCases (Device Agent type)
    3. TestSuite with TestSuiteCases
    4. TestSuiteExecution with TestSuiteExecutionDevice
    """
    try:
        # Get device_id from request data
        # device_id = request.data.get('device_id')
        device_id = '6c02259d-558e-48fc-a5ec-773a464d951a'


        if not device_id:
            return Response(
                {"error": "device_id is required in request bodysss"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        with transaction.atomic():
            # 1. Create or get TestCategory
            category, created = TestCategory.objects.get_or_create(
                name="Traffic",
                defaults={
                    'code': "TRF",
                    'description': "Traffic testing category for network performance and throughput validation"
                }
            )
            
            # 2. Create TestCase 1
            test_case_1 = TestCase.objects.create(
                name="Test Case 1",
                test_case_id="TestCase_001",
                category=category,
                description="Primary traffic validation test for basic connectivity and data flow using device agent",
                is_active=True,
                test_type=2  # Device Agent
            )
            
            # 3. Create TestCase 2
            test_case_2 = TestCase.objects.create(
                name="Test Case 2",
                test_case_id="TestCase_004",
                category=category,
                description="Secondary traffic validation test for advanced routing and switching using device agent",
                is_active=True,
                test_type=2  # Device Agent
            )
            
            # 4. Create TestSuite
            test_suite = TestSuite.objects.create(
                name="Logging and Reboot",
                category=category,
                description="Comprehensive test suite for system logging and reboot functionality using device agents",
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
                device = Device.objects.get(id=device_id)
                TestSuiteExecutionDevice.objects.create(
                    test_suite_execution=execution,
                    device=device,
                    status='pending'
                )
            except Device.DoesNotExist:
                return Response(
                    {"error": f"Device with ID {device_id} not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Return success response with created data
            return Response({
                "success": True,
                "message": "All device test data created successfully",
                "data": {
                    "category": {
                        "id": str(category.id),
                        "name": category.name,
                        "code": category.code,
                        "created": created
                    },
                    "test_cases": [
                        {
                            "id": str(test_case_1.id),
                            "name": test_case_1.name,
                            "test_case_id": test_case_1.test_case_id,
                            "test_type": "Device Agent"
                        },
                        {
                            "id": str(test_case_2.id),
                            "name": test_case_2.name,
                            "test_case_id": test_case_2.test_case_id,
                            "test_type": "Device Agent"
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
                        "device_id": device_id,
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
            {"error": "Failed to create device test data", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Second API - Robot Test Data
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_robot_test_data(request):
    """
    Create robot test data in one request:
    1. TestCategory (Wifi)
    2. Two TestCases (Robot Framework type)
    3. TestSuite with TestSuiteCases
    4. TestSuiteExecution with TestSuiteExecutionDevice
    """
    try:
        # Get device_id from request data
        # device_id = request.data.get('device_id')
        device_id = '6c02259d-558e-48fc-a5ec-773a464d951a'  
        if not device_id:
            return Response(
                {"error": "device_id is required in request body"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        with transaction.atomic():
            # 1. Create or get TestCategory
            category, created = TestCategory.objects.get_or_create(
                name="Wifi",
                defaults={
                    'code': "WF",
                    'description': "Wireless networking and connectivity testing category for WiFi interfaces, bridging, and WAN connectivity validation"
                }
            )
            
            # 2. Create TestCase 1
            test_case_1 = TestCase.objects.create(
                name="Ethernet (LAN) Bridging",
                test_case_id="BB-TRF-BRG-001",
                category=category,
                description="Validates Ethernet LAN bridging functionality, including bridge configuration, traffic forwarding, and network connectivity across bridge interfaces",
                is_active=True,
                test_type=1  # Robot Framework
            )
            
            # 3. Create TestCase 2
            test_case_2 = TestCase.objects.create(
                name="Wifi Wan Interface",
                test_case_id="BB-INT-WWAN-001",
                category=category,
                description="Comprehensive testing of WiFi WAN interface functionality including connection establishment, authentication, data transmission, and failover scenarios",
                is_active=True,
                test_type=1  # Robot Framework
            )
            
            # 4. Create TestSuite
            test_suite = TestSuite.objects.create(
                name="Ether and Wifi For Robot",
                category=category,
                description="Comprehensive Robot Framework test suite covering Ethernet bridging and WiFi WAN interface validation for network connectivity and performance testing",
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
                device = Device.objects.get(id=device_id)
                TestSuiteExecutionDevice.objects.create(
                    test_suite_execution=execution,
                    device=device,
                    status='pending'
                )
            except Device.DoesNotExist:
                return Response(
                    {"error": f"Device with ID {device_id} not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Return success response with created data
            return Response({
                "success": True,
                "message": "All robot test data created successfully",
                "data": {
                    "category": {
                        "id": str(category.id),
                        "name": category.name,
                        "code": category.code,
                        "created": created
                    },
                    "test_cases": [
                        {
                            "id": str(test_case_1.id),
                            "name": test_case_1.name,
                            "test_case_id": test_case_1.test_case_id,
                            "test_type": "Robot Framework"
                        },
                        {
                            "id": str(test_case_2.id),
                            "name": test_case_2.name,
                            "test_case_id": test_case_2.test_case_id,
                            "test_type": "Robot Framework"
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
                        "device_id": device_id,
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
            {"error": "Failed to create robot test data", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# class TestCaseExecutionResultView(ProtectedAPIMixin, generics.GenericAPIView):
class TestCaseExecutionResultView(generics.GenericAPIView):

    """
    Update test case execution results
    """
    serializer_class = TestCaseExecutionResultSerializer
    queryset = TestCaseExecution.objects.none()
    
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # return Response({"status" : "new_status" })

        
        validated_data = serializer.validated_data
        execution = validated_data['execution_instance']
        
        try:

            # Get the new status
            new_status = validated_data['status']
            
            # Update based on status
            if new_status == TestExecutionStatus.RUNNING:
                # Mark as running
                execution.status = new_status
                # execution.started_at = timezone.now()
                execution.save(update_fields=['status', 'started_at'])
                
            elif new_status in [TestExecutionStatus.SUCCESS, TestExecutionStatus.FAILED]:
                # Mark as completed (success or failed)
                execution.status = new_status
                # execution.completed_at = timezone.now()
                execution.exit_code = validated_data.get('exit_code')
                execution.stdout = validated_data.get('stdout', '')
                execution.stderr = validated_data.get('stderr', '')
                
                # Calculate duration if started_at exists
                if execution.started_at:
                    execution.execution_duration = execution.completed_at - execution.started_at
                
                # Set error message for failed status
                if new_status == TestExecutionStatus.FAILED:
                    execution.error_message = validated_data.get('stderr', 'Test failed')
                
                execution.save(update_fields=[
                    'status', 'completed_at', 'exit_code', 'stdout', 
                    'stderr', 'execution_duration', 'error_message'
                ])
                
            elif new_status == TestExecutionStatus.TIMEOUT:
                # Mark as timeout
                execution.status = new_status
                # execution.completed_at = timezone.now()
                execution.error_message = "Test execution timed out"
                
                if execution.started_at:
                    execution.execution_duration = execution.completed_at - execution.started_at
                
                execution.save(update_fields=[
                    'status', 'completed_at', 'error_message', 'execution_duration'
                ])
                
            elif new_status == TestExecutionStatus.CANCELLED:
                # Mark as cancelled
                execution.status = new_status
                # execution.completed_at = timezone.now()
                execution.error_message = "Test execution was cancelled"
                
                if execution.started_at:
                    execution.execution_duration = execution.completed_at - execution.started_at
                
                execution.save(update_fields=[
                    'status', 'completed_at', 'error_message', 'execution_duration'
                ])
            
            # Check if all test cases are completed for this suite execution
            # self._check_suite_execution_completion(execution.test_suite_execution, execution.device)
            
            # Prepare response
            response_data = {
                "success": True,
                "message": f"Test case execution updated to {new_status}",
                "data": {
                    "execution_id": str(execution.id),
                    "test_case_id": str(execution.test_case_id),
                    "test_case_name": execution.test_case.name,
                    "device_id": str(execution.device_id),
                    "device_name": execution.device.name,
                    "status": execution.status,
                    "started_at": execution.started_at.isoformat() if execution.started_at else None,
                    "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    "exit_code": execution.exit_code,
                    "stdout": execution.stdout,
                    "stderr": execution.stderr,
                    "error_message": execution.error_message,
                    # "duration": execution.formatted_duration,

                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {
                    "error": "Failed to update test case execution",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _check_suite_execution_completion(self, test_suite_execution, device):
        """Check if all test cases for a device in suite execution are completed"""
        try:
            # Get all test case executions for this suite and device
            all_executions = TestCaseExecution.objects.filter(
                test_suite_execution=test_suite_execution,
                device=device
            )
            
            # Check if all are completed
            incomplete_count = all_executions.filter(
                status__in=[TestExecutionStatus.PENDING, TestExecutionStatus.RUNNING]
            ).count()
            
            if incomplete_count == 0:
                # All test cases completed for this device
                # Update the TestSuiteExecutionDevice status
                suite_device = TestSuiteExecutionDevice.objects.get(
                    test_suite_execution=test_suite_execution,
                    device=device
                )
                
                # Check if any test case failed
                failed_count = all_executions.filter(
                    status__in=[TestExecutionStatus.FAILED, TestExecutionStatus.TIMEOUT]
                ).count()
                
                if failed_count > 0:
                    suite_device.status = 'failed'
                else:
                    suite_device.status = 'completed'
                
                suite_device.completed_at = timezone.now()
                suite_device.save(update_fields=['status', 'completed_at'])
                
                # Check if all devices are completed for the suite execution
                self._check_overall_suite_completion(test_suite_execution)
                
        except Exception as e:
            logger.error(f"Error checking suite execution completion: {e}")
    
    def _check_overall_suite_completion(self, test_suite_execution):
        """Check if all devices have completed the suite execution"""
        try:
            incomplete_devices = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution=test_suite_execution,
                status__in=['pending', 'running']
            ).count()
            
            if incomplete_devices == 0:
                # All devices completed
                test_suite_execution.is_executed = True
                test_suite_execution.save(update_fields=['is_executed'])
                
        except Exception as e:
            logger.error(f"Error checking overall suite completion: {e}")


# Create view instances
test_category_list = TestCategoryListCreateView.as_view()
test_category_detail = TestCategoryDetailView.as_view()
test_case_list = TestCaseListCreateView.as_view()
test_case_detail = TestCaseDetailView.as_view()
test_suite_list = TestSuiteListCreateView.as_view()
test_suite_detail = TestSuiteDetailView.as_view()
test_suite_execution_list = TestSuiteExecutionListCreateView.as_view()
test_suite_execution_detail = TestSuiteExecutionDetailView.as_view()