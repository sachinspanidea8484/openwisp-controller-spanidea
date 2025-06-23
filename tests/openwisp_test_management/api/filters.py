from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters

from openwisp_users.api.mixins import FilterDjangoByOrgManaged

from ..swapper import load_model

TestCategory = load_model("TestCategory")


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