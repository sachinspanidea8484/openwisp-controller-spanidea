from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from ..swapper import load_model

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")


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
    
    class Meta:
        model = TestCase
        fields = [
            "category",
            "name",
            "test_case_id",
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