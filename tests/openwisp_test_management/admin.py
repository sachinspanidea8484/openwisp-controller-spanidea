import logging

import reversion
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import model_ngettext
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from reversion.admin import VersionAdmin

from openwisp_users.multitenancy import MultitenantAdminMixin
from openwisp_utils.admin import TimeReadonlyAdminMixin

from .filters import (
    TestCategoryOrganizationFilter,
    TestCaseCategoryFilter,
    TestCaseCategoryOrganizationFilter,
)
from .swapper import load_model

logger = logging.getLogger(__name__)
TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")


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
        "test_case_count",
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
    
    delete_selected.short_description = _("Delete selected test categories")

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
        if "code" in form.base_fields:
         form.base_fields["code"].help_text = _(
            "Optional: Enter a code for internal reference"
        )    
        return form


@admin.register(TestCase)
class TestCaseAdmin(BaseVersionAdmin):
    list_display = [
        "name",
        "test_case_id",
        "category_link",
        "is_active",
        "created",
        "modified",
    ]
    list_filter = [
        TestCaseCategoryOrganizationFilter,
        TestCaseCategoryFilter,
        "is_active",
    ]
    list_select_related = ["category", "category__organization"]
    search_fields = ["name", "test_case_id", "description"]
    ordering = ["category__name", "name"]
    fields = [
        "category",
        "name",
        "test_case_id",
        "description",
        "is_active",
        "created",
        "modified",
    ]
    readonly_fields = ["created", "modified"]
    autocomplete_fields = ["category"]
    
    # Enable history button
    object_history_template = "reversion/object_history.html"
    
    actions = ["delete_selected", "recover_deleted", "activate_cases", "deactivate_cases"]

    def category_link(self, obj):
        """Display category as a link"""
        if obj.category:
            return format_html(
                '<a href="../testcategory/{}/change/">{}</a>',
                obj.category.pk,
                obj.category.name
            )
        return "-"
    category_link.short_description = _("Category")
    category_link.admin_order_field = "category__name"


    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        # Make test_case_id readonly after creation to maintain consistency
        # if obj and obj.pk:
        #     fields = list(fields) + ["test_case_id"]
        return fields

    def has_delete_permission(self, request, obj=None):
        """Check if user can delete test cases"""
        if not super().has_delete_permission(request, obj):
            return False
        if obj and not obj.is_deletable:
            return False
        return True

def delete_selected(self, request, queryset):
    """
    Custom delete action that checks if test cases can be deleted
    """
    # Check permissions
    if not self.has_delete_permission(request):
        raise PermissionDenied

    # Check for undeletable test cases
    undeletable = [obj for obj in queryset if not obj.is_deletable]

    if undeletable:
        msg = _("Cannot delete test cases that are in use: %s") % (
            ", ".join([str(obj) for obj in undeletable])
        )
        self.message_user(request, msg, messages.ERROR)
        return

    # Count before deletion
    count = queryset.count()

    # Perform deletion
     # Perform deletion
    self.delete_queryset(request, queryset)

    self.message_user(
        request,
        ngettext(
            "Successfully deleted %(count)d test case.",
            "Successfully deleted %(count)d test cases.",
            count,
        ) % {"count": count},
        messages.SUCCESS,
    )

    delete_selected.short_description = _("Delete selected test cases")

     

    @admin.action(description=_("Recover deleted test cases"))
    def recover_deleted(self, request, queryset):
        """Action to recover soft-deleted test cases"""
        # This is a placeholder for future soft-delete functionality
        self.message_user(
            request,
            _("Recovery functionality will be implemented in a future version"),
            messages.INFO
        )

    @admin.action(description=_("Activate selected test cases"))
    def activate_cases(self, request, queryset):
        """Activate selected test cases"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            ngettext(
                "%d test case was successfully activated.",
                "%d test cases were successfully activated.",
                updated,
            ) % updated,
            messages.SUCCESS,
        )

    @admin.action(description=_("Deactivate selected test cases"))
    def deactivate_cases(self, request, queryset):
        """Deactivate selected test cases"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            ngettext(
                "%d test case was successfully deactivated.",
                "%d test cases were successfully deactivated.",
                updated,
            ) % updated,
            messages.SUCCESS,
        )

    def changelist_view(self, request, extra_context=None):
        """Override to add custom title"""
        extra_context = extra_context or {}
        extra_context['title'] = _("Test Cases")
        return super().changelist_view(request, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add help text to form fields
        if "name" in form.base_fields:
            form.base_fields["name"].help_text = _(
                "Choose a descriptive name for this test case"
            )
        if "test_case_id" in form.base_fields:
            form.base_fields["test_case_id"].help_text = _(
                "Unique identifier that devices will use to execute this test. "
                # "This cannot be changed after creation."
            )
        return form


# Register models with reversion for history tracking
if not reversion.is_registered(TestCategory):
    reversion.register(TestCategory)
    
if not reversion.is_registered(TestCase):
    reversion.register(TestCase)    
