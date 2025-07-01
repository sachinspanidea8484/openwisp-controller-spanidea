from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from ..swapper import load_model

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteExecution = load_model("TestSuiteExecution")
from ..base.models import TestTypeChoices  # ADD THIS IMPORT



class TestCategoryFilter(filters.FilterSet):
    """API filter for test categories"""
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")
    
    class Meta:
        model = TestCategory
        fields = [
            "name",
        ]


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
    category = filters.UUIDFilter(field_name="category")
    is_active = filters.BooleanFilter(field_name="is_active")
    
    class Meta:
        model = TestSuite
        fields = [
            "category",
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