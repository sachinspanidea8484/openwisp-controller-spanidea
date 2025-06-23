import logging

import reversion
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import model_ngettext
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from reversion.admin import VersionAdmin

from openwisp_users.multitenancy import MultitenantAdminMixin
from openwisp_utils.admin import TimeReadonlyAdminMixin

from .filters import TestCategoryOrganizationFilter
from .swapper import load_model

logger = logging.getLogger(__name__)
TestCategory = load_model("TestCategory")


class BaseAdmin(MultitenantAdminMixin, TimeReadonlyAdminMixin, admin.ModelAdmin):
    save_on_top = True


class BaseVersionAdmin(MultitenantAdminMixin, TimeReadonlyAdminMixin, VersionAdmin):
    history_latest_first = True
    save_on_top = True


@admin.register(TestCategory)
class TestCategoryAdmin(BaseVersionAdmin):
    list_display = [
        "name",
        "organization",
        # "test_case_count", // later
        "created",
        "modified",
    ]
    list_filter = [TestCategoryOrganizationFilter]
    list_select_related = ["organization"]
    search_fields = ["name", "description"]
    ordering = ["name"]
    fields = [
        "organization",
        "name",
        "code",    # ✅ code visible only in Add/Edit form
        "description",
        "created",
        "modified",
    ]
    readonly_fields = ["created", "modified"]
    
    # Enable history button
    object_history_template = "reversion/object_history.html"
    
    actions = ["delete_selected", "recover_deleted"]

    def test_case_count(self, obj):
        """Display count of test cases in this category"""
        return obj.test_case_count
    test_case_count.short_description = _("Test Cases")

    def get_readonly_fields(self, request, obj=None):
     """
     Dynamically control which fields are readonly in the admin form.

     - For new objects (when obj is None or obj.pk doesn't exist):
        * Only 'created' and 'modified' fields are readonly.

     - For existing objects (edit form):
        * 'created' and 'modified' fields remain readonly.
        * 'organization' and 'time' fields are editable (because we don't add them to readonly_fields).
    
     You can customize this logic as needed.
     """
     fields = super().get_readonly_fields(request, obj)
    
    # Example: If you want 'organization' to be readonly during edit, uncomment below
    # if obj and obj.pk:
    #     fields = list(fields) + ["organization"]

     return fields

    def has_delete_permission(self, request, obj=None):
        """Check if user can delete test categories"""
        if not super().has_delete_permission(request, obj):
            return False
        if obj and not obj.is_deletable:
            return False
        return True

    def delete_selected(self, request, queryset):
     """
     Custom delete action that checks if categories can be deleted
     """
     # Check permissions
     if not self.has_delete_permission(request):
        raise PermissionDenied

     # Check if any category has test cases
     undeletable = []
     for obj in queryset:
        if not obj.is_deletable:
            undeletable.append(obj)

     if undeletable:
        msg = _("Cannot delete categories that contain test cases: %s") % (
            ", ".join([str(obj) for obj in undeletable])
        )
        self.message_user(request, msg, messages.ERROR)
        return

    # All selected categories can be deleted
     self.delete_queryset(request, queryset)

     self.message_user(
        request,
        ngettext(
            "Successfully deleted %(count)d test category.",
            "Successfully deleted %(count)d test categories.",
            queryset.count(),
        ) % {"count": queryset.count()},
        messages.SUCCESS,
    )

    @admin.action(description=_("Recover deleted test categories"))
    def recover_deleted(self, request, queryset):
        """Action to recover soft-deleted categories"""
        # This is a placeholder for future soft-delete functionality
        # For now, we'll show a message
        self.message_user(
            request,
            _("Recovery functionality will be implemented in a future version"),
            messages.INFO
        )
    
    def changelist_view(self, request, extra_context=None):
        """Override to add custom title"""
        extra_context = extra_context or {}
        extra_context['title'] = _("Test Categories")
        return super().changelist_view(request, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add help text to form fields
        if "name" in form.base_fields:
            form.base_fields["name"].help_text = _(
                "Choose a descriptive name for this test category"
            )
        return form


# Register model with reversion for history tracking
# reversion.register(TestCategory)


if not reversion.revisions.is_registered(TestCategory):
    reversion.register(TestCategory)