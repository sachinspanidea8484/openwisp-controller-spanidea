import logging

import reversion
from django import forms
from django.conf import settings

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import model_ngettext
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from reversion.admin import VersionAdmin
from .base.models import TestTypeChoices
import json
from django.urls import path
from django.shortcuts import get_object_or_404, render



from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.config.models import Device



from openwisp_utils.admin import TimeReadonlyAdminMixin

from .filters import (
    TestCaseCategoryFilter,
    TestCaseActiveFilter,
    TestCaseTypeFilter,

    TestSuiteCategoryFilter,
    TestSuiteActiveFilter,
    TestExecutionStatusFilter
)
from .swapper import load_model

logger = logging.getLogger(__name__)
TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteCase = load_model("TestSuiteCase")
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCaseExecution = load_model("TestCaseExecution")


# Device = load_model("config", "Device")
# Credentials = load_model("connection", "Credentials")
# DeviceConnection = load_model("connection", "DeviceConnection")





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
    search_fields = ["name" ,"code"]
    ordering = ["-created"]

    fields = [
        "name",
        "code",    # ✅ code visible only in Add/Edit form
        "description",
        # "created", 
        # "modified",
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
    
    def get_form(self, request, obj=None, **kwargs):
     form = super().get_form(request, obj, **kwargs)
    
    # Add placeholders and help text to form fields
     if "name" in form.base_fields:
        form.base_fields["name"].widget.attrs.update({
            'placeholder': _('Enter category name')
        })
        form.base_fields["name"].help_text = _(
            "Choose a descriptive name for this test category"
        )
        
     if "code" in form.base_fields:
        form.base_fields["code"].widget.attrs.update({
            'placeholder': _('Enter category code')  # Removed "Optional"
        })
        form.base_fields["code"].help_text = _(
            "Enter a required category code"  # Updated to indicate required
        )
        
     if "description" in form.base_fields:
         form.base_fields["description"].widget.attrs.update({
            'placeholder': _('Enter category description')
        })
        
     return form

    def changelist_view(self, request, extra_context=None):
        """Override to add custom title"""
        extra_context = extra_context or {}
        extra_context['title'] = _("Test Category")
        return super().changelist_view(request, extra_context) 

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






@admin.register(TestCase)
class TestCaseAdmin(BaseVersionAdmin):
    list_display = [
        "name",              # 1st - Test Case Name
        "test_case_id",      # 2nd - Test Case ID  
        "category_link",     # 3rd - Category
        "is_active",         # 4th - Is Active
        "test_type_display", # 5th - Test Type
        "created",           # 6th - Created
        "modified",          # 7th - Modified
    ]
    list_filter = [
        TestCaseCategoryFilter,
        TestCaseActiveFilter,
        TestCaseTypeFilter,
    ]
    list_select_related = ["category",]
    search_fields = ["name", "test_case_id", "description"]
    ordering = ["-created"]

    fields = [
        "category",
        "name",
        "test_case_id",
        "test_type",  # ADD THIS
        "params",  # ADD THIS - NEW FIELD
        "description",
        "is_active",
        # "created",
        # "modified",
    ]
    readonly_fields = ["created", "modified"]
    autocomplete_fields = ["category"]
    
    # Enable history button
    object_history_template = "reversion/object_history.html"
    
    actions = ["delete_selected", "recover_deleted", "activate_cases", "deactivate_cases"]

        # ADD THIS NEW METHOD
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

    def test_type_display(self, obj):
        """Display test type with a nice format"""
        return obj.get_test_type_display()
    test_type_display.short_description = _("Test Type")
    test_type_display.admin_order_field = "test_type"



    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        # Make test_case_id readonly after creation to maintain consistency
        # if obj and obj.pk:
        #     fields = list(fields) + ["test_case_id"]
        return fields
    

    def changelist_view(self, request, extra_context=None):
        """Override to add custom title"""
        extra_context = extra_context or {}
        extra_context['title'] = _("Test Cases")
        return super().changelist_view(request, extra_context) 

    def has_delete_permission(self, request, obj=None):
        """Check if user can delete test cases"""
        if not super().has_delete_permission(request, obj):
            return False
        if obj and not obj.is_deletable:
            return False
        return True
    def get_form(self, request, obj=None, **kwargs):
     form = super().get_form(request, obj, **kwargs)
    
     # Category field
     if "category" in form.base_fields:
        form.base_fields["category"].help_text = _(
            "Select the category this test case belongs to"
        )
    
     # Test Case Name field
     if "name" in form.base_fields:
        form.base_fields["name"].widget.attrs.update({
            'placeholder': _('Enter Test Case Name')
        })
        form.base_fields["name"].help_text = _(
            "Enter a descriptive name for this test case"
        )
        
     # Test Case ID field
     if "test_case_id" in form.base_fields:
        form.base_fields["test_case_id"].widget.attrs.update({
            'placeholder': _('Enter Test Case ID')
        })
        form.base_fields["test_case_id"].help_text = _(
            "Enter a unique identifier for this test case"
        )
        
     # Test Type field
     if "test_type" in form.base_fields:
        form.base_fields["test_type"].help_text = _(
            "Select the type of test to run"
        )
        
     # Parameters field
     if "params" in form.base_fields:
        form.base_fields["params"].widget.attrs.update({
            'placeholder': _('Enter Parameters')
        })
        form.base_fields["params"].help_text = _(
            "Optional parameters in JSON format. Leave empty if not needed"
        )
        
     # Description field
     if "description" in form.base_fields:
        form.base_fields["description"].widget.attrs.update({
            'placeholder': _('Enter Description'),
            'rows': 4
        })
        form.base_fields["description"].help_text = _(
            "Describe what this test case does"
        )
        
     # Is Active field
     if "is_active" in form.base_fields:
        form.base_fields["is_active"].help_text = _(
            "Check to make this test case active"
        )
        
     return form

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

   



class TestSuiteAdminForm(forms.ModelForm):
    """Custom form for TestSuite admin"""
    
    class Meta:
        model = TestSuite
        fields = ['name', 'description', 'category', 'is_active']
        labels = {
            'name': _('Test Group Name'),
            'description': _('Description'),
            'category': _('Select Test Category'),
            'is_active': _('Is Active'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Store the request data for later use
        self.request_data = kwargs.get('data', {})
        
        # If editing existing instance, get current test cases
        if self.instance and self.instance.pk:
            current_test_cases = self.instance.test_cases.all().values_list('id', flat=True)
            self.initial['selected_test_cases_data'] = json.dumps(
                [str(tc_id) for tc_id in current_test_cases]
            )
    
    def clean(self):
        """Custom validation with better error messages"""
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        
        if not category:
            return cleaned_data
        
        # Get selected test cases data
        selected_test_cases_data = self.data.get('selected_test_cases_data', '')
        
        # Validate that at least one test case is selected
        selected_count = 0
        if selected_test_cases_data:
            try:
                selected_ids = json.loads(selected_test_cases_data)
                selected_count = len([id for id in selected_ids if id])
            except json.JSONDecodeError:
                raise forms.ValidationError({
                    '__all__': _('Invalid test case selection data. Please try again.')
                })
        
        if selected_count == 0:
            raise forms.ValidationError({
                'category': _('At least one test case must be selected for this test group.')
            })
        
        # If this is an edit and category is being changed
        if self.instance and self.instance.pk and category:
            if self.instance.category_id != category.id and selected_count > 0:
                # Category is being changed - validate selected test cases belong to new category
                try:
                    selected_ids = json.loads(selected_test_cases_data)
                    
                    if selected_ids:
                        # Check if all selected test cases belong to the new category
                        valid_test_cases = TestCase.objects.filter(
                            id__in=selected_ids,
                            category=category,
                            is_active=True
                        ).count()
                        
                        if valid_test_cases != len([id for id in selected_ids if id]):
                            raise forms.ValidationError({
                                'category': _(
                                    'Some selected test cases do not belong to the new category. '
                                    'Please reselect test cases after changing the category.'
                                )
                            })
                except (json.JSONDecodeError, ValueError):
                    raise forms.ValidationError({
                        'category': _('Please reselect test cases for the new category.')
                    })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            
            # Process selected test cases
            selected_test_cases_data = self.data.get('selected_test_cases_data', '')
            logger.info(f"Received selected_test_cases_data: {selected_test_cases_data}")
            
            if selected_test_cases_data:
                try:
                    # Parse the JSON data
                    selected_ids = json.loads(selected_test_cases_data)
                    logger.info(f"Parsed test case IDs: {selected_ids}")
                    
                    # Filter out empty strings/None values
                    valid_ids = [id for id in selected_ids if id]
                    
                    if not valid_ids:
                        raise forms.ValidationError(_('At least one test case must be selected.'))
                    
                    # Clear existing test cases for this suite
                    TestSuiteCase.objects.filter(test_suite=instance).delete()
                    logger.info(f"Cleared existing test cases for suite: {instance.id}")
                    
                    # Create new TestSuiteCase entries
                    created_count = 0
                    for order, test_case_id in enumerate(valid_ids, start=1):
                        try:
                            # Verify test case exists and belongs to the same category
                            test_case = TestCase.objects.get(
                                id=test_case_id,
                                category=instance.category
                            )
                            
                            # Create the relationship
                            suite_case = TestSuiteCase.objects.create(
                                test_suite=instance,
                                test_case=test_case,
                                order=order
                            )
                            created_count += 1
                            logger.info(f"Created TestSuiteCase: {suite_case}")
                            
                        except TestCase.DoesNotExist:
                            logger.error(
                                f"Test case not found or doesn't belong to category: {test_case_id}"
                            )
                        except Exception as e:
                            logger.error(f"Error creating TestSuiteCase: {e}")
                    
                    logger.info(f"Created {created_count} TestSuiteCase entries")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing selected test cases JSON: {e}")
                    raise forms.ValidationError(_('Error processing selected test cases.'))
                except Exception as e:
                    logger.error(f"Unexpected error saving test cases: {e}")
                    raise forms.ValidationError(f'Error saving test cases: {str(e)}')
            else:
                # No test cases selected - this should be caught by clean() method
                raise forms.ValidationError(_('At least one test case must be selected.'))
        
        return instance
    

@admin.register(TestSuite)
class TestSuiteAdmin(BaseVersionAdmin):
    form = TestSuiteAdminForm
    change_form_template = 'admin/test_management/testsuite/change_form.html'
    
    list_display = [
        "name",
        "category_link", 
        "test_case_count",
        "is_active",
        "created",
        "modified",
    ]
    
    list_filter = [
        TestSuiteCategoryFilter,
        TestSuiteActiveFilter,
    ]
    
    list_select_related = ["category"]
    search_fields = ["name", "description"]
    # ordering = ["category__name", "name"]
    ordering = ["-created"]

    
    fields = [
        "name",
        "description",
        "is_active",
        "category",
    ]
    
    readonly_fields = ["created", "modified"]
    autocomplete_fields = ["category"]
    
    # Enable history button
    object_history_template = "reversion/object_history.html"
    
    actions = ["activate_groups", "deactivate_groups"]

    class Media:
        js = ('admin/js/jquery.init.js',)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Customize form fields
        if "name" in form.base_fields:
            form.base_fields["name"].widget.attrs.update({
                'placeholder': _('Enter Test Group Name'),
            })
            form.base_fields["name"].help_text = _(
                "Enter a descriptive name for this test group"
            )
        
        if "description" in form.base_fields:
            form.base_fields["description"].widget.attrs.update({
                'placeholder': _('Enter Description'),
                'rows': 4,
            })
            form.base_fields["description"].help_text = _(
                "Describe what this test group does"
            )
            
        if "category" in form.base_fields:
            form.base_fields["category"].help_text = _(
                "Select a category to see available test cases"
            )
            
        if "is_active" in form.base_fields:
            form.base_fields["is_active"].help_text = _(
                "Check to make this test group active"
            )
        
        return form

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

    def get_readonly_fields(self, request, obj=None):
        """Remove current_test_cases_display from readonly fields"""
        fields = list(super().get_readonly_fields(request, obj))
        # Don't add current_test_cases_display anymore
        return fields
    
    def get_fields(self, request, obj=None):
        """Same fields for both add and edit"""
        return [
            "name",
            "description", 
            "is_active",
            "category",
        ]

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add selected test cases with order to context"""
        extra_context = extra_context or {}
        
        obj = self.get_object(request, object_id)
        if obj:
            # Get test cases with their order
            test_suite_cases = TestSuiteCase.objects.filter(
                test_suite=obj
            ).select_related('test_case').order_by('order')
            
            test_cases_with_order = []
            for suite_case in test_suite_cases:
                test_cases_with_order.append({
                    'id': str(suite_case.test_case.id),
                    'name': suite_case.test_case.name,
                    'test_case_id': suite_case.test_case.test_case_id,
                    'order': suite_case.order
                })
            
            extra_context['selected_test_cases_with_order'] = json.dumps(test_cases_with_order)
        
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        """Save the model and handle test case relationships"""
        super().save_model(request, obj, form, change)
        
        # Handle test cases after the model is saved
        selected_test_cases_data = request.POST.get('selected_test_cases_data', '')
        logger.info(f"save_model - selected_test_cases_data: {selected_test_cases_data}")
        
        if selected_test_cases_data:
            try:
                # Parse the JSON data
                selected_ids = json.loads(selected_test_cases_data)
                logger.info(f"save_model - parsed IDs: {selected_ids}")
                
                # Clear existing test cases
                TestSuiteCase.objects.filter(test_suite=obj).delete()
                
                # Create new relationships
                for order, test_case_id in enumerate(selected_ids, start=1):
                    if test_case_id:
                        try:
                            test_case = TestCase.objects.get(
                                id=test_case_id,
                                category=obj.category  # Ensure test case belongs to same category
                            )
                            TestSuiteCase.objects.create(
                                test_suite=obj,
                                test_case=test_case,
                                order=order
                            )
                            logger.info(f"Created TestSuiteCase for test case: {test_case_id}")
                        except TestCase.DoesNotExist:
                            logger.error(f"Test case not found or category mismatch: {test_case_id}")
                        except Exception as e:
                            logger.error(f"Error creating TestSuiteCase: {e}")
                            
                # Show success message
                test_count = TestSuiteCase.objects.filter(test_suite=obj).count()
                messages.success(
                    request, 
                    f"Test group saved with {test_count} test cases."
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                messages.error(request, "Error processing selected test cases.")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                messages.error(request, f"Error saving test cases: {str(e)}")
        else:
            # Clear existing test cases if none selected
            TestSuiteCase.objects.filter(test_suite=obj).delete()
    
    def save_related(self, request, form, formsets, change):
        """Handle related objects after form save"""
        super().save_related(request, form, formsets, change)
        
        # Additional logging to debug
        logger.info(f"save_related called, change={change}")

    @admin.action(description=_("Activate selected test groups"))
    def activate_groups(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            ngettext(
                "%d test group was successfully activated.",
                "%d test groups were successfully activated.",
                updated,
            ) % updated,
            messages.SUCCESS,
        )

    @admin.action(description=_("Deactivate selected test groups"))
    def deactivate_groups(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            ngettext(
                "%d test group was successfully deactivated.",
                "%d test groups were successfully deactivated.",
                updated,
            ) % updated,
            messages.SUCCESS,
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = _("Test Groups")
        return super().changelist_view(request, extra_context)
# Add inline for execution devices
class TestSuiteExecutionDeviceInline(admin.TabularInline):
    """Inline admin for devices in a test execution"""  # Changed comment
    model = TestSuiteExecutionDevice
    extra = 0
    fields = ['device', 'status', 'started_at', 'completed_at']
    readonly_fields = ['device', 'status', 'started_at', 'completed_at']
    verbose_name = _("Test Execution Device")  # Add this
    verbose_name_plural = _("Test Execution Devices")  # Add this
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    




class TestSuiteExecutionAdminForm(forms.ModelForm):
    """Custom form for TestSuiteExecution admin"""
    
    class Meta:
        model = TestSuiteExecution
        fields = ['test_suite']
        labels = {
            'test_suite': _('Select Test Group'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Customize test_suite field
        if "test_suite" in self.fields:
            self.fields["test_suite"].help_text = _(
                "Select a test group to execute"
            )
            self.fields["test_suite"].queryset = TestSuite.objects.filter(
                is_active=True
            ).select_related('category')
    
    def clean(self):
        """Custom validation"""
        cleaned_data = super().clean()
        test_suite = cleaned_data.get('test_suite')
        
        if not test_suite:
            raise forms.ValidationError({
                'test_suite': _('Please select a test group to execute.')
            })
        
        # Validate selected devices
        selected_devices_data = self.data.get('selected_devices_data', '')
        if selected_devices_data:
            try:
                selected_device_ids = json.loads(selected_devices_data)
                if not selected_device_ids or len(selected_device_ids) == 0:
                    raise forms.ValidationError({
                        '__all__': _('At least one device must be selected for execution.')
                    })
                
                # Validate that all selected devices exist and are working
                valid_devices = Device.objects.filter(
                    id__in=selected_device_ids,
                    is_working=True
                ).count()
                
                if valid_devices != len(selected_device_ids):
                    raise forms.ValidationError({
                        '__all__': _('Some selected devices are not available or not working.')
                    })
                    
            except json.JSONDecodeError:
                raise forms.ValidationError({
                    '__all__': _('Invalid device selection data.')
                })
        else:
            raise forms.ValidationError({
                '__all__': _('At least one device must be selected for execution.')
            })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            
            # Process selected devices
            selected_devices_data = self.data.get('selected_devices_data', '')
            if selected_devices_data:
                try:
                    selected_device_ids = json.loads(selected_devices_data)
                    
                    # Clear existing devices for this execution
                    TestSuiteExecutionDevice.objects.filter(test_suite_execution=instance).delete()
                    
                    # Create new TestSuiteExecutionDevice entries
                    for device_id in selected_device_ids:
                        try:
                            device = Device.objects.get(id=device_id, is_working=True)
                            TestSuiteExecutionDevice.objects.create(
                                test_suite_execution=instance,
                                device=device,
                                status='pending'
                            )
                        except Device.DoesNotExist:
                            logger.error(f"Device not found or not working: {device_id}")
                        except Exception as e:
                            logger.error(f"Error creating TestSuiteExecutionDevice: {e}")
                            
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing selected devices JSON: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error saving devices: {e}")
        
        return instance















# @admin.register(TestSuiteExecution)
# class TestSuiteExecutionAdmin(BaseVersionAdmin):
#     form = TestSuiteExecutionAdminForm
#     change_form_template = 'admin/test_management/testsuiteexecution/change_form.html'
#     list_display = [
#         "test_suite_name",
#         "device_count",
#         # "execution_status",
#         "status_summary_display",
#         "is_executed",
#         "created",
#         "view_history",  # Add this new column
#     ]
#     list_filter = [
#         TestExecutionStatusFilter,  # Add this new filter
#         "created",
#         ("test_suite", admin.RelatedOnlyFieldListFilter),
#     ]
#     list_select_related = ["test_suite", "test_suite__category"]
#     search_fields = ["test_suite__name"]
#     ordering = ["-created"]
    
#     fields = [
#         "test_suite",
#     ]
    

#     readonly_fields = ["created", "modified"]
#     actions = ["execute_test_suite"]

#     class Media:
#         js = ('admin/js/jquery.init.js',)
    
#     class Meta:
#         verbose_name = _("Test Execution")  # Change from "Test Suite Execution"
#         verbose_name_plural = _("Test Executions")  # Change from "Test Suite Executions"
    
#     def changelist_view(self, request, extra_context=None):
#         """Override to add custom title"""
#         extra_context = extra_context or {}
#         extra_context['title'] = _("Test Executions")  # Change title
#         return super().changelist_view(request, extra_context)
    
#     def test_suite_name(self, obj):
#         """Display test suite name with link"""
#         if obj.test_suite:
#             return format_html(
#                 '<a href="../testsuite/{}/change/">{}</a>',
#                 obj.test_suite.pk,
#                 obj.test_suite.name
#             )
#         return "-"
#     test_suite_name.short_description = _("Test Group Name")
#     test_suite_name.admin_order_field = "test_suite__name"
    
#     def device_count(self, obj):
#         """Display device count"""
#         return obj.device_count
#     device_count.short_description = _("Devices") 
#     def get_urls(self):
#      """Add custom URL for test execution history"""
#      urls = super().get_urls()
#      custom_urls = [
#         path(
#             '<path:object_id>/history/',
#             self.admin_site.admin_view(self.execution_history_view),
#             name='test_management_testexecution_history'
#         ),
#      ]
#      return custom_urls + urls

#     def execution_history_view(self, request, object_id):
#      """Custom view for execution history"""
#      execution = get_object_or_404(TestSuiteExecution, pk=object_id)
    
#      # Get all execution devices
#      execution_devices = TestSuiteExecutionDevice.objects.filter(
#         test_suite_execution=execution
#      ).select_related('device').order_by('device__name')
    
#      # Get all test case executions
#      test_case_executions = TestCaseExecution.objects.filter(
#         test_suite_execution=execution
#      ).select_related('device', 'test_case', 'test_case__category').order_by(
#         'device__name', 'execution_order'
#      )
    
#      # Group test case executions by device
#      device_executions = {}
#      for device_exec in execution_devices:
#         device = device_exec.device
#         device_executions[device.id] = {
#             'device': device,
#             'device_execution': device_exec,
#             'test_cases': test_case_executions.filter(device=device)
#         }
    
#      context = {
#         'title': f'Test Execution History - {execution.test_suite.name}',
#         'execution': execution,
#         'execution_devices': execution_devices,
#         'device_executions': device_executions,
#         'test_case_executions': test_case_executions,
#         'opts': self.model._meta,
#         'has_view_permission': True,
#         'original': execution,
#         'preserved_filters': self.get_preserved_filters(request),
#      }
    
#      return render(
#         request,
#         'admin/test_management/testexecution/execution_history.html',
#         context
#         )

    
    
#     def view_history(self, obj):
#         """Add history view link"""
#         if obj.pk:
#             # You can customize the URL pattern based on your history view
#             return format_html(
#                 '<a href="{}" class="viewlink">View History</a>',
#             f'{obj.pk}/history/',
#             )
#         return "-"
#     view_history.short_description = _("History")
#     view_history.allow_tags = True
    
#     def execution_status(self, obj):
#         """Display execution status summary"""
#         summary = obj.status_summary
#         if isinstance(summary, str):
#             return summary
        
#         return format_html(
#             '<span title="Total: {total}, Completed: {completed}, Failed: {failed}, Running: {running}, Pending: {pending}">'
#             '✓ {completed} | ✗ {failed} | ⚡ {running} | ⏳ {pending}'
#             '</span>',
#             **summary
#         )
#     execution_status.short_description = _("Status")
    
#     def device_summary(self, obj):
#         """Display device summary in detail view"""
#         if not obj.pk:
#             return "-"
        
#         summary = obj.status_summary
#         if isinstance(summary, str):
#             return summary
        
#         return format_html(
#             '<div style="line-height: 1.8;">'
#             '<strong>Total Devices:</strong> {total}<br>'
#             '<strong>Completed:</strong> <span style="color: green;">✓ {completed}</span><br>'
#             '<strong>Failed:</strong> <span style="color: red;">✗ {failed}</span><br>'
#             '<strong>Running:</strong> <span style="color: orange;">⚡ {running}</span><br>'
#             '<strong>Pending:</strong> <span style="color: gray;">⏳ {pending}</span>'
#             '</div>',
#             **summary
#         )
#     device_summary.short_description = _("Execution Summary")
    
#     def has_delete_permission(self, request, obj=None):
#         """Prevent deletion of executed test suites"""
#         if obj and obj.is_executed:
#             return False
#         return super().has_delete_permission(request, obj)
    
#     @admin.action(description=_("Execute selected test suites"))
#     def execute_test_suite(self, request, queryset):
#         """Execute test suites using Celery tasks"""
#         from .tasks import execute_test_suite
        
#         # Filter only non-executed ones
#         to_execute = queryset.filter(is_executed=False)
        
#         if to_execute.count() == 0:
#             self.message_user(
#                 request,
#                 _("No pending executions to process"),
#                 messages.WARNING
#             )
#             return
        
#         executed_count = 0
#         for execution in to_execute:
#             # Calculate estimated test count
#             test_count = 0
#             device_count = execution.device_count
            
#             for test_case in execution.test_suite.test_cases.filter(test_type=1):
#                 test_count += 1
            
#             total_test_executions = test_count * device_count
            
#             # Mark as executed
#             execution.is_executed = True
#             execution.save()
            
#             # Launch Celery task
#             execute_test_suite.delay(str(execution.id))
#             executed_count += 1
            
#             # Log info
#             logger.info(
#                 f"Started execution {execution.id}: "
#                 f"{test_count} tests × {device_count} devices = "
#                 f"{total_test_executions} parallel test executions"
#             )
        
#         self.message_user(
#             request,
#             ngettext(
#                 "%d test execution was started.",
#                 "%d test executions were started.",
#                 executed_count,
#             ) % executed_count,
#             messages.SUCCESS,
#         )

    
        
        
# @admin.register(TestSuiteExecution)
# class TestSuiteExecutionAdmin(BaseVersionAdmin):
#     form = TestSuiteExecutionAdminForm
#     change_form_template = 'admin/test_management/testsuiteexecution/change_form.html'

    
#     list_display = [
#         "test_suite_name",
#         "device_count",
#         "status_summary_display", # want later
#         "is_executed",
#         "created",
#     ]
    
#     list_filter = [
#         "is_executed",
#         "created",
#     ]
    
#     search_fields = ["test_suite__name"]
#     ordering = ["-created"]
    
#     fields = [
#         "test_suite",
#     ]
    
#     readonly_fields = ["created", "modified"]
    
#     # Enable history button
#     object_history_template = "reversion/object_history.html"

#     class Media:
#         js = ('admin/js/jquery.init.js',)

#     def test_suite_name(self, obj):
#         """Display test suite name"""
#         return obj.test_suite.name
#     test_suite_name.short_description = _("Test Group Name")
#     test_suite_name.admin_order_field = "test_suite__name"

#     def status_summary_display(self, obj):
#         """Display execution status summary"""
#         summary = obj.status_summary
#         if not summary.get('has_devices', False):
#             return format_html('<span style="color: #999;">No devices</span>')
        
#         total = summary['total']
#         completed = summary['completed']
#         failed = summary['failed']
#         running = summary['running']
#         pending = summary['pending']
        
#         html = f'<div style="font-size: 12px;">'
#         html += f'<div>Total: {total}</div>'
#         if completed > 0:
#             html += f'<div style="color: #28a745;">Completed: {completed}</div>'
#         if running > 0:
#             html += f'<div style="color: #007bff;">Running: {running}</div>'
#         if failed > 0:
#             html += f'<div style="color: #dc3545;">Failed: {failed}</div>'
#         if pending > 0:
#             html += f'<div style="color: #ffc107;">Pending: {pending}</div>'
#         html += '</div>'
        
#         return format_html(html)
#     status_summary_display.short_description = _("Status Summary")

#     def get_form(self, request, obj=None, **kwargs):
#         form = super().get_form(request, obj, **kwargs)
        
#         # Customize form fields
#         if "test_suite" in form.base_fields:
#             form.base_fields["test_suite"].help_text = _(
#                 "Select a test group to execute on selected devices"
#             )
        
#         return form

#     def changelist_view(self, request, extra_context=None):
#         extra_context = extra_context or {}
#         extra_context['title'] = _("Test Executions")
#         return super().changelist_view(request, extra_context)

#     def has_change_permission(self, request, obj=None):
#         """Prevent editing of executed test suites"""
#         if obj and obj.is_executed:
#             return False
#         return super().has_change_permission(request, obj)

#     def has_delete_permission(self, request, obj=None):
#         """Prevent deletion of executed test suites"""
#         if obj and obj.is_executed:
#             return False
#         return super().has_delete_permission(request, obj)



@admin.register(TestSuiteExecution)
class TestSuiteExecutionAdmin(BaseVersionAdmin):
    form = TestSuiteExecutionAdminForm
    change_form_template = 'admin/test_management/testsuiteexecution/change_form.html'
    list_display = [
        "test_suite_name",
        "device_count",
        # "execution_status",
        # "status_summary_display",
        "is_executed",
        "created",
        "view_history",  # Add this new column
    ]
    list_filter = [
        TestExecutionStatusFilter,  # Add this new filter
        "created",
        ("test_suite", admin.RelatedOnlyFieldListFilter),
    ]
    list_select_related = ["test_suite", "test_suite__category"]
    search_fields = ["test_suite__name"]
    ordering = ["-created"]
    
    fields = [
        "test_suite",
    ]
    

    readonly_fields = ["created", "modified"]
    actions = ["execute_test_suite"]
    
    
    class Meta:
        verbose_name = _("Test Execution")  # Change from "Test Suite Execution"
        verbose_name_plural = _("Test Executions")  # Change from "Test Suite Executions"
    
    def changelist_view(self, request, extra_context=None):
        """Override to add custom title"""
        extra_context = extra_context or {}
        extra_context['title'] = _("Test Executions")  # Change title
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
    test_suite_name.short_description = _("Test Group Name")
    test_suite_name.admin_order_field = "test_suite__name"
    
    def device_count(self, obj):
        """Display device count"""
        return obj.device_count
    device_count.short_description = _("Devices") 
    def get_urls(self):
     """Add custom URL for test execution history"""
     urls = super().get_urls()
     custom_urls = [
        path(
            '<path:object_id>/history/',
            self.admin_site.admin_view(self.execution_history_view),
            name='test_management_testexecution_history'
        ),
     ]
     return custom_urls + urls

    def execution_history_view(self, request, object_id):
     """Custom view for execution history"""
     execution = get_object_or_404(TestSuiteExecution, pk=object_id)
    
     # Get all execution devices
     execution_devices = TestSuiteExecutionDevice.objects.filter(
        test_suite_execution=execution
     ).select_related('device').order_by('device__name')
    
     # Get all test case executions
     test_case_executions = TestCaseExecution.objects.filter(
        test_suite_execution=execution
     ).select_related('device', 'test_case', 'test_case__category').order_by(
        'device__name', 'execution_order'
     )
    
     # Group test case executions by device
     device_executions = {}
     for device_exec in execution_devices:
        device = device_exec.device
        device_executions[device.id] = {
            'device': device,
            'device_execution': device_exec,
            'test_cases': test_case_executions.filter(device=device)
        }
    
     context = {
        'title': f'Test Execution History - {execution.test_suite.name}',
        'execution': execution,
        'execution_devices': execution_devices,
        'device_executions': device_executions,
        'test_case_executions': test_case_executions,
        'opts': self.model._meta,
        'has_view_permission': True,
        'original': execution,
        'preserved_filters': self.get_preserved_filters(request),
     }
    
     return render(
        request,
        'admin/test_management/testexecution/execution_history.html',
        context
        )

    
    
    def view_history(self, obj):
        """Add history view link"""
        if obj.pk:
            # You can customize the URL pattern based on your history view
            return format_html(
                '<a href="{}" class="viewlink">View History</a>',
            f'{obj.pk}/history/',
            )
        return "-"
    view_history.short_description = _("History")
    view_history.allow_tags = True
    
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
    def execute_test_suite(self, request, queryset):
        """Execute test suites using Celery tasks"""
        from .tasks import execute_test_suite
        
        # Filter only non-executed ones
        to_execute = queryset.filter(is_executed=False)
        
        if to_execute.count() == 0:
            self.message_user(
                request,
                _("No pending executions to process"),
                messages.WARNING
            )
            return
        
        executed_count = 0
        for execution in to_execute:
            # Calculate estimated test count
            test_count = 0
            device_count = execution.device_count
            
            for test_case in execution.test_suite.test_cases.filter(test_type=1):
                test_count += 1
            
            total_test_executions = test_count * device_count
            
            # Mark as executed
            execution.is_executed = True
            execution.save()
            
            # Launch Celery task
            execute_test_suite.delay(str(execution.id))
            executed_count += 1
            
            # Log info
            logger.info(
                f"Started execution {execution.id}: "
                f"{test_count} tests × {device_count} devices = "
                f"{total_test_executions} parallel test executions"
            )
        
        self.message_user(
            request,
            ngettext(
                "%d test execution was started.",
                "%d test executions were started.",
                executed_count,
            ) % executed_count,
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
