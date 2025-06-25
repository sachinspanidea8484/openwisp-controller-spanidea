from django.utils.translation import gettext_lazy as _
from django.contrib import admin

from .swapper import load_model

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")


class TestCaseCategoryFilter(admin.SimpleListFilter):
    """Filter test cases by category"""
    parameter_name = "category"
    title = _("category")
    
    def lookups(self, request, model_admin):
        # Get all categories
        categories = TestCategory.objects.all().order_by('name')
        return [(cat.id, cat.name) for cat in categories]
    
    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(category_id=value)
        return queryset


class TestSuiteCategoryFilter(admin.SimpleListFilter):
    """Filter test suites by category"""
    parameter_name = "category"
    title = _("category")
    
    def lookups(self, request, model_admin):
        # Get all categories
        categories = TestCategory.objects.all().order_by('name')
        return [(cat.id, cat.name) for cat in categories]
    
    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(category_id=value)
        return queryset


class TestSuiteActiveFilter(admin.SimpleListFilter):
    """Filter test suites by active status"""
    title = _("active status")
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