from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status

from rest_framework.decorators import api_view



from rest_framework.decorators import action
from rest_framework.response import Response
from .filters import TestSuiteFilter

from django.utils.translation import gettext_lazy as _
from .serializers import TestSuiteListSerializer
from .filters import TestSuiteFilter

from openwisp_controller.config.models import Device
from openwisp_controller.connection.models import DeviceConnection 
from .serializers import (
    TestSuiteExecutionListSerializer,
    TestSuiteExecutionSerializer,
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




# Create view instances
test_category_list = TestCategoryListCreateView.as_view()
test_category_detail = TestCategoryDetailView.as_view()
test_case_list = TestCaseListCreateView.as_view()
test_case_detail = TestCaseDetailView.as_view()
test_suite_list = TestSuiteListCreateView.as_view()
test_suite_detail = TestSuiteDetailView.as_view()
test_suite_execution_list = TestSuiteExecutionListCreateView.as_view()
test_suite_execution_detail = TestSuiteExecutionDetailView.as_view()