from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authentication import SessionAuthentication


from rest_framework.decorators import api_view ,authentication_classes, permission_classes
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta

import logging
logger = logging.getLogger(__name__)

from django.db import transaction
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from django.http.response import HttpResponse, HttpResponseNotFound


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
    TestCaseExecutionResultSerializer,
    TestSuiteExecutionDeleteSerializer,
    TestSuiteExecutionDeleteAllSerializer,
    BulkTestDataCreationSerializer
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


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # To not perform the csrf check previously happening


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
                # test_case_2 = TestCase.objects.create(
                #     name="Test Case 2",
                #     test_case_id="TestCase_004",
                #     category=category,
                #     description="Secondary traffic validation test for advanced routing and switching using device agent",
                #     is_active=True,
                #     test_type=2  # Device Agent
                # )
                
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
                
                # TestSuiteCase.objects.create(
                #     test_suite=test_suite,
                #     test_case=test_case_2,
                #     order=2
                # )
                
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
                            # {
                            #     "id": str(test_case_2.id),
                            #     "name": test_case_2.name,
                            #     "test_case_id": test_case_2.test_case_id,
                            #     "test_type": "Device Agent"
                            # }
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
        



class AddFireWallGDeviceTestDataView(ProtectedAPIMixin, generics.CreateAPIView):
    """
    Create device test data in one request:
    1. TestCategory (FireWall)
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
                    name="FireWall",
                    defaults={
                        'code': "FireWall",
                        'description': "FireWall testing category for network performance and throughput validation"
                    }
                )
                
                # 2. Create TestCase 1
                test_case_1 = TestCase.objects.create(
                    name="FireWall Traffic",
                    test_case_id="BB-FF-001",
                    category=category,
                    description="Primary FireWall traffic validation ",
                    is_active=True,
                    test_type=1  # Robot specific
                )
       
                # 4. Create TestSuite
                test_suite = TestSuite.objects.create(
                    name="FireWall",
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
  
                        ],
                        "test_suite": {
                            "id": str(test_suite.id),
                            "name": test_suite.name,
                            "test_case_count": 1
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



class AddWifiGDeviceTestDataView(ProtectedAPIMixin, generics.CreateAPIView):
    """
    Create device test data in one request:
    1. TestCategory (Wifi)
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
                    name="Wifi",
                    defaults={
                        'code': "Wifi",
                        'description': "Wifi testing category for network performance and throughput validation"
                    }
                )
                
                # 2. Create TestCase 1
                test_case_1 = TestCase.objects.create(
                    name="Wifi Traffic",
                    test_case_id="BB-INT-WWAN-001",
                    category=category,
                    description="Primary wifi traffic validation ",
                    is_active=True,
                    test_type=1,  # Robot specific,
                    params =  {
                        "PC1": { "ip": "10.10.10.1", "username": "osboxes", "password": "spanidea" },
                        "PC2": { "ip": "10.10.10.2", "username": "osboxes", "password": "spanidea" },
                        "PC3": { "ip": "10.10.10.3", "username": "osboxes", "password": "spanidea" }
                        }
                )
       
                # 4. Create TestSuite
                test_suite = TestSuite.objects.create(
                    name="Wifi",
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
  
                        ],
                        "test_suite": {
                            "id": str(test_suite.id),
                            "name": test_suite.name,
                            "test_case_count": 1
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



class AddFiveGDeviceTestDataView(ProtectedAPIMixin, generics.CreateAPIView):
    """
    Create device test data in one request:
    1. TestCategory (5G)
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
                    name="5G",
                    defaults={
                        'code': "5G",
                        'description': "5G testing category for network performance and throughput validation"
                    }
                )
                
                # 2. Create TestCase 1
                test_case_1 = TestCase.objects.create(
                    name="Black Box 5G",
                    test_case_id="BB_INT_5G_001",
                    category=category,
                    description="Primary 5g sim validation ",
                    is_active=True,
                    test_type=2  # Device Agent
                )
       
                # 4. Create TestSuite
                test_suite = TestSuite.objects.create(
                    name="5G",
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
  
                        ],
                        "test_suite": {
                            "id": str(test_suite.id),
                            "name": test_suite.name,
                            "test_case_count": 1
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

class AddLoggingDeviceTestDataView(ProtectedAPIMixin, generics.CreateAPIView):
    """
    Create device test data in one request:
    1. TestCategory (Logging)
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
                    name="Logging",
                    defaults={
                        'code': "LOG",
                        'description': "Logging testing category for network performance and throughput validation"
                    }
                )
                
                # 2. Create TestCase 1
                test_case_1 = TestCase.objects.create(
                    name="Test Case 1",
                    test_case_id="TestCase_001",
                    category=category,
                    description="Primary logging validation test for basic connectivity and data flow using device agent",
                    is_active=True,
                    test_type=2  # Device Agent
                )
       
                # 4. Create TestSuite
                test_suite = TestSuite.objects.create(
                    name="Logging",
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
  
                        ],
                        "test_suite": {
                            "id": str(test_suite.id),
                            "name": test_suite.name,
                            "test_case_count": 1
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
            print(">>>>>>>>>>>>>>>>>>>>>>>>>Result call✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅")
            
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





class RobotTestResultView(APIView):
    """
    API endpoint to receive test results from Robot Framework server
    No serializer - direct processing of payload
    """
    authentication_classes = []  # Disable auth for now, enable as needed
    permission_classes = []  # Disable permissions for now
    
    def post(self, request, *args, **kwargs):
        """
        Accept test results from Robot Framework server
        Expected payload:
        {
            "execution_id": "uuid",
            "status": "running|success|failed|timeout|cancelled",
            "exit_code": 0,
            "stdout": "output",
            "stderr": "error",
            "started_at": "ISO datetime",
            "completed_at": "ISO datetime"
        }
        """
        try:
            data = request.data
            logger.info(f"Received Robot Framework test result: {data}")
            print(f"✅ Robot Framework Result API called with data: {data}")
            # return Response({"status" : "done"}, status=status.HTTP_200_OK)
            
            # Extract execution_id
            execution_id = data.get('execution_id')
            if not execution_id:
                return Response({
                    "error": "execution_id is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Find the TestCaseExecution record
            try:
                execution = TestCaseExecution.objects.get(id=execution_id)
                print(f"✅ Found TestCaseExecution: {execution}")
            except TestCaseExecution.DoesNotExist:
                return Response({
                    "error": f"TestCaseExecution with id {execution_id} not found"
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Extract status
            new_status = data.get('status')
            if not new_status:
                return Response({
                    "error": "status is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Map status to TestExecutionStatus
            status_mapping = {
                'running': TestExecutionStatus.RUNNING,
                'success': TestExecutionStatus.SUCCESS,
                'failed': TestExecutionStatus.FAILED,
                'timeout': TestExecutionStatus.TIMEOUT,
                'cancelled': TestExecutionStatus.CANCELLED
            }
            
            if new_status not in status_mapping:
                return Response({
                    "error": f"Invalid status: {new_status}. Must be one of {list(status_mapping.keys())}"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            execution_status = status_mapping[new_status]
            
            # Update execution based on status
            if execution_status == TestExecutionStatus.RUNNING:
                execution.status = execution_status
                if data.get('started_at'):
                    # execution.started_at = datetime.fromisoformat(data['started_at'].replace('Z', '+00:00'))
                    print("")
                else:
                    execution.started_at = timezone.now()
                execution.save(update_fields=['status', 'started_at'])
                print(f"✅ Updated to RUNNING status")
                
            elif execution_status in [TestExecutionStatus.SUCCESS, TestExecutionStatus.FAILED]:
                execution.status = execution_status
                
                # Set completion time
                if data.get('completed_at'):
                    # execution.completed_at = datetime.fromisoformat(data['completed_at'].replace('Z', '+00:00'))
                    print("")
                else:
                    execution.completed_at = timezone.now()
                
                # Set other fields
                execution.exit_code = data.get('exit_code')
                execution.stdout = data.get('stdout', '')
                execution.stderr = data.get('stderr', '')
                
                # Calculate duration
                # if execution.started_at:
                #     execution.execution_duration = execution.completed_at - execution.started_at
                
                # Set error message for failed status
                if execution_status == TestExecutionStatus.FAILED:
                    execution.error_message = data.get('stderr', 'Test failed')
                
                execution.save(update_fields=[
                    'status', 'completed_at', 'exit_code', 'stdout', 
                    'stderr', 'execution_duration', 'error_message'
                ])
                print(f"✅ Updated to {execution_status} status")
                
            elif execution_status == TestExecutionStatus.TIMEOUT:
                execution.status = execution_status
                if data.get('completed_at'):
                    # execution.completed_at = datetime.fromisoformat(data['completed_at'].replace('Z', '+00:00'))
                    print("")
                else:
                    execution.completed_at = timezone.now()
                execution.error_message = data.get('error_message', 'Test execution timed out')
                
                if execution.started_at:
                    execution.execution_duration = execution.completed_at - execution.started_at
                
                execution.save(update_fields=[
                    'status', 'completed_at', 'error_message', 'execution_duration'
                ])
                print(f"✅ Updated to TIMEOUT status")
                
            elif execution_status == TestExecutionStatus.CANCELLED:
                execution.status = execution_status
                if data.get('completed_at'):
                    # execution.completed_at = datetime.fromisoformat(data['completed_at'].replace('Z', '+00:00'))
                    print("")
                else:
                    execution.completed_at = timezone.now()
                execution.error_message = data.get('error_message', 'Test execution was cancelled')
                
                if execution.started_at:
                    execution.execution_duration = execution.completed_at - execution.started_at
                
                execution.save(update_fields=[
                    'status', 'completed_at', 'error_message', 'execution_duration'
                ])
                print(f"✅ Updated to CANCELLED status")
            
            # Check if all test cases are completed for this suite execution
            self._check_suite_execution_completion(execution.test_suite_execution, execution.device)
            
            # Prepare response
            response_data = {
                "success": True,
                "message": f"Test case execution updated to {new_status}",
                "data": {
                    "execution_id": str(execution.id),
                    "test_case_id": str(execution.test_case.test_case_id),
                    "test_case_name": execution.test_case.name,
                    "device_id": str(execution.device.id),
                    "device_name": execution.device.name,
                    "status": execution.status,
                    "started_at": execution.started_at.isoformat() if execution.started_at else None,
                    "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    "exit_code": execution.exit_code,
                    "duration": str(execution.execution_duration) if execution.execution_duration else None
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating robot test result: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return Response({
                "error": "Failed to update test case execution",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
                
                print(f"✅ Updated TestSuiteExecutionDevice status to: {suite_device.status}")
                
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
                # All devices completed - don't set is_executed here as it's controlled by admin action
                print(f"✅ All devices completed for test suite execution: {test_suite_execution}")
                
        except Exception as e:
            logger.error(f"Error checking overall suite completion: {e}")


class DeviceTestResultView(APIView):
    """
    API endpoint to receive test results from Robot Framework server
    No serializer - direct processing of payload
    """
    authentication_classes = []  # Disable auth for now, enable as needed
    permission_classes = []  # Disable permissions for now
    
    def post(self, request, *args, **kwargs):
        """
        Accept test results from Robot Framework server
        Expected payload:
        {
            "execution_id": "uuid",
            "status": "running|success|failed|timeout|cancelled",
            "exit_code": 0,
            "stdout": "output",
            "stderr": "error",
            "started_at": "ISO datetime",
            "completed_at": "ISO datetime"
        }
        """
        try:
            data = request.data
            logger.info(f"Received Robot Framework test result✅✅✅✅✅✅✅✅✅✅✅✅✅: {data}")
  
            
            # Extract execution_id
            execution_id = data.get('execution_id')
            if not execution_id:
                return Response({
                    "error": "execution_id is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Find the TestCaseExecution record
            try:
                execution = TestCaseExecution.objects.get(id=execution_id)
                print(f"✅ Found TestCaseExecution: {execution}")
                print(f"📊 Current DB status: {execution.status}")
            except TestCaseExecution.DoesNotExist:
                print(f"❌ TestCaseExecution with id {execution_id} not found")
                return Response({
                    "error": f"TestCaseExecution with id {execution_id} not found"
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Extract status
            new_status = data.get('status')
            exit_code = data.get('exit_code')
            
            # Status icons mapping
            status_icons = {
                'running': '🏃‍♂️',
                'success': '✅',
                'failed': '❌',
                'timeout': '⏰',
                'cancelled': '🚫'
            }
            
            # Print status with icon
            icon = status_icons.get(new_status, '❓')
            print(f"{icon} Received status: {new_status}")
            
            # Print exit code with icon
            if exit_code is not None:
                exit_icon = '✓' if exit_code == 0 else '✗'
                print(f"{exit_icon} Exit code: {exit_code}")

            if not new_status:
                return Response({
                    "error": "status is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Map status to TestExecutionStatus
            status_mapping = {
                'running': TestExecutionStatus.RUNNING,
                'success': TestExecutionStatus.SUCCESS,
                'failed': TestExecutionStatus.FAILED,
                'timeout': TestExecutionStatus.TIMEOUT,
                'cancelled': TestExecutionStatus.CANCELLED
            }
            
            if new_status not in status_mapping:
                print(f"⚠️ Invalid status received: {new_status}")
                return Response({
                    "error": f"Invalid status: {new_status}. Must be one of {list(status_mapping.keys())}"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            execution_status = status_mapping[new_status]
            print(f"🔄 Mapped '{new_status}' to TestExecutionStatus: {execution_status}")
            
            # ===== STATUS UPDATE LOGIC COMMENTED OUT =====
            # Update execution based on status
            if execution_status == TestExecutionStatus.RUNNING:
                execution.status = execution_status
                if data.get('started_at'):
                    print("⏱️ Using provided started_at timestamp")
                else:
                    execution.started_at = timezone.now()
                    print("⏱️ Setting started_at to current time")
                execution.save(update_fields=['status', 'started_at'])
                print(f"🏃‍♂️ Updated to RUNNING status")
                
            elif execution_status in [TestExecutionStatus.SUCCESS, TestExecutionStatus.FAILED]:
                # Debug print before update
                print(f"🔍 Before update - execution.status: {execution.status}")
                print(f"🔍 Setting execution.status to: {execution_status}")
                
                execution.status = execution_status
                
                # Set completion time
                if data.get('completed_at'):
                    print("⏱️ Using provided completed_at timestamp")
                else:
                    execution.completed_at = timezone.now()
                    print("⏱️ Setting completed_at to current time")
                
                # Set other fields
                execution.exit_code = data.get('exit_code')
                execution.stdout = data.get('stdout', '')
                execution.stderr = data.get('stderr', '')
                
                # Debug: Print what we're about to save
                print(f"📝 About to save:")
                print(f"   - status: {execution.status}")
                print(f"   - exit_code: {execution.exit_code}")
                print(f"   - stdout length: {len(execution.stdout)} chars")
                print(f"   - stderr length: {len(execution.stderr)} chars")
                
                # Set error message for failed status
                if execution_status == TestExecutionStatus.FAILED:
                    # Use stderr if available, otherwise extract error from stdout
                    if data.get('stderr'):
                        execution.error_message = data.get('stderr')
                    else:
                        # Extract error from stdout if present
                        stdout = data.get('stdout', '')
                        if '[ERROR]' in stdout:
                            error_lines = [line for line in stdout.split('\n') if '[ERROR]' in line]
                            execution.error_message = '\n'.join(error_lines) if error_lines else 'Test failed'
                        else:
                            execution.error_message = 'Test failed'
                    print(f"❌ Test FAILED with error: {execution.error_message[:100]}...")
                else:
                    print(f"✅ Test SUCCEEDED")
                
                # Save with explicit field list
                fields_to_update = [
                    'status', 'completed_at', 'exit_code', 'stdout', 
                    'stderr', 'error_message'
                ]
                
                # Only update duration if we have both timestamps
                if execution.started_at and execution.completed_at:
                    execution.execution_duration = execution.completed_at - execution.started_at
                    fields_to_update.append('execution_duration')
                
                execution.save(update_fields=fields_to_update)
                
                # Verify the save worked
                execution.refresh_from_db()
                print(f"🔍 After save - execution.status from DB: {execution.status}")
                
                status_icon = '✅' if execution_status == TestExecutionStatus.SUCCESS else '❌'
                print(f"{status_icon} Updated to {execution_status} status (verified from DB: {execution.status})")
                
            elif execution_status == TestExecutionStatus.TIMEOUT:
                execution.status = execution_status
                if data.get('completed_at'):
                    print("⏱️ Using provided completed_at timestamp")
                else:
                    execution.completed_at = timezone.now()
                    print("⏱️ Setting completed_at to current time")
                execution.error_message = data.get('error_message', 'Test execution timed out')
                
                if execution.started_at:
                    execution.execution_duration = execution.completed_at - execution.started_at
                    print(f"⏱️ Execution duration: {execution.execution_duration}")
                
                execution.save(update_fields=[
                    'status', 'completed_at', 'error_message', 'execution_duration'
                ])
                print(f"⏰ Updated to TIMEOUT status")
                
            elif execution_status == TestExecutionStatus.CANCELLED:
                execution.status = execution_status
                if data.get('completed_at'):
                    print("⏱️ Using provided completed_at timestamp")
                else:
                    execution.completed_at = timezone.now()
                    print("⏱️ Setting completed_at to current time")
                execution.error_message = data.get('error_message', 'Test execution was cancelled')
                
                if execution.started_at:
                    execution.execution_duration = execution.completed_at - execution.started_at
                    print(f"⏱️ Execution duration: {execution.execution_duration}")
                
                execution.save(update_fields=[
                    'status', 'completed_at', 'error_message', 'execution_duration'
                ])
                print(f"🚫 Updated to CANCELLED status")
            # ===== END OF COMMENTED STATUS UPDATE LOGIC =====
            
            print(f"⚠️ STATUS UPDATE LOGIC IS COMMENTED OUT - NO DATABASE CHANGES MADE")
            
            # Check if all test cases are completed for this suite execution
            # ALSO COMMENTING THIS OUT SINCE IT DEPENDS ON STATUS
            # self._check_suite_execution_completion(execution.test_suite_execution, execution.device)
            
            # Prepare response
            response_data = {
                "success": True,
                "message": f"Test case execution would be updated to {new_status} (but update is commented out)",
                "data": {
                    "execution_id": str(execution.id),
                    "test_case_id": str(execution.test_case.test_case_id),
                    "test_case_name": execution.test_case.name,
                    "device_id": str(execution.device.id),
                    "device_name": execution.device.name,
                    "status": execution.status,  # This will show the current DB value
                    "requested_status": new_status,  # Show what was requested
                    "started_at": execution.started_at.isoformat() if execution.started_at else None,
                    "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    "exit_code": execution.exit_code,
                    "duration": str(execution.execution_duration) if execution.execution_duration else None
                }
            }
            
            print(f"✉️ Sending response: Status update SKIPPED (current DB status: {execution.status})")
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating robot test result: {str(e)}")
            import traceback
            traceback.print_exc()
            print(f"💥 Error occurred: {str(e)}")
            
            return Response({
                "error": "Failed to update test case execution",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
                    print(f"❌ TestSuiteExecutionDevice marked as FAILED (failed tests: {failed_count})")
                else:
                    suite_device.status = 'completed'
                    print(f"✅ TestSuiteExecutionDevice marked as COMPLETED (all tests passed)")
                
                suite_device.completed_at = timezone.now()
                suite_device.save(update_fields=['status', 'completed_at'])
                
                print(f"📊 Updated TestSuiteExecutionDevice status to: {suite_device.status}")
                
                # Check if all devices are completed for the suite execution
                self._check_overall_suite_completion(test_suite_execution)
                
        except Exception as e:
            logger.error(f"Error checking suite execution completion: {e}")
            print(f"⚠️ Error in _check_suite_execution_completion: {e}")
    
    def _check_overall_suite_completion(self, test_suite_execution):
        """Check if all devices have completed the suite execution"""
        try:
            incomplete_devices = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution=test_suite_execution,
                status__in=['pending', 'running']
            ).count()
            
            if incomplete_devices == 0:
                # All devices completed - don't set is_executed here as it's controlled by admin action
                print(f"🎉 All devices completed for test suite execution: {test_suite_execution}")
            else:
                print(f"⏳ Still waiting for {incomplete_devices} device(s) to complete")
                
        except Exception as e:
            logger.error(f"Error checking overall suite completion: {e}")
            print(f"⚠️ Error in _check_overall_suite_completion: {e}")
# views.py
class TestSuiteExecutionDeleteView(ProtectedAPIMixin, generics.DestroyAPIView):
    """
    Delete a test suite execution and all related data.
    
    This will delete:
    - TestSuiteExecution record
    - All related TestSuiteExecutionDevice records (CASCADE)
    - All related TestCaseExecution records (CASCADE)
    
    The TestSuite itself will NOT be deleted (PROTECT).
    """
    queryset = TestSuiteExecution.objects.all()
    serializer_class = TestSuiteExecutionDeleteSerializer
    lookup_field = 'pk'
    
    def destroy(self, request, *args, **kwargs):
        """Custom destroy with confirmation and detailed response"""
        instance = self.get_object()
        
        # Validate confirmation
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Gather information before deletion
        deletion_summary = {
            'test_suite_execution': {
                'id': str(instance.id),
                'test_suite_name': instance.test_suite.name,
                'created_at': instance.created.isoformat(),
                'is_executed': instance.is_executed
            },
            'related_data': {
                'execution_devices_count': instance.devices.count(),
                'test_case_executions_count': TestCaseExecution.objects.filter(
                    test_suite_execution=instance
                ).count()
            }
        }
        
        # Get device names for reference
        device_names = list(
            instance.devices.values_list('device__name', flat=True)
        )
        deletion_summary['devices'] = device_names
        
        try:
            # Perform deletion (CASCADE will handle related objects)
            instance.delete()
            
            return Response({
                'success': True,
                'message': _('Test suite execution and all related data deleted successfully'),
                'deleted_data': deletion_summary
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': _('Failed to delete test suite execution'),
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, *args, **kwargs):
        """Override delete method to use destroy"""
        return self.destroy(request, *args, **kwargs)

# views.py
class TestSuiteExecutionDeleteAllView(ProtectedAPIMixin, generics.GenericAPIView):
    """
    Delete a test suite execution and ALL related data including:
    - TestCaseExecution records
    - TestSuiteExecutionDevice records
    - TestSuite
    - TestSuiteCase records
    - TestCase records (if not used elsewhere)
    - TestCategory (if not used elsewhere)
    """
    queryset = TestSuiteExecution.objects.all()  # Add this line
    serializer_class = TestSuiteExecutionDeleteAllSerializer  # Add this line
    lookup_field = 'pk'
    
    def delete(self, request, pk):
        """Delete all related test data"""
        execution = self.get_object()  # This will now work with GenericAPIView
        
        # Validate request
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        force_delete = serializer.validated_data.get('force_delete', False)
        
        try:
            with transaction.atomic():
                # Collect all related data before deletion
                test_suite = execution.test_suite
                category = test_suite.category
                
                # Get all test cases from this suite
                test_cases = list(test_suite.test_cases.all())
                test_case_ids = [tc.id for tc in test_cases]
                
                # Prepare deletion summary
                deletion_summary = {
                    'test_suite_execution': {
                        'id': str(execution.id),
                        'created_at': execution.created.isoformat()
                    },
                    'test_suite': {
                        'id': str(test_suite.id),
                        'name': test_suite.name
                    },
                    'category': {
                        'id': str(category.id),
                        'name': category.name
                    },
                    'deleted_counts': {}
                }
                
                # 1. Delete TestCaseExecution records
                case_exec_count = TestCaseExecution.objects.filter(
                    test_suite_execution=execution
                ).delete()[0]
                deletion_summary['deleted_counts']['test_case_executions'] = case_exec_count
                
                # 2. Delete TestSuiteExecutionDevice records
                device_count = TestSuiteExecutionDevice.objects.filter(
                    test_suite_execution=execution
                ).delete()[0]
                deletion_summary['deleted_counts']['execution_devices'] = device_count
                
                # 3. Delete the TestSuiteExecution
                execution.delete()
                deletion_summary['deleted_counts']['test_suite_execution'] = 1
                
                # 4. Check if test suite is used in other executions
                other_executions = TestSuiteExecution.objects.filter(
                    test_suite=test_suite
                ).exists()
                
                if not other_executions or force_delete:
                    # 5. Delete TestSuiteCase relationships
                    suite_case_count = TestSuiteCase.objects.filter(
                        test_suite=test_suite
                    ).delete()[0]
                    deletion_summary['deleted_counts']['test_suite_cases'] = suite_case_count
                    
                    # 6. Delete the TestSuite
                    test_suite.delete()
                    deletion_summary['deleted_counts']['test_suite'] = 1
                    
                    # 7. Delete TestCases if not used elsewhere
                    deleted_test_cases = []
                    for test_case in test_cases:
                        # Check if test case is used in other suites
                        other_suites = TestSuiteCase.objects.filter(
                            test_case=test_case
                        ).exists()
                        
                        # Check if test case has other executions
                        other_case_executions = TestCaseExecution.objects.filter(
                            test_case=test_case
                        ).exists()
                        
                        if (not other_suites and not other_case_executions) or force_delete:
                            deleted_test_cases.append({
                                'id': str(test_case.id),
                                'name': test_case.name,
                                'test_case_id': test_case.test_case_id
                            })
                            test_case.delete()
                    
                    deletion_summary['deleted_counts']['test_cases'] = len(deleted_test_cases)
                    deletion_summary['deleted_test_cases'] = deleted_test_cases
                    
                    # 8. Delete Category if not used elsewhere
                    other_test_cases = TestCase.objects.filter(
                        category=category
                    ).exists()
                    other_test_suites = TestSuite.objects.filter(
                        category=category
                    ).exists()
                    
                    if (not other_test_cases and not other_test_suites) or force_delete:
                        category.delete()
                        deletion_summary['deleted_counts']['category'] = 1
                        deletion_summary['category_deleted'] = True
                    else:
                        deletion_summary['category_deleted'] = False
                        deletion_summary['category_still_in_use'] = True
                else:
                    deletion_summary['test_suite_deleted'] = False
                    deletion_summary['test_suite_still_in_use'] = True
                
                return Response({
                    'success': True,
                    'message': _('Test data deleted successfully'),
                    'deletion_summary': deletion_summary
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response({
                'error': _('Failed to delete test data'),
                'details': str(e),
                'type': type(e).__name__
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        








# views.py
class BulkTestDataCreationView(ProtectedAPIMixin, generics.CreateAPIView):
    """
    Create complete test data in one request:
    1. TestCategory (create or use existing)
    2. Multiple TestCases (create or use existing)
    3. TestSuite with test cases
    4. TestSuiteExecution with multiple devices
    """
    serializer_class = BulkTestDataCreationSerializer
    queryset = TestSuiteExecution.objects.none()  # Dummy queryset for permissions
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        category_data = serializer.validated_data['category']
        test_cases_data = serializer.validated_data['test_cases']
        test_suite_data = serializer.validated_data['test_suite']
        device_ids = serializer.validated_data['device_ids']
        use_existing = serializer.validated_data['use_existing']
        
        try:
            with transaction.atomic():
                # 1. Create or get TestCategory
                if use_existing:
                    category, category_created = TestCategory.objects.get_or_create(
                        name=category_data['name'],
                        defaults={
                            'code': category_data.get('code', ''),
                            'description': category_data.get('description', '')
                        }
                    )
                else:
                    # Force create new category
                    category = TestCategory.objects.create(
                        name=category_data['name'],
                        code=category_data.get('code', ''),
                        description=category_data.get('description', '')
                    )
                    category_created = True
                
                # 2. Create TestCases
                created_test_cases = []
                test_case_objects = []
                
                for tc_data in test_cases_data:
                    if use_existing:
                        # Try to get existing test case by test_case_id
                        test_case = TestCase.objects.filter(
                            test_case_id=tc_data['test_case_id']
                        ).first()
                        
                        if test_case:
                            # Update category if different
                            if test_case.category != category:
                                test_case.category = category
                                test_case.save()
                            test_case_created = False
                        else:
                            # Create new test case
                            test_case = TestCase.objects.create(
                                name=tc_data['name'],
                                test_case_id=tc_data['test_case_id'],
                                category=category,
                                test_type=tc_data['test_type'],
                                description=tc_data.get('description', ''),
                                is_active=tc_data.get('is_active', True)
                            )
                            test_case_created = True
                    else:
                        # Force create new test case
                        test_case = TestCase.objects.create(
                            name=tc_data['name'],
                            test_case_id=tc_data['test_case_id'],
                            category=category,
                            test_type=tc_data['test_type'],
                            description=tc_data.get('description', ''),
                            is_active=tc_data.get('is_active', True)
                        )
                        test_case_created = True
                    
                    test_case_objects.append(test_case)
                    created_test_cases.append({
                        'id': str(test_case.id),
                        'name': test_case.name,
                        'test_case_id': test_case.test_case_id,
                        'test_type': test_case.get_test_type_display(),
                        'created': test_case_created
                    })
                
                # 3. Create TestSuite
                if use_existing:
                    # Check if suite exists with same name and category
                    test_suite = TestSuite.objects.filter(
                        name=test_suite_data['name'],
                        category=category
                    ).first()
                    
                    if test_suite:
                        test_suite_created = False
                        # Clear existing test cases
                        TestSuiteCase.objects.filter(test_suite=test_suite).delete()
                    else:
                        test_suite = TestSuite.objects.create(
                            name=test_suite_data['name'],
                            category=category,
                            description=test_suite_data.get('description', ''),
                            is_active=test_suite_data.get('is_active', True)
                        )
                        test_suite_created = True
                else:
                    test_suite = TestSuite.objects.create(
                        name=test_suite_data['name'],
                        category=category,
                        description=test_suite_data.get('description', ''),
                        is_active=test_suite_data.get('is_active', True)
                    )
                    test_suite_created = True
                
                # 4. Create TestSuiteCase entries
                for order, test_case in enumerate(test_case_objects, start=1):
                    TestSuiteCase.objects.create(
                        test_suite=test_suite,
                        test_case=test_case,
                        order=order
                    )
                
                # 5. Create TestSuiteExecution
                execution = TestSuiteExecution.objects.create(
                    test_suite=test_suite,
                    is_executed=False
                )
                
                # 6. Create TestSuiteExecutionDevice entries
                devices = Device.objects.filter(id__in=device_ids)
                execution_devices = []
                
                for device in devices:
                    exec_device = TestSuiteExecutionDevice.objects.create(
                        test_suite_execution=execution,
                        device=device,
                        status='pending'
                    )
                    execution_devices.append({
                        'device_id': str(device.id),
                        'device_name': device.name,
                        'status': 'pending'
                    })
                
                # 7. Create TestCaseExecution entries for each device and test case
                for device in devices:
                    for order, test_case in enumerate(test_case_objects, start=1):
                        TestCaseExecution.objects.create(
                            test_suite_execution=execution,
                            device=device,
                            test_case=test_case,
                            status=TestExecutionStatus.PENDING,
                            execution_order=order
                        )
                
                # Return comprehensive response
                return Response({
                    'success': True,
                    'message': 'Test data created successfully',
                    'data': {
                        'category': {
                            'id': str(category.id),
                            'name': category.name,
                            'code': category.code,
                            'created': category_created
                        },
                        'test_cases': created_test_cases,
                        'test_cases_count': len(created_test_cases),
                        'test_suite': {
                            'id': str(test_suite.id),
                            'name': test_suite.name,
                            'description': test_suite.description,
                            'test_case_count': len(test_case_objects),
                            'created': test_suite_created
                        },
                        'execution': {
                            'id': str(execution.id),
                            'test_suite_name': test_suite.name,
                            'device_count': len(devices),
                            'devices': execution_devices,
                            'total_test_executions': len(devices) * len(test_case_objects)
                        }
                    }
                }, status=status.HTTP_201_CREATED)
                
        except ValidationError as e:
            return Response(
                {'error': 'Validation error', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to create test data', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




# Add this function to your views.py
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_category_test_cases(request, category_id):
    """
    API endpoint to get test cases for a specific category
    Used by the admin interface for dynamic test case selection
    """
    try:
        # Verify category exists
        if not TestCategory.objects.filter(id=category_id).exists():
            return Response(
                {"error": "Category not found", "category_id": str(category_id)},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get active test cases for the category
        test_cases = TestCase.objects.filter(
            category_id=category_id,
            is_active=True
        ).order_by('name')
        
        # Serialize test cases
        test_cases_data = []
        for tc in test_cases:
            test_cases_data.append({
                'id': str(tc.id),
                'name': tc.name,
                'test_case_id': tc.test_case_id,
                'test_type': tc.test_type,
                'test_type_display': tc.get_test_type_display()
            })
        
        return Response({
            'success': True,
            'category_id': str(category_id),
            'test_cases': test_cases_data,
            'count': len(test_cases_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting test cases for category {category_id}: {str(e)}")
        return Response(
            {"error": "Failed to retrieve test cases", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )










@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_test_suite_details(request, suite_id):
    """
    API endpoint to get test suite details with test cases
    Used by TestSuiteExecution admin interface
    """
    if not suite_id:
        return Response({
            'success': False,
            'error': 'suite_id is required in URL'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get test suite
        test_suite = get_object_or_404(TestSuite, id=suite_id)

        # Get test cases with their order
        test_suite_cases = TestSuiteCase.objects.filter(
            test_suite=test_suite
        ).select_related('test_case', 'test_case__category').order_by('order')

        # Serialize test cases data
        test_cases_data = []
        for suite_case in test_suite_cases:
            tc = suite_case.test_case
            test_cases_data.append({
                'id': str(tc.id),
                'name': tc.name,
                'test_case_id': tc.test_case_id,
                'category': tc.category.name,
                'test_type': tc.test_type,
                'test_type_display': tc.get_test_type_display(),
                'order': suite_case.order,
                'is_active': tc.is_active
            })

        # Serialize test suite data
        test_suite_data = {
            'id': str(test_suite.id),
            'name': test_suite.name,
            'category': test_suite.category.name,
            'category_id': str(test_suite.category.id),
            'description': test_suite.description or '',
            'is_active': test_suite.is_active,
            'test_case_count': len(test_cases_data),
            'created': test_suite.created.isoformat() if test_suite.created else None,
            'modified': test_suite.modified.isoformat() if test_suite.modified else None
        }

        return Response({
            'success': True,
            'test_suite': test_suite_data,
            'test_cases': test_cases_data,
            'count': len(test_cases_data)
        }, status=status.HTTP_200_OK)

    except TestSuite.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Test suite not found',
            'suite_id': str(suite_id)
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Error getting test suite details for {suite_id}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve test suite details',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_devices(request):
    """
    API endpoint to get available devices for test execution
    Used by TestSuiteExecution admin interface
    """
    # ============= CONFIGURATION SECTION =============
    # Set this to True to show only devices with connections
    # Set this to False to show all devices regardless of connection status
    FILTER_BY_CONNECTION = False  # ← Change this to False when you want to show all devices
    # =================================================
    
    try:
        # Get organization filter if user has limited access
        organization_filter = {}
        
        # Check different possible ways organizations might be associated with user
        user_organizations = None
        
        # Try different organization access patterns in OpenWISP
        if hasattr(request.user, 'organizations_managed'):
            orgs_managed = request.user.organizations_managed
            if hasattr(orgs_managed, 'all'):
                user_organizations = orgs_managed.all()
            elif isinstance(orgs_managed, (list, tuple)):
                user_organizations = orgs_managed
        elif hasattr(request.user, 'organizations'):
            orgs = request.user.organizations
            if hasattr(orgs, 'all'):
                user_organizations = orgs.all()
            elif isinstance(orgs, (list, tuple)):
                user_organizations = orgs
        elif hasattr(request.user, 'organizationuser_set'):
            user_organizations = [ou.organization for ou in request.user.organizationuser_set.all()]
        
        # Apply organization filter if user has organization restrictions
        if user_organizations:
            if isinstance(user_organizations, (list, tuple)):
                if len(user_organizations) > 0:
                    organization_filter['organization__in'] = user_organizations
            else:
                if user_organizations.exists():
                    organization_filter['organization__in'] = user_organizations
        
        # Get devices with organization filter
        devices_query = Device.objects.filter(
            **organization_filter
        ).select_related('organization')
        
        # Apply connection filter if enabled
        if FILTER_BY_CONNECTION:
            devices_query = devices_query.filter(
                deviceconnection__isnull=False, 
                deviceconnection__enabled=True
            ).distinct()
        
        devices = devices_query.order_by('name')
        
        devices_data = []
        for device in devices:
            try:
                # Get device connection status
                has_connection = False
                connection_status = 'No Connection'
                
                try:
                    if hasattr(device, 'deviceconnection'):
                        device_conn = device.deviceconnection
                        if device_conn and hasattr(device_conn, 'enabled'):
                            has_connection = device_conn.enabled
                            connection_status = 'Connected' if has_connection else 'Disabled'
                except Exception as conn_error:
                    logger.debug(f"Connection check failed for device {device.id}: {str(conn_error)}")
                
                # Skip devices without connection if filtering is enabled
                if FILTER_BY_CONNECTION and not has_connection:
                    continue
                
                # Determine device status based on available fields
                device_status = 'Offline'
                is_deactivated = getattr(device, '_is_deactivated', False)
                
                if is_deactivated:
                    device_status = 'Deactivated'
                elif getattr(device, 'last_ip', None) and getattr(device, 'management_ip', None):
                    device_status = 'Online'
                elif getattr(device, 'last_ip', None):
                    device_status = 'Reachable'
                
                device_data = {
                    'id': str(device.id),
                    'name': device.name,
                    'organization': device.organization.name if device.organization else 'No Organization',
                    'organization_id': str(device.organization.id) if device.organization else None,
                    'last_ip': getattr(device, 'last_ip', None) or 'N/A',
                    'management_ip': getattr(device, 'management_ip', None) or 'N/A',
                    'mac_address': getattr(device, 'mac_address', None) or 'N/A',
                    'status': device_status,
                    'connection_status': connection_status,
                    'has_connection': has_connection,
                    'is_active': not is_deactivated,  # Use _is_deactivated field inverted
                    'model': getattr(device, 'model', None) or 'Unknown',
                    'os': getattr(device, 'os', None) or 'Unknown',
                    'hardware_id': getattr(device, 'hardware_id', None) or 'N/A',
                    'created': device.created.isoformat() if hasattr(device, 'created') and device.created else None,
                }
                
                devices_data.append(device_data)
                
            except Exception as device_error:
                logger.warning(f"Error processing device {device.id}: {str(device_error)}")
                # Add device with basic info even if there's an error (only if not filtering by connection)
                if not FILTER_BY_CONNECTION:
                    devices_data.append({
                        'id': str(device.id),
                        'name': getattr(device, 'name', 'Unknown Device'),
                        'organization': device.organization.name if device.organization else 'No Organization',
                        'organization_id': str(device.organization.id) if device.organization else None,
                        'last_ip': getattr(device, 'last_ip', None) or 'N/A',
                        'management_ip': 'N/A',
                        'mac_address': 'N/A',
                        'status': 'Unknown',
                        'connection_status': 'Unknown',
                        'has_connection': False,
                        'is_active': True,
                        'model': 'Unknown',
                        'os': 'Unknown',
                        'hardware_id': 'N/A',
                        'created': None,
                    })
        
        # Sort devices by name
        devices_data.sort(key=lambda x: x['name'].lower())
        
        return Response({
            'success': True,
            'devices': devices_data,
            'count': len(devices_data),
            'filters_applied': bool(organization_filter),
            'connection_filter_enabled': FILTER_BY_CONNECTION,
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting available devices: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve available devices',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    




@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def test_execution_history(request, execution_id):
    """
    API endpoint to get test execution history with enhanced statistics
    """
    try:
        execution = TestSuiteExecution.objects.get(pk=execution_id)
        
        # Get all execution devices
        execution_devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        ).select_related('device').order_by('device__name')
        
        # Get all test case executions
        test_case_executions = TestCaseExecution.objects.filter(
            test_suite_execution=execution
        ).select_related('device', 'test_case', 'test_case__category').order_by(
            'device__name', 'execution_order'
        )
        
        # Build response data
        devices_data = []
        for device_exec in execution_devices:
            device = device_exec.device
            device_test_cases = test_case_executions.filter(device=device)
            
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
                    # 'duration': test_exec.formatted_duration,
                })
            
            device_data = {
                'device_id': str(device.id),
                'device_name': device.name,
                'device_execution_id': str(device_exec.pk),
                'device_execution_status': device_exec.status,
                'error_message': device_exec.output if device_exec.status == 'failed' else None,
                'started_at': device_exec.started_at.isoformat() if device_exec.started_at else None,
                'completed_at': device_exec.completed_at.isoformat() if device_exec.completed_at else None,
                'statistics': {
                    'total': total,
                    'success': success,
                    'failed': failed,
                    'completed': completed,
                    'percentage': percentage,
                    'overall_status': overall_status
                },
                'test_cases': test_cases_data
            }
            
            devices_data.append(device_data)
        
        # Build execution summary
        execution_data = {
            'execution_id': str(execution.pk),
            'test_suite_name': execution.test_suite.name,
            'test_suite_id': str(execution.test_suite.pk),
            'category_name': execution.test_suite.category.name,
            'category_id': str(execution.test_suite.category.pk),
            'total_devices': execution.device_count,
            'total_test_cases': execution.test_suite.test_case_count,
            'is_executed': execution.is_executed,
            'created': execution.created.isoformat() if execution.created else None,
            'devices': devices_data
        }
        
        return Response({
            'success': True,
            'data': execution_data
        }, status=status.HTTP_200_OK)
        
    except TestSuiteExecution.DoesNotExist:
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_test_log(request, execution_id):
    """
    Download test execution log as text file
    """
    try:
        test_execution = TestCaseExecution.objects.get(pk=execution_id)
        
        # Simple format - just stdout and stderr
        content = []
        
        # Add header
        content.append(f"Test Log: {test_execution.test_case.name} on {test_execution.device.name}")
        content.append(f"Execution ID: {str(execution_id)}")  # Convert UUID to string
        content.append("=" * 60)
        content.append("")
        
        # Add stdout
        if test_execution.stdout:
            content.append("=== STANDARD OUTPUT ===")
            content.append(test_execution.stdout.strip())
            content.append("")
        
        # Add stderr
        if test_execution.stderr:
            content.append("=== STANDARD ERROR ===")
            content.append(test_execution.stderr.strip())
            content.append("")
        
        # If no output
        if not test_execution.stdout and not test_execution.stderr:
            content.append("No output available for this test execution.")
        
        # Join content
        final_content = '\n'.join(content)
        
        # Create plain text response
        response = HttpResponse(final_content, content_type='text/plain; charset=utf-8')
        
        # Set download filename - convert UUID to string before slicing
        filename = f"log_{test_execution.test_case.test_case_id}_{str(execution_id)[:8]}.txt"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except TestCaseExecution.DoesNotExist:
        return HttpResponse("Test execution not found", content_type='text/plain', status=404)
    except Exception as e:
        logger.error(f"Error downloading test log: {str(e)}")
        return HttpResponse(f"Error: {str(e)}", content_type='text/plain', status=500)



@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])  # Disable CSRF requirement
def retry_test_execution(request, execution_id):
    """
    Retry a single test execution
    """
    try:
        test_execution = TestCaseExecution.objects.get(pk=execution_id)
        
        # Check if test is in a retryable state
        if test_execution.status != 'failed':
            
            return Response({
                'success': False,
                'error': 'Only failed tests can be retried'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Import and call the Celery task
        from ..tasks import retry_test_execution as retry_task
        retry_task.delay(str(execution_id))
        
        return Response({
            'success': True,
            'message': 'Test retry initiated successfully',
            'execution_id': str(execution_id)
        }, status=status.HTTP_200_OK)
        
    except TestCaseExecution.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Test execution not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error retrying test: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to retry test',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def retry_device_tests(request, device_execution_id):
    """
    Retry all failed tests for a device
    """
    try:
        # Get the device execution
        device_execution = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
        
        # Get all failed test executions for this device
        failed_tests = TestCaseExecution.objects.filter(
            test_suite_execution=device_execution.test_suite_execution,
            device=device_execution.device,
            status='failed'
        )
        
        if not failed_tests.exists():
            return Response({
                'success': False,
                'error': 'No failed tests found for this device'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Import and call the Celery task for each failed test
        from ..tasks import retry_test_execution as retry_task
        retried_count = 0
        
        for test in failed_tests:
            retry_task.delay(str(test.pk))
            retried_count += 1
        
        return Response({
            'success': True,
            'message': f'Retrying {retried_count} failed tests',
            'device_execution_id': str(device_execution_id),
            'retried_count': retried_count
        }, status=status.HTTP_200_OK)
        
    except TestSuiteExecutionDevice.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Device execution not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error retrying device tests: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to retry device tests',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Create view instances
test_category_list = TestCategoryListCreateView.as_view()
test_category_detail = TestCategoryDetailView.as_view()
test_case_list = TestCaseListCreateView.as_view()
test_case_detail = TestCaseDetailView.as_view()
test_suite_list = TestSuiteListCreateView.as_view()
test_suite_detail = TestSuiteDetailView.as_view()
test_suite_execution_list = TestSuiteExecutionListCreateView.as_view()
test_suite_execution_detail = TestSuiteExecutionDetailView.as_view()


