from django.contrib import admin

from django.utils.translation import gettext_lazy as _
from swapper import load_model

from openwisp_users.multitenancy import MultitenantRelatedOrgFilter

Config = load_model("config", "Config")

from django.contrib.admin.filters import RelatedFieldListFilter

class NoEmptyRelatedFieldListFilter(RelatedFieldListFilter):
    def choices(self, changelist):
        for choice in super().choices(changelist):
            if choice['display'] == '-':
                continue  # skip the "no group" option
            yield choice
            
class TemplatesFilter(MultitenantRelatedOrgFilter):
    title = _("template")
    field_name = "templates"
    parameter_name = "config__templates"
    rel_model = Config


class GroupFilter(MultitenantRelatedOrgFilter, admin.SimpleListFilter):
    title = _("group")
    field_name = "group"
    parameter_name = "group_id"


class DeviceGroupFilter(admin.SimpleListFilter):
    title = _("has devices?")
    parameter_name = "empty"

    def lookups(self, request, model_admin):
        return (
            ("true", _("No")),
            ("false", _("Yes")),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(device__isnull=self.value() == "true").distinct()
        return queryset
