from django.utils.translation import gettext_lazy as _

from openwisp_users.multitenancy import (
    MultitenantOrgFilter,
    MultitenantRelatedOrgFilter,
)

from .swapper import load_model

TestCategory = load_model("TestCategory")


class TestCategoryOrganizationFilter(MultitenantOrgFilter):
    """Filter test categories by organization"""
    parameter_name = "organization"
    title = _("organization")