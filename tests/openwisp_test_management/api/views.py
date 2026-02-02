from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, pagination ,status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework.generics import GenericAPIView
from openwisp_users.api.mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
from openwisp_users.api.permissions import DjangoModelPermissions
from rest_framework.permissions import IsAuthenticated
from openwisp_test_management.utils import build_all_testcases_zip
from ..swapper import load_model
from .filters import TestCategoryFilter ,TestSuiteFilter, TestCaseFilter
from .serializers import (
    TestCategorySerializer,
    TestCategoryDetailSerializer,
    TestCaseSerializer,
    TestCaseDetailSerializer,
    TestSuiteSerializer,
    TestSuiteDetailSerializer,
)
from rest_framework.parsers import MultiPartParser, FormParser
TestCategory = load_model("TestCategory")
TestSuite = load_model("TestSuite")
TestCase = load_model("TestCase")
TestSuiteCase = load_model("TestSuiteCase")




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

test_case_list = TestCaseListView.as_view()
test_case_detail = TestCaseDetailView.as_view()

export_all_scripts = ExportAllTestCaseScriptsView.as_view()