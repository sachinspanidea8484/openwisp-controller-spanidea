from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from ..swapper import load_model

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteExecution = load_model("TestSuiteExecution")
from ..base.models import TestTypeChoices  # ADD THIS IMPORT



# ============================================================================
# TEST CATEGORY FILTERS
# ============================================================================
class TestCategoryFilter(filters.FilterSet):
    """
    Filter for TestCategory
    Allows filtering by name and code
    """
    name = filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label=_("Category Name (contains)")
    )
    
    code = filters.CharFilter(
        field_name="code",
        lookup_expr="iexact",
        label=_("Category Code (exact)")
    )
    
    class Meta:
        model = TestCategory
        fields = ["name", "code"]


# ============================================================================
# TEST SUITE (TEST GROUP) FILTERS
# ============================================================================

class TestSuiteFilter(filters.FilterSet):
    """Filter for TestSuite (Test Group)"""
    name = filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label=_("Group Name (contains)")
    )
    
    is_active = filters.BooleanFilter(
        field_name="is_active",
        label=_("Is Active")
    )
    
    created_by = filters.UUIDFilter(
        field_name="created_by",
        label=_("Created By (User ID)")
    )
    
    class Meta:
        model = TestSuite
        fields = ["name", "is_active", "created_by"]


# ============================================================================
# TEST CASE FILTERS (FOR LISTING API)
# ============================================================================

class TestCaseListFilter(filters.FilterSet):
    """Filter for TestCase listing"""
    name = filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label=_("Test Case Name (contains)")
    )
    
    test_case_id = filters.CharFilter(
        field_name="test_case_id",
        lookup_expr="icontains",
        label=_("Test Case ID (contains)")
    )
    
    category = filters.ModelMultipleChoiceFilter(
        field_name="category",
        queryset=load_model("TestCategory").objects.all(),
        label=_("Category (multiple)")
    )
    
    test_type = filters.ChoiceFilter(
        field_name="test_type",
        choices=[(1, 'Robot Framework'), (2, 'Device')],
        label=_("Test Type")
    )
    
    is_active = filters.BooleanFilter(
        field_name="is_active",
        label=_("Is Active")
    )
    
    created_by = filters.UUIDFilter(
        field_name="created_by",
        label=_("Created By (User ID)")
    )
    
    class Meta:
        model = TestCase
        fields = ["name", "test_case_id", "category", "test_type", "is_active", "created_by"]

# OLD 


class TestCaseFilter(filters.FilterSet):
    """API filter for test cases"""
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")
    test_case_id = filters.CharFilter(field_name="test_case_id", lookup_expr="icontains")
    category = filters.UUIDFilter(field_name="category")
    is_active = filters.BooleanFilter(field_name="is_active")
    test_type = filters.ChoiceFilter(
    field_name="test_type",
    choices=TestTypeChoices.choices,  # Use the actual choices
    label=_("Test Type")
    )
    
    class Meta:
        model = TestCase
        fields = [
            "category",
            "name",
            "test_case_id",
            "test_type",  # ADD THIS
            "is_active",
        ]


class TestSuiteFilter(filters.FilterSet):
    """API filter for test suites"""
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")
    # category = filters.UUIDFilter(field_name="category")
    is_active = filters.BooleanFilter(field_name="is_active")
    
    class Meta:
        model = TestSuite
        fields = [
            # "category",
            "name",
            "is_active",
        ]

class TestSuiteExecutionFilter(filters.FilterSet):
    """API filter for test suite executions"""
    test_suite = filters.UUIDFilter(field_name="test_suite")
    is_executed = filters.BooleanFilter(field_name="is_executed")
    created_after = filters.DateTimeFilter(field_name="created", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created", lookup_expr="lte")
    
    class Meta:
        model = TestSuiteExecution
        fields = [
            "test_suite",
            "is_executed",
            "created_after",
            "created_before",
        ]        