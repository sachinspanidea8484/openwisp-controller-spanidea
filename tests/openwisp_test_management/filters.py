from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from openwisp_users.multitenancy import MultitenantOrgFilter


from .swapper import load_model

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")


from .base.models import TestTypeChoices


class TestCaseCategoryFilter(admin.SimpleListFilter):
    """Filter test cases by category"""
    parameter_name = "category"
    title = _("Category")
    
    def lookups(self, request, model_admin):
        # Get all categories
        categories = TestCategory.objects.all().order_by('name')
        return [(cat.id, cat.name) for cat in categories]
    
    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(category_id=value)
        return queryset


class TestCaseActiveFilter(admin.SimpleListFilter):
    """Filter test cases by active status"""
    parameter_name = "is_active"
    title = _("Is Active")  # This changes the filter title
    
    def lookups(self, request, model_admin):
        return [
            (True, _("Active")),
            (False, _("Inactive")),
        ]
    
    def queryset(self, request, queryset):
        value = self.value()
        if value == 'True':
            return queryset.filter(is_active=True)
        elif value == 'False':
            return queryset.filter(is_active=False)
        return queryset


class TestCaseTypeFilter(admin.SimpleListFilter):
    """Filter test cases by test type"""
    parameter_name = "test_type"
    title = _("Test Type")  # This changes the filter title
    
    def lookups(self, request, model_admin):
        # Get the choices from your TestTypeChoices
        return TestTypeChoices.choices
    
    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(test_type=value)
        return queryset

class TestSuiteCategoryFilter(admin.SimpleListFilter):
    """Filter test groups by category"""  # Changed comment
    parameter_name = "category"
    title = _("Category")  # You can change this if needed
    
    def lookups(self, request, model_admin):
        categories = TestCategory.objects.all().order_by('name')
        return [(cat.id, cat.name) for cat in categories]
    
    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(category_id=value)
        return queryset

class TestSuiteActiveFilter(admin.SimpleListFilter):
    """Filter test groups by active status"""
    parameter_name = "is_active"
    title = _("Is Active")
    
    def lookups(self, request, model_admin):
        return [
            ('1', _("Active")),
            ('0', _("Inactive")),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(is_active=True)
        elif self.value() == '0':
            return queryset.filter(is_active=False)
        return queryset
    """Filter test suites by active status"""
    title = _("Is Active")
    parameter_name = "is_active"
    
    def lookups(self, request, model_admin):
        return (
            ("1", _("Active")),
            ("0", _("Inactive")),
        )
    
    def queryset(self, request, queryset):
        if self.value() == "1":
            return queryset.filter(is_active=True)
        elif self.value() == "0":
            return queryset.filter(is_active=False)
        return queryset
    


# Add this new filter class at the top with other filters
class TestExecutionStatusFilter(admin.SimpleListFilter):
    title = _('execution status')
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return (
            ('0', _('Created')),
            ('1', _('Execution in Progress')),
            ('2', _('Partially Completed')),
            ('3', _('Completed')),
        )
    
    def queryset(self, request, queryset):
        value = self.value()
        if value is not None:
            # Iterate queryset and filter based on status property
            ids = [obj.id for obj in queryset if str(obj.status) == value]
            return queryset.filter(id__in=ids)
        return queryset














# Add these new filter classes:
class DeviceGroupOrganizationFilter(MultitenantOrgFilter):
    """Filter device groups by organization"""
    parameter_name = "organization"
    title = _("organization")

class DeviceGroupActiveFilter(admin.SimpleListFilter):
    title = _("device status")
    parameter_name = "device_status"

    def lookups(self, request, model_admin):
        return (
            ("active", _("Has Active Devices")),
            ("all_inactive", _("All Devices Inactive")),
            ("empty", _("No Devices")),
        )

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(devices__device___is_deactivated=False).distinct()
        elif self.value() == "all_inactive":
            return queryset.exclude(devices__device___is_deactivated=False).distinct()
        elif self.value() == "empty":
            return queryset.filter(devices__isnull=True)
        return queryset
