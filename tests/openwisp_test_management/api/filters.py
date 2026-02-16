from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from openwisp_controller.config.models import Device

from ..swapper import load_model
from openwisp_users.api.mixins import FilterDjangoByOrgManaged
TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteExecution = load_model("TestSuiteExecution")
TestDeviceGroup = load_model("TestDeviceGroup")
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
    name = filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label=_("Group Name (contains)")
    )
    is_active = filters.BooleanFilter(
        field_name="is_active",
        label=_("Is Active")
    )

    class Meta:
        model = TestSuite
        fields = ["name", "is_active"]


# ============================================================================
# TEST CASE FILTERS (FOR LISTING API)
# ============================================================================
class TestCaseFilter(filters.FilterSet):
    name = filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label=_("Test Case Name (contains)")
    )
    category = filters.UUIDFilter(
        field_name="category__id",
        label=_("Category ID (exact)")
    )
    test_type = filters.ChoiceFilter(
        field_name="test_type",
        choices=TestTypeChoices.choices,
        label=_("Test Type")
    )
    is_active = filters.BooleanFilter(
        field_name="is_active",
        label=_("Is Active")
    )

    class Meta:
        model = TestCase
        fields = ["name", "category", "test_type", "is_active"]



class TestSuiteExecutionFilter(filters.FilterSet):
    """API filter for test suite executions"""
    test_suite = filters.UUIDFilter(field_name="test_suite")
    is_executed = filters.BooleanFilter(field_name="is_executed")
    
    class Meta:
        model = TestSuiteExecution
        fields = [
            "test_suite",
            "is_executed",
        ]        


# ============================================================================
# TEST DEVICE GROUP FILTERS
# ============================================================================
class TestDeviceGroupFilter(FilterDjangoByOrgManaged):
    """
    Filter for TestDeviceGroup
    Organization-aware filtering for multi-tenant support
    """
    name = filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label=_("Group Name (contains)")
    )
    
    organization = filters.UUIDFilter(
        field_name="organization",
        label=_("Organization ID")
    )
    
    class Meta:
        model = TestDeviceGroup
        fields = ["name", "organization"]


# ============================================================================
# DEVICE FILTER (FOR ADDING DEVICES TO GROUP)
# ============================================================================
class DeviceFilterForGroup(FilterDjangoByOrgManaged):
    """
    Filter devices by organization
    Used when selecting devices to add to a test device group
    
    Query param:
        ?organization=<uuid>
        
    Only shows devices from the specified organization
    that the user has access to
    """
    name = filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label=_("Device Name (contains)")
    )
    
    organization = filters.UUIDFilter(
        field_name="organization",
        label=_("Organization ID"),
        required=True,  # Must specify organization
        help_text=_("Filter devices by organization (required)")
    )
    
    class Meta:
        model = Device
        fields = ["name", "organization"]
