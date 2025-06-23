from django.utils.translation import gettext_lazy as _

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