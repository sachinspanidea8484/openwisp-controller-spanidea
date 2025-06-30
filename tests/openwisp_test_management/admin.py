import logging

import reversion
from django import forms

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import model_ngettext
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from reversion.admin import VersionAdmin

from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.config.models import Device



from openwisp_utils.admin import TimeReadonlyAdminMixin

from .filters import (
    TestCaseCategoryFilter,
    TestSuiteCategoryFilter,
    TestSuiteActiveFilter,
)
from .swapper import load_model

logger = logging.getLogger(__name__)
TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteCase = load_model("TestSuiteCase")
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")


class BaseAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    save_on_top = True


class BaseVersionAdmin(TimeReadonlyAdminMixin, VersionAdmin):
    history_latest_first = True
    save_on_top = True


@admin.register(TestCategory)
class TestCategoryAdmin(BaseVersionAdmin):
    list_display = [
        "name",
        "test_case_count",
        "created",
        "modified",
    ]
    list_filter = []
    search_fields = ["name", "description"]
    ordering = ["name"]
    fields = [
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
        TestCaseCategoryFilter,
        "is_active",
    ]
    list_select_related = ["category",]
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





class TestSuiteCaseInlineForm(forms.ModelForm):
    """Custom form for TestSuiteCase inline"""
    class Meta:
        model = TestSuiteCase
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only filter if we have a valid test suite with a category
        if (self.instance and 
            hasattr(self.instance, 'test_suite_id') and 
            self.instance.test_suite_id):
            try:
                test_suite = self.instance.test_suite
                if test_suite and test_suite.category:
                    self.fields['test_case'].queryset = TestCase.objects.filter(
                        category=test_suite.category,
                        is_active=True
                    ).order_by('name')
                    return
            except:
                pass
        
        # Fallback: show all active test cases
        self.fields['test_case'].queryset = TestCase.objects.filter(
            is_active=True
        ).order_by('name')


class TestSuiteCaseInline(admin.TabularInline):
    """Inline admin for test cases in a test suite"""
    model = TestSuiteCase
    form = TestSuiteCaseInlineForm
    extra = 1
    fields = ['test_case', 'order']
    ordering = ['order']
    verbose_name = _("Test Case")
    verbose_name_plural = _("Test Cases")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('test_case', 'test_case__category')
    
    # Override permission methods since TestSuiteCase has no model permissions
    def has_add_permission(self, request, obj=None):
        # Check parent model permissions instead
        return request.user.has_perm('test_management.change_testsuite')
    
    def has_change_permission(self, request, obj=None):
        # Check parent model permissions instead
        return request.user.has_perm('test_management.change_testsuite')
    
    def has_delete_permission(self, request, obj=None):
        # Check parent model permissions instead
        return request.user.has_perm('test_management.change_testsuite')
    
    def has_view_permission(self, request, obj=None):
        # Check parent model permissions instead
        return request.user.has_perm('test_management.view_testsuite')


class TestSuiteAdminForm(forms.ModelForm):
    """Custom form for TestSuite admin"""
    test_cases = forms.ModelMultipleChoiceField(
        queryset=TestCase.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("Test Cases"),
        help_text=_("Select test cases to include in this suite")
    )

    class Meta:
        model = TestSuite
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set up test cases field based on category
        if self.instance and self.instance.pk and hasattr(self.instance, 'category_id') and self.instance.category_id:
            # Editing existing suite
            self.fields['test_cases'].queryset = TestCase.objects.filter(
                category_id=self.instance.category_id,  # Use category_id instead of category
                is_active=True
            ).order_by('name')
            self.fields['test_cases'].initial = self.instance.test_cases.all()
        elif 'category' in self.data:
            # Creating new suite with category selected
            try:
                category_id = self.data.get('category')
                if category_id:
                    self.fields['test_cases'].queryset = TestCase.objects.filter(
                        category_id=category_id,
                        is_active=True
                    ).order_by('name')
            except (ValueError, TypeError):
                pass

    def save(self, commit=True):
        instance = super().save(commit=commit)
        
        if commit and 'test_cases' in self.cleaned_data:
            # Clear existing test cases
            instance.testsuitecase_set.all().delete()
            
            # Add selected test cases with order
            for order, test_case in enumerate(self.cleaned_data['test_cases'], start=1):
                TestSuiteCase.objects.create(
                    test_suite=instance,
                    test_case=test_case,
                    order=order
                )
        
        return instance


@admin.register(TestSuite)
class TestSuiteAdmin(BaseVersionAdmin):
    form = TestSuiteAdminForm
    list_display = [
        "name",
        "category_link",
        "test_case_count",
        "is_active",
        # "execution_count",
        "created",
        "modified",
    ]
    list_filter = [
        TestSuiteCategoryFilter,
        TestSuiteActiveFilter,
    ]
    list_select_related = ["category"]
    search_fields = ["name", "description"]
    ordering = ["category__name", "name"]
    fields = [
        "category",
        "name",
        "description",
        "is_active",
        # "test_cases",
        "created",
        "modified",
    ]
    readonly_fields = ["created", "modified"]
    autocomplete_fields = ["category"]
    inlines = [TestSuiteCaseInline]
    
    # Enable history button
    object_history_template = "reversion/object_history.html"
    
    actions = ["delete_selected", "recover_deleted", "activate_suites", "deactivate_suites"]

    class Media:
        css = {
            'all': ('test-management/css/test-suite-admin.css',)
        }
        js = ('test-management/js/test-suite-admin.js',)

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

    def test_case_count(self, obj):
        """Display count of test cases in this suite"""
        return obj.test_case_count
    test_case_count.short_description = _("Test Cases")

    def execution_count(self, obj):
        """Display count of executions"""
        return obj.execution_count
    execution_count.short_description = _("Executions")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        # Make category readonly after creation
        if obj and obj.pk:
            fields = list(fields) + ["category"]
        return fields

    def has_delete_permission(self, request, obj=None):
        """Check if user can delete test suites"""
        if not super().has_delete_permission(request, obj):
            return False
        if obj and not obj.is_deletable:
            return False
        return True

    def delete_selected(self, request, queryset):
        """Custom delete action that checks if test suites can be deleted"""
        # Check permissions
        if not self.has_delete_permission(request):
            raise PermissionDenied
        
        # Check if any test suite has executions
        undeletable = []
        for obj in queryset:
            if not obj.is_deletable:
                undeletable.append(obj)
        
        if undeletable:
            msg = _("Cannot delete test suites that have been executed: %s") % (
                ", ".join([str(obj) for obj in undeletable])
            )
            self.message_user(request, msg, messages.ERROR)
            return
        
        # If we're here, all selected test suites can be deleted
        count = queryset.count()
        
        # Delete objects
        for obj in queryset:
            obj.delete()
            
        self.message_user(
            request,
            ngettext(
                "Successfully deleted %(count)d test suite.",
                "Successfully deleted %(count)d test suites.",
                count,
            ) % {"count": count},
            messages.SUCCESS,
        )
    
    delete_selected.short_description = _("Delete selected test suites")

    @admin.action(description=_("Recover deleted test suites"))
    def recover_deleted(self, request, queryset):
        """Action to recover soft-deleted test suites"""
        self.message_user(
            request,
            _("Recovery functionality will be implemented in a future version"),
            messages.INFO
        )

    @admin.action(description=_("Activate selected test suites"))
    def activate_suites(self, request, queryset):
        """Activate selected test suites"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            ngettext(
                "%d test suite was successfully activated.",
                "%d test suites were successfully activated.",
                updated,
            ) % updated,
            messages.SUCCESS,
        )

    @admin.action(description=_("Deactivate selected test suites"))
    def deactivate_suites(self, request, queryset):
        """Deactivate selected test suites"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            ngettext(
                "%d test suite was successfully deactivated.",
                "%d test suites were successfully deactivated.",
                updated,
            ) % updated,
            messages.SUCCESS,
        )

    def changelist_view(self, request, extra_context=None):
        """Override to add custom title"""
        extra_context = extra_context or {}
        extra_context['title'] = _("Test Suites")
        return super().changelist_view(request, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add help text to form fields
        if "name" in form.base_fields:
            form.base_fields["name"].help_text = _(
                "Choose a descriptive name for this test suite"
            )
        return form

    def get_inline_instances(self, request, obj=None):
     """Show inline only when editing existing suite"""
     if obj and obj.pk:
        return super().get_inline_instances(request, obj)
     return []
    
class MassExecutionForm(forms.Form):
    """Form for creating mass executions"""
    test_suite = forms.ModelChoiceField(
        queryset=TestSuite.objects.filter(is_active=True),
        empty_label=_("Select a test suite"),
        label=_("Test Suite"),
        help_text=_("Select an active test suite to execute"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.none(),
        label=_("Devices"),
        help_text=_("Select devices with working SSH connections"),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'size': '10',
            'style': 'height: 300px;'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get only devices with working SSH connections

        working_device_ids = DeviceConnection.objects.filter(
            is_working=True,
            enabled=True
        ).values_list('device_id', flat=True)

        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        
        self.fields['devices'].queryset = Device.objects.filter(
            id__in=working_device_ids
        ).select_related('organization').order_by('organization__name', 'name')


# Add inline for execution devices
class TestSuiteExecutionDeviceInline(admin.TabularInline):
    """Inline admin for devices in a test suite execution"""
    model = TestSuiteExecutionDevice
    extra = 0
    fields = ['device', 'status', 'started_at', 'completed_at']
    readonly_fields = ['device', 'status', 'started_at', 'completed_at']
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Add the Mass Execution Admin
@admin.register(TestSuiteExecution)
class TestSuiteExecutionAdmin(BaseVersionAdmin):
    list_display = [
        "test_suite_name",
        "device_count",
        "execution_status",
        "is_executed",
        "created",
    ]
    list_filter = [
        "is_executed",
        "created",
        ("test_suite", admin.RelatedOnlyFieldListFilter),
    ]
    list_select_related = ["test_suite", "test_suite__category"]
    search_fields = ["test_suite__name"]
    ordering = ["-created"]
    fields = [
        "test_suite",
        "is_executed",
        "device_summary",
        "created",
        "modified",
    ]
    readonly_fields = ["device_summary", "created", "modified"]
    inlines = [TestSuiteExecutionDeviceInline]
    actions = ["execute_test_suites"]
    
    def get_urls(self):
        """Add custom URL for mass execution creation"""
        urls = super().get_urls()
        custom_urls = [
            # path(
            #     'mass-execution/',
            #     self.admin_site.admin_view(self.mass_execution_view),
            #     name='test_management_testsuitexecution_mass_execution'
            # ),
        ]
        return custom_urls + urls
    
    def mass_execution_view(self, request):
      
        """View for creating mass executions"""
        if request.method == 'POST':
            form = MassExecutionForm(request.POST)
            if form.is_valid():
                test_suite = form.cleaned_data['test_suite']
                devices = form.cleaned_data['devices']
                
                # Create test suite execution
                execution = TestSuiteExecution.objects.create(
                    test_suite=test_suite
                )
                
                # Create device executions
                for device in devices:
                    TestSuiteExecutionDevice.objects.create(
                        test_suite_execution=execution,
                        device=device
                    )
                
                self.message_user(
                    request,
                    _(f"Created mass execution for {test_suite.name} on {len(devices)} devices"),
                    messages.SUCCESS
                )
                
                # Redirect to the change page
                return HttpResponseRedirect(
                    reverse(
                        'admin:test_management_testsuitexecution_change',
                        args=[execution.pk]
                    )
                )
        else:
            form = MassExecutionForm()
        
        context = {
            'title': _('Create Mass Execution'),
            'form': form,
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
            'has_add_permission': self.has_add_permission(request),
            'has_change_permission': self.has_change_permission(request),
            'has_delete_permission': self.has_delete_permission(request),
        }
        
        return render(request, 'admin/test_management/mass_execution.html', context)
    
    def changelist_view(self, request, extra_context=None):
        """Override to add custom button"""
        extra_context = extra_context or {}
        extra_context['has_mass_execution_permission'] = self.has_add_permission(request)
        return super().changelist_view(request, extra_context)
    
    def test_suite_name(self, obj):
        """Display test suite name with link"""
        if obj.test_suite:
            return format_html(
                '<a href="../testsuite/{}/change/">{}</a>',
                obj.test_suite.pk,
                obj.test_suite.name
            )
        return "-"
    test_suite_name.short_description = _("Test Suite")
    test_suite_name.admin_order_field = "test_suite__name"
    
    def device_count(self, obj):
        """Display device count"""
        return obj.device_count
    device_count.short_description = _("Devices")
    
    def execution_status(self, obj):
        """Display execution status summary"""
        summary = obj.status_summary
        if isinstance(summary, str):
            return summary
        



        
        return format_html(
            '<span title="Total: {total}, Completed: {completed}, Failed: {failed}, Running: {running}, Pending: {pending}">'
            '✓ {completed} | ✗ {failed} | ⚡ {running} | ⏳ {pending}'
            '</span>',
            **summary
        )
    execution_status.short_description = _("Status")
    
    def device_summary(self, obj):
        """Display device summary in detail view"""
        if not obj.pk:
            return "-"
        
        summary = obj.status_summary
        if isinstance(summary, str):
            return summary
        
        return format_html(
            '<div style="line-height: 1.8;">'
            '<strong>Total Devices:</strong> {total}<br>'
            '<strong>Completed:</strong> <span style="color: green;">✓ {completed}</span><br>'
            '<strong>Failed:</strong> <span style="color: red;">✗ {failed}</span><br>'
            '<strong>Running:</strong> <span style="color: orange;">⚡ {running}</span><br>'
            '<strong>Pending:</strong> <span style="color: gray;">⏳ {pending}</span>'
            '</div>',
            **summary
        )
    device_summary.short_description = _("Execution Summary")
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of executed test suites"""
        if obj and obj.is_executed:
            return False
        return super().has_delete_permission(request, obj)
    
    @admin.action(description=_("Execute selected test suites"))
    def execute_test_suites(self, request, queryset):
        """Action to execute test suites"""
        # Filter only non-executed ones
        to_execute = queryset.filter(is_executed=False)
        
        if to_execute.count() == 0:
            self.message_user(
                request,
                _("No pending executions to process"),
                messages.WARNING
            )
            return
        
        # Here you would trigger the actual execution
        # For now, we'll just mark them as executed
        count = to_execute.update(is_executed=True)
        
        self.message_user(
            request,
            ngettext(
                "%d test suite execution was started.",
                "%d test suite executions were started.",
                count,
            ) % count,
            messages.SUCCESS,
        )


# Register models with reversion for history tracking
if not reversion.is_registered(TestCategory):
    reversion.register(TestCategory)
    
if not reversion.is_registered(TestCase):
    reversion.register(TestCase)    


# Register models with reversion for history tracking
if not reversion.is_registered(TestSuite):
    reversion.register(TestSuite)
    
# if not reversion.is_registered(TestSuiteCase):
#     reversion.register(TestSuiteCase)    

if not reversion.is_registered(TestSuiteExecution):
    reversion.register(TestSuiteExecution)