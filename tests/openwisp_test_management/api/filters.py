from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from openwisp_users.api.mixins import FilterDjangoByOrgManaged

from ..swapper import load_model

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")


class TestCategoryFilter(FilterDjangoByOrgManaged):
    """API filter for test categories"""
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")
    
    class Meta:
        model = TestCategory
        fields = [
            "organization",
            "organization__slug",
            "name",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_valid_filterform_labels()

    def _set_valid_filterform_labels(self):
        """Set user-friendly labels for filters"""
        if "organization" in self.filters:
            self.filters["organization"].label = _("Organization")
        if "organization__slug" in self.filters:
            self.filters["organization__slug"].label = _("Organization slug")


class TestCaseFilter(FilterDjangoByOrgManaged):
    """API filter for test cases"""
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")
    test_case_id = filters.CharFilter(field_name="test_case_id", lookup_expr="icontains")
    category = filters.UUIDFilter(field_name="category")
    is_active = filters.BooleanFilter(field_name="is_active")
    
    class Meta:
        model = TestCase
        fields = [
            "category__organization",
            "category__organization__slug",
            "category",
            "name",
            "test_case_id",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_valid_filterform_labels()

    def _set_valid_filterform_labels(self):
        """Set user-friendly labels for filters"""
        if "category__organization" in self.filters:
            self.filters["category__organization"].label = _("Organization")
        if "category__organization__slug" in self.filters:
            self.filters["category__organization__slug"].label = _("Organization slug")
        if "category" in self.filters:
            self.filters["category"].label = _("Category")