from django.utils.translation import gettext_lazy as _
from django.contrib import admin


from openwisp_users.multitenancy import (
    MultitenantOrgFilter,
    MultitenantRelatedOrgFilter,
)

from .swapper import load_model

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")


class TestCategoryOrganizationFilter(MultitenantOrgFilter):
    """Filter test categories by organization"""
    parameter_name = "organization"
    title = _("organization")


class TestCaseCategoryFilter(MultitenantRelatedOrgFilter):
    """Filter test cases by category"""
    field_name = "category"
    parameter_name = "category"
    title = _("category")
    
    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(category_id=value)
        return queryset


class TestCaseCategoryOrganizationFilter(MultitenantOrgFilter):
    """Filter test cases by organization through category"""
    parameter_name = "category__organization"
    rel_model = TestCategory
    title = _("organization")


class TestSuiteCategoryFilter(MultitenantRelatedOrgFilter):
    """Filter test suites by category"""
    field_name = "category"
    parameter_name = "category"
    title = _("category")
    
    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(category_id=value)
        return queryset


class TestSuiteCategoryOrganizationFilter(MultitenantOrgFilter):
    """Filter test suites by organization through category"""
    parameter_name = "category__organization"
    rel_model = TestCategory
    title = _("organization")


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