from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, pagination ,status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError


from openwisp_users.api.mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
from openwisp_users.api.permissions import DjangoModelPermissions
from rest_framework.permissions import IsAuthenticated

from ..swapper import load_model
from .filters import TestCategoryFilter ,TestSuiteFilter, TestCaseListFilter
from .serializers import (
    TestCategorySerializer,
    TestCategoryDetailSerializer,
    TestSuiteSerializer,
    TestSuiteDetailSerializer,
    AddTestCasesToGroupSerializer,
    RemoveTestCasesFromGroupSerializer,
    TestCaseListSerializer,
)

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
    - Regular users see only test cases they created
    
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
# TEST SUITE (TEST GROUP) VIEWS
# ============================================================================
class TestSuiteListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    """
    API endpoint for listing and creating test groups
    
    GET  /api/v1/test-management/test-group/
    - List all test groups (paginated)
    - Superusers see all groups
    - Regular users see only groups they created
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
        Regular users see only test groups they created
        """
        user = self.request.user
        qs = TestSuite.objects.all().select_related('created_by')
        
        if not user.is_superuser:
            # Regular users see only their own test groups
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
        Regular users see only test groups they created
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


@api_view(['POST'])
def add_test_cases_to_group(request, pk):
    """
    Add test cases to a test group
    
    POST /api/v1/test-management/test-group/<uuid:pk>/add-test-cases/
    
    Body:
    {
        "test_case_ids": ["uuid1", "uuid2", "uuid3"]
    }
    
    Response:
    {
        "message": "3 test case(s) added to test group",
        "test_group": {...},
        "added_count": 3
    }
    """
    # Check permissions
    if not request.user.is_authenticated:
        return Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Get test group
    try:
        test_group = TestSuite.objects.get(pk=pk)
    except TestSuite.DoesNotExist:
        return Response(
            {"detail": "Test group not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if user can modify this group
    if not request.user.is_superuser and test_group.created_by != request.user:
        return Response(
            {"detail": "You do not have permission to modify this test group."},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Validate request data
    serializer = AddTestCasesToGroupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    test_case_ids = serializer.validated_data['test_case_ids']
    
    # Add test cases
    with transaction.atomic():
        added_count = 0
        for test_case_id in test_case_ids:
            test_case = TestCase.objects.get(id=test_case_id)
            
            # Check if already exists
            if not test_group.test_cases.filter(id=test_case_id).exists():
                test_group.test_cases.add(test_case)
                added_count += 1
    
    # Return response
    test_group.refresh_from_db()
    group_serializer = TestSuiteDetailSerializer(test_group, context={'request': request})
    
    return Response({
        "message": f"{added_count} test case(s) added to test group",
        "test_group": group_serializer.data,
        "added_count": added_count
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def remove_test_cases_from_group(request, pk):
    """
    Remove test cases from a test group
    
    POST /api/v1/test-management/test-group/<uuid:pk>/remove-test-cases/
    
    Body:
    {
        "test_case_ids": ["uuid1", "uuid2"]
    }
    
    Response:
    {
        "message": "2 test case(s) removed from test group",
        "test_group": {...},
        "removed_count": 2
    }
    """
    # Check permissions
    if not request.user.is_authenticated:
        return Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Get test group
    try:
        test_group = TestSuite.objects.get(pk=pk)
    except TestSuite.DoesNotExist:
        return Response(
            {"detail": "Test group not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if user can modify this group
    if not request.user.is_superuser and test_group.created_by != request.user:
        return Response(
            {"detail": "You do not have permission to modify this test group."},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Validate request data
    serializer = RemoveTestCasesFromGroupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    test_case_ids = serializer.validated_data['test_case_ids']
    
    # Remove test cases
    with transaction.atomic():
        removed_count = 0
        for test_case_id in test_case_ids:
            if test_group.test_cases.filter(id=test_case_id).exists():
                test_group.test_cases.remove(test_case_id)
                removed_count += 1
    
    # Return response
    test_group.refresh_from_db()
    group_serializer = TestSuiteDetailSerializer(test_group, context={'request': request})
    
    return Response({
        "message": f"{removed_count} test case(s) removed from test group",
        "test_group": group_serializer.data,
        "removed_count": removed_count
    }, status=status.HTTP_200_OK)


# ============================================================================
# TEST CASE LISTING VIEW (WITH CATEGORY FILTER)
# ============================================================================

class TestCaseListView(ProtectedAPIMixin, generics.ListAPIView):
    """
    API endpoint for listing test cases with category filter
    
    GET /api/v1/test-management/test-cases/
    - List all test cases (paginated)
    - Superusers see all test cases
    - Regular users see only test cases they created
    - Filter by category (multiple): ?category=uuid1,uuid2
    - Filter by test_type, is_active, etc.
    - Search by name, test_case_id
    
    Examples:
    - All test cases: /test-cases/
    - By category: /test-cases/?category=uuid1&category=uuid2
    - Active only: /test-cases/?is_active=true
    - By type: /test-cases/?test_type=1
    - Search: /test-cases/?search=ping
    """
    serializer_class = TestCaseListSerializer
    pagination_class = ListViewPagination
    
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = TestCaseListFilter
    search_fields = ["name", "test_case_id", "description"]
    ordering_fields = ["name", "test_case_id", "created", "modified"]
    ordering = ["-created"]
    
    def get_queryset(self):
        """
        Superusers see all test cases
        Regular users see only test cases they created
        """
        user = self.request.user
        qs = TestCase.objects.all().select_related('category', 'created_by')
        
        if not user.is_superuser:
            # Regular users see only their own test cases
            qs = qs.filter(created_by=user)
        
        return qs


# Export view functions for urls.py
test_suite_list = TestSuiteListView.as_view()
test_suite_detail = TestSuiteDetailView.as_view()
test_case_list_view = TestCaseListView.as_view()
test_category_list = TestCategoryListView.as_view()
test_category_detail = TestCategoryDetailView.as_view()