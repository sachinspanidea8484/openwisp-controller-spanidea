import logging

import reversion
from django import forms
from django.conf import settings

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import model_ngettext
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.http import JsonResponse
from django.db import transaction
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from reversion.admin import VersionAdmin
from .base.models import TestTypeChoices
import json
from django.urls import path
from django.shortcuts import get_object_or_404, render
import traceback

import json
from django.utils.translation import gettext_lazy as _

import time
from django.utils import timezone
from django.core.validators import RegexValidator
from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.config.models import Device

from reversion.models import Version
from django.http import HttpResponseRedirect
from django.urls import reverse

from openwisp_utils.admin import TimeReadonlyAdminMixin

from .filters import (
    TestCaseCategoryFilter,
    TestCaseActiveFilter,
    TestCaseTypeFilter,

    TestSuiteCategoryFilter,
    TestSuiteActiveFilter,
    TestExecutionStatusFilter,
    DeviceGroupOrganizationFilter,
    DeviceGroupActiveFilter
)
from .swapper import load_model
from openwisp_users.multitenancy import MultitenantOrgFilter, MultitenantRelatedOrgFilter
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper

logger = logging.getLogger(__name__)
TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteCase = load_model("TestSuiteCase")
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCaseExecution = load_model("TestCaseExecution")


TestDeviceGroup = load_model("TestDeviceGroup")
TestDeviceGroupDevice = load_model("TestDeviceGroupDevice")



# Device = load_model("config", "Device")
# Credentials = load_model("connection", "Credentials")
# DeviceConnection = load_model("connection", "DeviceConnection")





class BaseAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    save_on_top = True


class BaseVersionAdmin(TimeReadonlyAdminMixin, VersionAdmin):
    history_latest_first = True
    save_on_top = True
    list_per_page= 10


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
    
    def recover_view(self, request, version_id, extra_context=None):
        extra_context = extra_context or {}
        extra_context["is_recover_view"]= True
        return super().recover_view(request, version_id, extra_context=extra_context)
    
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

class FormattedJSONField(forms.CharField):
    """Custom field that formats JSON for display"""
    
    def prepare_value(self, value):
        """Format JSON value before displaying in the widget"""
        if value is None or value == '':
            return ''
        
        try:
            if isinstance(value, (dict, list)):
                parsed = value
            elif isinstance(value, str):
                parsed = json.loads(value)
            else:
                parsed = value
            
            # Format with proper indentation
            return json.dumps(parsed, indent=4, ensure_ascii=False, sort_keys=True)
        except (json.JSONDecodeError, TypeError):
            return value

allowed_test_case_id = RegexValidator(
    regex=r'^[A-Za-z0-9_\-.:/]+$',
    message=_("Only letters, numbers, underscores (_), hyphens (-), dots (.), colons (:), and slashes (/) are allowed.")
)

class TestCaseAdminForm(forms.ModelForm):
    test_case_id = forms.CharField(
        validators=[allowed_test_case_id],
        widget=forms.TextInput(attrs={
            'pattern': r'[A-Za-z0-9_\-.:/]+',
            'title': _("Only letters, numbers, _, -, ., :, / are allowed")
        })
    )

    params = FormattedJSONField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 15,
            'cols': 80,
            'placeholder': _('Enter Parameters in JSON format'),
            'id': 'id_params',
            
        })
    )
    
    json_file = forms.FileField(
        required=False,
        help_text=_("Upload a JSON file to populate parameters"),
        widget=forms.FileInput(attrs={
            'accept': '.json',
            'id': 'json-file-input',
            'style': 'display: none;'
        })
    )
    
    class Meta:
        model = TestCase
        fields = '__all__'
    
    def clean_params(self):
        params = self.cleaned_data.get('params')
        if params and params.strip():
            try:
                # Validate and minify JSON for storage
                return json.loads(params.strip())
                # return json.dumps(parsed, separators=(',', ':'))
                # return params
            except json.JSONDecodeError as e:
                raise forms.ValidationError(_("Invalid JSON format: {}".format(str(e))))
        return {}
    
    # def clean_json_file(self):
    #     json_file = self.cleaned_data.get('json_file')
    #     if json_file:
    #         try:
    #             content = json_file.read().decode('utf-8')
    #             json.loads(content)
    #             return json_file
    #         except (UnicodeDecodeError, json.JSONDecodeError) as e:
    #             raise forms.ValidationError(_("Invalid JSON file: {}".format(str(e))))
    #     return json_file

@admin.register(TestCase)
class TestCaseAdmin(BaseVersionAdmin):
    form = TestCaseAdminForm
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
        "json_file",
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

    def recover_view(self, request, version_id, extra_context=None):
        extra_context = extra_context or {}
        extra_context["is_recover_view"]= True
        return super().recover_view(request, version_id, extra_context=extra_context)

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
                "Only letters, numbers, _, -, ., :, / are allowed."
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
            
        if "json_file" in form.base_fields:
            form.base_fields["json_file"].widget.attrs.update({
                'id': 'json-file-input',  # Make sure this ID matches
                'accept': '.json',
                'style': 'display: none;'
            })
        return form

    class Media:
        js = ('test-management/js/json_file_handler.js',)  # Add custom JavaScript
        css = {
            'all': ('test-management/css/json_file_handler.css',)  # Optional custom CSS
        }

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

        

    # @admin.action(description=_("Recover deleted test cases"))
    # def recover_deleted(self, request, queryset):
    #     """Action to recover soft-deleted test cases"""
    #     # This is a placeholder for future soft-delete functionality
    #     self.message_user(
    #         request,
    #         _("Recovery functionality will be implemented in a future version"),
    #         messages.INFO
    #     )

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
        fields = ['name', 'description', 'is_active']
        labels = {
            'name': _('Test Group Name'),
            'description': _('Description'),
            'is_active': _('Is Active'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_data = kwargs.get('data', {})

        # Load current test cases (if editing existing suite)
        if self.instance and self.instance.pk:
            current_test_cases = self.instance.test_cases.all().values_list('id', flat=True)
            self.initial['selected_test_cases_data'] = json.dumps(
                [str(tc_id) for tc_id in current_test_cases]
            )

    def clean(self):
        cleaned_data = super().clean()
        
        selected_test_cases_data = self.data.get('selected_test_cases_data', '')

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
                '__all__': _('At least one test case must be selected for this test group.')
            })

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if commit:
            instance.save()

            selected_test_cases_data = self.data.get('selected_test_cases_data', '')
            logger.info(f"Received selected_test_cases_data: {selected_test_cases_data}")
            
            if selected_test_cases_data:
                try:
                    selected_ids = json.loads(selected_test_cases_data)
                    valid_ids = [id for id in selected_ids if id]

                    if not valid_ids:
                        raise forms.ValidationError(_('At least one test case must be selected.'))

                    # Clear old entries
                    TestSuiteCase.objects.filter(test_suite=instance).delete()

                    # Create new suite-case links
                    for order, test_case_id in enumerate(valid_ids, start=1):
                        try:
                            test_case = TestCase.objects.get(id=test_case_id)

                            TestSuiteCase.objects.create(
                                test_suite=instance,
                                test_case=test_case,
                                order=order
                            )

                        except TestCase.DoesNotExist:
                            logger.error(f"Test case not found: {test_case_id}")
                        except Exception as e:
                            logger.error(f"Error creating TestSuiteCase: {e}")

                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing selected test cases JSON: {e}")
                    raise forms.ValidationError(_('Error processing selected test cases.'))
                except Exception as e:
                    logger.error(f"Unexpected error saving test cases: {e}")
                    raise forms.ValidationError(f'Error saving test cases: {str(e)}')
            else:
                raise forms.ValidationError(_('At least one test case must be selected.'))

        return instance

@admin.register(TestSuite)
class TestSuiteAdmin(BaseVersionAdmin):
    form = TestSuiteAdminForm
    change_form_template = 'admin/test_management/testsuite/change_form.html'
    
    list_display = [
        "name",
        # "category_link", 
        "test_case_count",
        "is_active",
        "created",
        "modified",
    ]
    
    list_filter = [
        # TestSuiteCategoryFilter,
        TestSuiteActiveFilter,
    ]
    
    # list_select_related = ["category"]
    search_fields = ["name", "description"]
    # ordering = ["category__name", "name"]
    ordering = ["-created"]

    
    fields = [
        "name",
        "description",
        "is_active",
        # "category",
    ]
    
    readonly_fields = ["created", "modified"]
    # autocomplete_fields = ["category"]
    
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
            
            
        if "is_active" in form.base_fields:
            form.base_fields["is_active"].help_text = _(
                "Check to make this test group active"
            )
        
        return form

    # def category_link(self, obj):
    #     """Display category as a link"""
    #     if obj.category:
    #         return format_html(
    #             '<a href="../testcategory/{}/change/">{}</a>',
    #             obj.category.pk,
    #             obj.category.name
    #         )
    #     return "-"
    # category_link.short_description = _("Category")
    # category_link.admin_order_field = "category__name"

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
            # "category",
        ]

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add selected test cases with order to context"""
        extra_context = extra_context or {}
        
        obj = self.get_object(request, object_id)
        if obj:
            # Get test cases with their order
            test_suite_cases = TestSuiteCase.objects.filter(
                test_suite=obj
            ).select_related('test_case','test_case__category').order_by('order')
            
            test_cases_with_order = []
            for suite_case in test_suite_cases:
                test_cases_with_order.append({
                    'id': str(suite_case.test_case.id),
                    'name': suite_case.test_case.name,
                    'test_case_id': suite_case.test_case.test_case_id,
                    'order': suite_case.order,
                    'test_type_display': suite_case.test_case.get_test_type_display(),
                    'category': suite_case.test_case.category.name
                })
            
            extra_context['selected_test_cases_with_order'] = json.dumps(test_cases_with_order)
        extra_context['categories']= TestCategory.objects.all()

        
        return super().change_view(request, object_id, form_url, extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Override add view to add categories to context"""
        extra_context = extra_context or {}
        extra_context['categories'] = TestCategory.objects.all()
        return super().add_view(request, form_url, extra_context)
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
                                id=test_case_id
                                
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
    def recover_view(self, request, version_id, extra_context=None):
        extra_context = extra_context or {}
        extra_context["categories"] = list(TestCategory.objects.values("id", "name"))
        extra_context["is_recover_view"]= True
        version = self._get_version_object(version_id)
        obj = version._object_version.object

        # Get all related TestSuiteCase versions from the SAME revision
        related_versions = Version.objects.get_for_model(TestSuiteCase).filter(
            revision=version.revision
        )

        test_cases_with_order = []
        
        for related_version in related_versions:
            suite_case = related_version._object_version.object
            test_cases_with_order.append({
                'id': str(suite_case.test_case.id),
                'name': suite_case.test_case.name,
                'test_case_id': suite_case.test_case.test_case_id,
                'order': suite_case.order,
                'test_type_display': suite_case.test_case.get_test_type_display(),
                'category': suite_case.test_case.category.name
            })
        
        extra_context['selected_test_cases_with_order'] = json.dumps(test_cases_with_order)
        extra_context['show_category_filter']= True

        return super().recover_view(request, version_id, extra_context=extra_context)
    
    def _get_version_object(self, version_id):
        """
        Utility to fetch the Version object for the given version_id.
        This avoids duplicating queryset logic from reversion's internal code.
        """
        from reversion.models import Version
        try:
            return Version.objects.get(pk=version_id)
        except Version.DoesNotExist:
            return None

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
    
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['device_selection'].widget = forms.RadioSelect(choices=self.fields['device_selection'].choices)
        if getattr(self.instance, "status", None) not in [0,4]:
            self.fields['device_selection'].disabled = True
            self.fields['name'].disabled = True
            self.fields['test_suite'].disabled = True

        
        # Store selected devices data for later use
        self._selected_devices_data = None
        self._device_group=None
        # Customize test_suite field
        if "test_suite" in self.fields:
            self.fields["test_suite"].help_text = _(
                "Select a test group to execute"
            )
            self.fields["test_suite"].queryset = TestSuite.objects.filter(
                is_active=True
            )
    
    class Meta:
        model = TestSuiteExecution
        fields = ['name','test_suite', 'device_selection','device_group']
        labels = {
            'name' : _('Enter Execution Name'),
            'test_suite': _('Select Test Group'),
            'device_selection' :_('Device Selection Type'),
        }
    def clean(self):
        """Custom validation"""
        print(">>> CLEAN METHOD STARTED <<<")
        cleaned_data = super().clean()
        test_suite = cleaned_data.get('test_suite')
        
        if not test_suite:
            print(">>> ERROR: No test suite selected <<<")
            # raise forms.ValidationError({
            #     'test_suite': _('Please select a test group to execute.')
            # })
        
        # Validate selected devices
        selected_devices_data = self.data.get('selected_devices_data', '')
        print(f">>> Selected devices data from form: {selected_devices_data} <<<")
        
        device_selection = cleaned_data.get("device_selection")
        device_group= self.data.get('device_group','')
        self._device_group=device_group

        if device_selection == 1:
            if not device_group:
                raise forms.ValidationError("Device group is required when device selection type is 'Device Group'")

            # attach for later saving
            cleaned_data["device_group"] = (device_group)

            # org check
            # from .models import 
            # device_group = DeviceGroup.objects.filter(id=device_group).first()
            # if device_group and test_suite and device_group.organization_id != test_suite.organization_id:
                # raise forms.ValidationError("Device group must belong to the same organization")


        if selected_devices_data:
            try:
                selected_device_ids = json.loads(selected_devices_data)
                print(f">>> Parsed device IDs: {selected_device_ids} <<<")
                
                if not selected_device_ids or len(selected_device_ids) == 0:
                    print(">>> ERROR: No devices selected <<<")
                    raise forms.ValidationError({
                        '__all__': _('At least one device must be selected for execution.')
                    })
                
                # Validate that all selected devices exist and are working
                valid_devices = Device.objects.filter(
                    id__in=selected_device_ids,
                    # is_working=True
                ).count()
                
                print(f">>> Valid devices count: {valid_devices}, Selected count: {len(selected_device_ids)} <<<")
                
                if valid_devices != len(selected_device_ids):
                    print(">>> ERROR: Some devices are not available or not working <<<")
                    raise forms.ValidationError({
                        '__all__': _('Some selected devices are not available or not working.')
                    })
                
                # Store the validated device data for later use
                self._selected_devices_data = selected_devices_data
                    
            except json.JSONDecodeError:
                print(">>> ERROR: JSON decode error for device selection <<<")
                raise forms.ValidationError({
                    '__all__': _('Invalid device selection data.')
                })
        else:
            print(">>> ERROR: No device selection data found <<<")
            raise forms.ValidationError({
                '__all__': _('At least one device must be selected for execution.')
            })
        
        print(">>> CLEAN METHOD COMPLETED SUCCESSFULLY <<<")
        return cleaned_data
    
    def save_devices(self, instance):
        """Save devices for the test suite execution"""
        print(f">>> SAVE_DEVICES METHOD STARTED for instance: {instance.id} <<<")
        # if instance.device_selection == 1:
        #  # Skip, because model.save() already creates devices + testcases
        #  return
        
        # Use stored device data or get from form data
        selected_devices_data = self._selected_devices_data or self.data.get('selected_devices_data', '')
        print(f">>> Processing selected devices data: {selected_devices_data} <<<")
        
        if selected_devices_data:
            try:
                selected_device_ids = json.loads(selected_devices_data)
                print(f">>> Parsed device IDs for saving: {selected_device_ids} <<<")
                
                # Clear existing devices for this execution
                deleted_count = TestSuiteExecutionDevice.objects.filter(test_suite_execution=instance).delete()
                print(f">>> Deleted {deleted_count[0]} existing TestSuiteExecutionDevice entries <<<")
                
                # Create new TestSuiteExecutionDevice entries
                successful_devices = 0
                for device_id in selected_device_ids:
                    print(f">>> Processing device ID: {device_id} <<<")
                    try:
                        device = Device.objects.get(id=device_id)
                        print(f">>> Found device: {device} (ID: {device.id}) <<<")
                        
                        execution_device = TestSuiteExecutionDevice.objects.create(
                            test_suite_execution=instance,
                            device=device,
                            status='pending'
                        )
                        print(f">>> Created TestSuiteExecutionDevice: {execution_device.id} <<<")
                        successful_devices += 1
                        
                    except Device.DoesNotExist:
                        error_msg = f"Device not found: {device_id}"
                        logger.error(error_msg)
                        print(f">>> ERROR: {error_msg} <<<")
                    except Exception as e:
                        error_msg = f"Error creating TestSuiteExecutionDevice: {e}"
                        logger.error(error_msg)
                        print(f">>> ERROR: {error_msg} <<<")
                        print(f">>> Exception type: {type(e).__name__} <<<")
                        print(f">>> Full traceback: {traceback.format_exc()} <<<")
                
                print(f">>> Successfully created {successful_devices}/{len(selected_device_ids)} TestSuiteExecutionDevice entries <<<")
                
                # Verify the saved devices
                saved_devices = TestSuiteExecutionDevice.objects.filter(test_suite_execution=instance)
                print(f">>> Verification: Found {saved_devices.count()} devices in DB for this execution <<<")
                for sd in saved_devices:
                    print(f">>>   - Device: {sd.device.id}, Status: {sd.status} <<<")
                        
            except json.JSONDecodeError as e:
                error_msg = f"Error parsing selected devices JSON: {e}"
                logger.error(error_msg)
                print(f">>> ERROR: {error_msg} <<<")
            except Exception as e:
                error_msg = f"Unexpected error saving devices: {e}"
                logger.error(error_msg)
                print(f">>> ERROR: {error_msg} <<<")
                print(f">>> Exception type: {type(e).__name__} <<<")
                print(f">>> Full traceback: {traceback.format_exc()} <<<")
        else:
            print(">>> WARNING: No selected_devices_data found during save_devices <<<")
    
    def save(self, commit=True):
        print(">>> SAVE METHOD STARTED <<<")
        print(f">>> Commit parameter: {commit} <<<")
        
        instance = super().save(commit=False)
        print(f">>> Instance created/updated: {instance} (ID: {instance.id if instance.id else 'NEW'}) <<<")
        if instance.device_selection == 1 and self._device_group:
            try:
                device_group = TestDeviceGroup.objects.get(id=self._device_group)
                instance.device_group = device_group
                print(f">>> Assigned device_group_id: {instance.device_group} <<<")
            except ValueError:
                raise forms.ValidationError({
                    'device_group': _('Invalid device group selected.')
                })
        if commit:
            instance.save()
            print(f">>> Instance saved to DB. ID: {instance.id} <<<")
            
            # Save devices after the instance is saved
            self.save_devices(instance)
        else:
            # When commit=False, we need to add a hook to save devices later
            print(">>> Commit=False, adding save_m2m hook for devices <<<")
            old_save_m2m = self.save_m2m
            def save_m2m():
                old_save_m2m()
                print(">>> save_m2m called, now saving devices <<<")
                self.save_devices(instance)
            self.save_m2m = save_m2m
        
        print(f">>> SAVE METHOD COMPLETED. Returning instance: {instance} <<<")
        return instance


@admin.register(TestSuiteExecution)
class TestSuiteExecutionAdmin(BaseVersionAdmin):
    form = TestSuiteExecutionAdminForm
    
    change_form_template = 'admin/test_management/testsuitexecution/change_form.html'
    list_display = [
        "name",
        "test_suite_name",
        "device_count",
        "testcase_count",
        "status_label",
        "created",
        "view_history",
     ]
    list_filter = [
        TestExecutionStatusFilter,  # Add this new filter
        "created",
        ("test_suite", admin.RelatedOnlyFieldListFilter),
    ]
    list_select_related = ["test_suite"]
    search_fields = ["test_suite__name"]
    ordering = ["-created"]
    
    fields = [
        "name",
        "test_suite",
        "device_selection",
        # "device_group",
    ]
    autocomplete_fields=["test_suite"]
    

    readonly_fields = ["created", "modified", "device_count", "testcase_count"]
    actions = ["execute_test_suite"]
    class Media:
        js = ('admin/js/jquery.init.js',)
    
    class Meta:
        verbose_name = _("Test Execution")  # Change from "Test Suite Execution"
        verbose_name_plural = _("Test Executions")  # Change from "Test Suite Executions"
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)

        if db_field.name == "test_suite":
            obj_id = request.resolver_match.kwargs.get("object_id")
            if obj_id:
                obj = self.get_object(request, obj_id)
                if obj and obj.status not in [0,4]:
                    # unwrap RelatedFieldWidgetWrapper (removes the icons)
                    if isinstance(formfield.widget, RelatedFieldWidgetWrapper):
                        formfield.widget = formfield.widget.widget
                        formfield.widget.attrs["disabled"] = True
        return formfield
   
    #  function which trigger to show save and execute button on ui
    def render_change_form(
        self, request, context, *, add=False, change=False, form_url='', obj=None
    ):
        if obj and obj.is_executed:
            context["hide_submit_row"] = True
        else:
            context["hide_submit_row"] = False
        context['show_save_and_execute'] = True
        context['show_timed_execute']=True
        context['show_save_and_continue'] = context.get('show_save_and_continue', False)

        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )
    #  call this function when you want to execute the test suite
    def _start_execution(self, request, obj,from_action_execution):
        """
        Internal helper so we can call the same code from
        an admin *action* and from a change/add form.
        """
        self.execute_test_suite(request, self.model.objects.filter(pk=obj.pk), from_action_execution)

    # “Save & execute” after ADD call
    def response_add(self, request, obj, post_url_continue=None):
        if '_save_execute' in request.POST:
            super().save_model(request, obj, request.POST, True)
           
          
            transaction.on_commit(lambda: self._start_execution(request, obj,False))

            # Send the user back to the change form of what he just created
            return self.response_post_save_add(request, obj)
        if '_schedule_execution' in request.POST:
            schedule_datetime = request.POST.get("schedule_datetime")
            if schedule_datetime:
                self._schedule_execution(request, obj, schedule_datetime)
            return self.response_post_save_add(request, obj)

        return super().response_add(request, obj, post_url_continue)

    # “Save & execute” after CHANGE call
    def response_change(self, request, obj):
        if '_save_execute' in request.POST:
            self._start_execution(request, obj,True)
            return self.response_post_save_change(request, obj)   # stay on the same page
        
        if '_schedule_execution' in request.POST:
            
            schedule_datetime = request.POST.get("schedule_datetime")
            if schedule_datetime:
                self._schedule_execution(request, obj, schedule_datetime)
            return self.response_post_save_change(request, obj)
        return super().response_change(request, obj)

    def _schedule_execution(self, request, obj, schedule_datetime):
        from .models import ScheduledExecution
        from django.utils.dateparse import parse_datetime

        dt = parse_datetime(schedule_datetime)
        if not dt:
            self.message_user(request, "Invalid date/time format", level=messages.ERROR)
            return

        ScheduledExecution.objects.update_or_create(
            execution=obj,
            defaults={
                "scheduled_time": dt,
                "status": ScheduledExecution.Status.PENDING
            }
        )

        self.message_user(
            request,
            f"Execution scheduled for {dt}",
            messages.SUCCESS
        )

    def changelist_view(self, request, extra_context=None):
        """Override to add custom title"""
        extra_context = extra_context or {}
        extra_context['title'] = _("Test Executions")  # Change title
        return super().changelist_view(request, extra_context)
    
    def status_label(self, obj):
     """Return human readable execution status"""
     return obj.status_display
    status_label.short_description = _("Status")
    
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
        """Add custom URL for test execution history only"""
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
        """Custom view for execution history with enhanced statistics"""
        execution = get_object_or_404(TestSuiteExecution, pk=object_id)
        
        # Get all execution devices
        execution_devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        ).select_related('device').order_by('device__name')
        
        # Get all test case executions
        test_case_executions = TestCaseExecution.objects.filter(
            test_suite_execution=execution
        ).select_related('device', 'test_case').order_by(
            'device__name', 'execution_order'
        )
        
        # Group test case executions by device with statistics
        device_executions = {}
        for device_exec in execution_devices:
            device = device_exec.device
            device_test_cases = test_case_executions.filter(device=device)
            
            # Calculate statistics
            total = device_test_cases.count()
            success = device_test_cases.filter(status='success').count()
            failed = device_test_cases.filter(status='failed').count()
            completed = success + failed
            
            # Determine overall status
            if total == 0:
                overall_status = 'pending'
                percentage = 0
            elif completed == 0:
                overall_status = 'pending'
                percentage = 0
            elif failed == 0 and success == total:
                overall_status = 'success'
                percentage = 100
            else:
                overall_status = 'failed'
                percentage = (success / total * 100) if total > 0 else 0
            
            device_executions[device.id] = {
                'device': device,
                'device_execution': device_exec,
                'test_cases': device_test_cases,
                'stats': {
                    'total': total,
                    'success': success,
                    'failed': failed,
                    'completed': completed,
                    'percentage': percentage,
                    'overall_status': overall_status
                }
            }
        
        context = {
            'title': f'Test Execution History - {execution.test_suite.name}',
            'execution': execution,
            'execution_id': str(execution.pk),

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
    
    # def execution_status(self, obj):
    #     """Display execution status summary"""
    #     summary = obj.status_summary
    #     if isinstance(summary, str):
    #         return summary
        
    #     return format_html(
    #         '<span title="Total: {total}, Completed: {completed}, Failed: {failed}, Running: {running}, Pending: {pending}">'
    #         '✓ {completed} | ✗ {failed} | ⚡ {running} | ⏳ {pending}'
    #         '</span>',
    #         **summary
    #     )
    



    def save_model(self, request, obj, form, change):
        print(f">>> ADMIN save_model called. Change: {change} <<<")
        super().save_model(request, obj, form, change)
        print(f">>> Object saved with ID: {obj.id} <<<")
        if '_save_execute' in request.POST and not change:
            # Object is being saved for the first time, and "Save and Execute" was clicked
            self._start_execution(request, obj)
        # Ensure devices are saved
        if hasattr(form, 'save_devices'):
            form.save_devices(obj)

        # ✅ FIX: absolute import
        from openwisp_test_management.swapper import load_model
        TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")

        obj.device_count = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=obj
        ).count()
        obj.testcase_count = obj.test_suite.test_case_count if obj.test_suite_id else 0

        obj.save(update_fields=["device_count", "testcase_count"])

        print(f">>> ADMIN save_model completed. Updated device_count={obj.device_count}, testcase_count={obj.testcase_count} <<<")
    
    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        """Prevent deletion of executed test suites"""
        if obj and obj.is_executed:
            return False
        return super().has_delete_permission(request, obj)
    
    @admin.action(description=_("Execute Selected Test Groups"))
    def execute_test_suite(self, request, queryset, from_action_execution=True):
        """Execute test suites using Celery tasks"""
        from .tasks import execute_test_suite as execute_test_suite_task
        from .models import ScheduledExecution
        
        logger.info(f"Execute action triggered for {queryset.count()} items")
        
        if from_action_execution:

            #   executions that are actively scheduled/running
            active_scheduled_ids = ScheduledExecution.objects.filter(
                execution__in=queryset,
                status__in=[
                    ScheduledExecution.Status.QUEUED,      # Already triggered
                    ScheduledExecution.Status.IN_PROCESS   # Currently running
                ]
            ).values_list('execution_id', flat=True)
            
            
            #  executions scheduled for future
            future_scheduled_ids = ScheduledExecution.objects.filter(
                execution__in=queryset,
                status=ScheduledExecution.Status.PENDING,
                scheduled_time__gt=timezone.now()
            ).values_list('execution_id', flat=True)
            
            # executions that are overdue but still pending
            overdue_scheduled_ids = ScheduledExecution.objects.filter(
                execution__in=queryset,
                status=ScheduledExecution.Status.PENDING,
                scheduled_time__lte=timezone.now()
            ).values_list('execution_id', flat=True)
           
            #  Categorize the queryset
            active_scheduled = queryset.filter(id__in=active_scheduled_ids)
            future_scheduled = queryset.filter(id__in=future_scheduled_ids, is_executed=False)
            overdue_scheduled = queryset.filter(id__in=overdue_scheduled_ids, is_executed=False)
            
            #  Items to execute: Not scheduled OR not executed
            # Exclude actively running/queued items
            # Include overdue items (execute them immediately)
            to_execute = queryset.filter(is_executed=False).exclude(
                id__in=set(active_scheduled_ids) | set(future_scheduled_ids) 
            )
        else:
            
            future_scheduled_ids = ScheduledExecution.objects.filter(
                execution__in=queryset,
                status=ScheduledExecution.Status.PENDING,
                scheduled_time__gt=timezone.now()
            ).values_list('execution_id', flat=True)
            future_scheduled = queryset.filter(id__in=future_scheduled_ids, is_executed=False)
            to_execute = queryset.filter(is_executed=False).exclude(
                id__in=set(future_scheduled_ids) 
            )
        
        # Currently running/queued
        if active_scheduled.exists():
            count = active_scheduled.count()
            if request:
                self.message_user(
                    request,
                    _(f"{count} test suite(s) are currently running or queued. Skipping these."),
                    messages.WARNING
                )
            
        # Scheduled for future
        if future_scheduled.exists():
            count = future_scheduled.count()
            msg = f"{count} test suite(s) already scheduled for future execution."
            if request:
                self.message_user(request, _(msg), messages.INFO)
        
        
        # Nothing to execute
        if to_execute.count() == 0:
            if not (active_scheduled.exists() or future_scheduled.exists() or overdue_scheduled.exists()) and request:
                self.message_user(
                    request,
                    _("No pending executions to process"),
                    messages.WARNING
                )
            return
        
        #  Execute the filtered items
        executed_count = 0
        failed_count = 0
        
        for execution in to_execute:
            try:
                # Double-check not already executed
                if execution.is_executed:
                    logger.warning(f"Execution {execution.id} already marked as executed")
                    continue
                
                # Validate test and device counts
                test_count = execution.test_suite.test_cases.filter(test_type=1).count()
                device_count = execution.device_count
                
                # if test_count == 0:
                #     logger.warning(f"No tests found for execution {execution.id}")
                #     if request:
                #         self.message_user(
                #             request,
                #             f"Skipped {execution}: No tests found",
                #             messages.WARNING
                #         )
                #     continue
                
                # if device_count == 0:
                #     logger.warning(f"No devices for execution {execution.id}")
                #     if request:
                #         self.message_user(
                #             request,
                #             f"Skipped {execution}: No devices configured",
                #             messages.WARNING
                #         )
                #     continue
                
                # Mark as executed
                execution.is_executed = True
                execution.save()
                
                # Launch Celery task
                result = execute_test_suite_task.delay(str(execution.id))
                
                executed_count += 1
                
                total_test_executions = test_count * device_count
                logger.info(
                    f"Started execution {execution.id} (Task: {result.id}): "
                    f"{test_count} tests × {device_count} devices = "
                    f"{total_test_executions} parallel executions"
                )
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to execute {execution.id}: {e}", exc_info=True)
                if request:
                    self.message_user(
                        request,
                        f"Failed to start {execution}: {str(e)}",
                        messages.ERROR
                    )
        
        # Final feedback
        if executed_count > 0 and request:
            self.message_user(
                request,
                ngettext(
                    "%d test execution was started.",
                    "%d test executions were started.",
                    executed_count,
                ) % executed_count,
                messages.SUCCESS,
            )
        
        if failed_count > 0 and request:
            self.message_user(
                request,
                f"{failed_count} execution(s) failed to start",
                messages.ERROR
            )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            device_group= getattr(obj, "device_group", None)
            if device_group:
                extra_context["execution_device_group"] = {
                    "id": str(device_group.id),
                    "name": device_group.name,
                }
            else:
                extra_context["execution_device_group"] = None

            # check if it is in other state than created(0)
            if obj and obj.status != "0":
                extra_context["hide_submit_row"] = True
            related_device_ids = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution=obj
            ).values_list("device_id", flat=True)
            devices_query = Device.objects.filter(
                id__in=related_device_ids
            ).select_related("organization")
            devices_data = []
            for device in devices_query:
                device_status = "Offline"
                is_deactivated = getattr(device, "_is_deactivated", False)

                if is_deactivated:
                    device_status = "Deactivated"
                elif getattr(device, "last_ip", None) and getattr(device, "management_ip", None):
                    device_status = "Online"
                elif getattr(device, "last_ip", None):
                    device_status = "Reachable"

                devices_data.append({
                    "id": str(device.id),
                    "name": device.name,
                    "organization": device.organization.name if device.organization else "No Organization",
                    "organization_id": str(device.organization.id) if device.organization else None,
                    "last_ip": getattr(device, "last_ip", None) or "N/A",
                    "management_ip": getattr(device, "management_ip", None) or "N/A",
                    "mac_address": getattr(device, "mac_address", None) or "N/A",
                    "status": device_status,
                    "connection_status": "Unknown",
                    "has_connection": False,
                    "is_active": True,
                    "model": getattr(device, "model", None) or "Unknown",
                    "os": getattr(device, "os", None) or "Unknown",
                    "hardware_id": getattr(device, "hardware_id", None) or "N/A",
                    "created": device.created.isoformat() if hasattr(device, "created") and device.created else None,
                })

            extra_context["execution_devices_json"] = json.dumps(devices_data)
      
        return super().change_view(request, object_id, form_url, extra_context)
    
    def recover_view(self, request, version_id, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_execution_device_details'] = True
        extra_context["is_recover_view"]= True
        version = self._get_version_object(version_id)

        if version:

            execution_obj = version._object_version.object        
            # 🔹 Add device_group info if it exists
            device_group = getattr(execution_obj, "device_group", None)
            if device_group:
                extra_context["execution_device_group"] = {
                    "id": str(device_group.id),
                    "name": device_group.name,
                }
            else:
                extra_context["execution_device_group"] = None
            # Now get related devices (live DB, not historical)
            related_versions = version.revision.version_set.filter(
            content_type__model="testsuiteexecutiondevice"
            )

            recovered_device_ids = [str(v._object_version.object.device_id) for v in related_versions]

            # 🔹 Re-use logic from get_available_devices
            devices_query = Device.objects.filter(id__in=recovered_device_ids).select_related("organization")
            print("devices_query>>>>>>>>>>>>",devices_query)
            devices_data = []
            for device in devices_query:

                device_status = 'Offline'
                is_deactivated = getattr(device, '_is_deactivated', False)
                
                if is_deactivated:
                    device_status = 'Deactivated'
                elif getattr(device, 'last_ip', None) and getattr(device, 'management_ip', None):
                    device_status = 'Online'
                elif getattr(device, 'last_ip', None):
                    device_status = 'Reachable'
                devices_data.append({
                    'id': str(device.id),
                    'name': device.name,
                    'organization': device.organization.name if device.organization else 'No Organization',
                    'organization_id': str(device.organization.id) if device.organization else None,
                    'last_ip': getattr(device, 'last_ip', None) or 'N/A',
                    'management_ip': getattr(device, 'management_ip', None) or 'N/A',
                    'mac_address': getattr(device, 'mac_address', None) or 'N/A',
                    'status': device_status,
                    'connection_status': 'Unknown',  # you can expand this to match get_available_devices
                    'has_connection': False,          # or compute properly like in API
                    'is_active': True,
                    'model': getattr(device, 'model', None) or 'Unknown',
                    'os': getattr(device, 'os', None) or 'Unknown',
                    'hardware_id': getattr(device, 'hardware_id', None) or 'N/A',
                    'created': device.created.isoformat() if hasattr(device, 'created') and device.created else None,
                })
            

            extra_context['execution_devices_json'] = json.dumps(devices_data)

        return super().recover_view(request, version_id, extra_context=extra_context)



    def _get_version_object(self, version_id):
        """
        Utility to fetch the Version object for the given version_id.
        This avoids duplicating queryset logic from reversion's internal code.
        """
        from reversion.models import Version
        try:
            return Version.objects.get(pk=version_id)
        except Version.DoesNotExist:
            return None
  







# Admin Forms
class TestDeviceGroupAdminForm(forms.ModelForm):
    """Custom form for TestDeviceGroup admin"""
    
    class Meta:
        model = TestDeviceGroup
        fields = ['organization', 'name', 'description']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load current devices if editing existing group
        if self.instance and self.instance.pk:
            current_devices = self.instance.devices.all().values_list('device__id', flat=True)
            self.initial['selected_devices_data'] = json.dumps(
                [str(device_id) for device_id in current_devices]
            )
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name and (len(name) < 3 or len(name) > 100):
            raise forms.ValidationError(_("Group name must be between 3 and 100 characters"))
        return name
    
    def clean_description(self):
        description = self.cleaned_data.get('description')
        if description and len(description) > 500:
            raise forms.ValidationError(_("Description cannot exceed 500 characters"))
        return description
    
    def clean(self):
        cleaned_data = super().clean()
        
        selected_devices_data = self.data.get('selected_devices_data', '')

        selected_count = 0
        if selected_devices_data:
            try:
                selected_ids = json.loads(selected_devices_data)
                selected_count = len([id for id in selected_ids if id])
            except json.JSONDecodeError:
                raise forms.ValidationError({
                    '__all__': _('Invalid test Device selection data. Please try again.')
                })

        if selected_count == 0:
            raise forms.ValidationError({
                '__all__': _('At least one test Device must be selected for this Device group.')
            })

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            
            # Handle device relationships
            selected_devices_data = self.data.get('selected_devices_data', '')
            
            if selected_devices_data:
                try:
                    selected_ids = json.loads(selected_devices_data)
                    valid_ids = [id for id in selected_ids if id]
                    
                    # Clear old devices
                    TestDeviceGroupDevice.objects.filter(group=instance).delete()
                    
                    # Add new devices
                    for device_id in valid_ids:
                        try:
                            device = Device.objects.get(id=device_id)
                            TestDeviceGroupDevice.objects.create(
                                group=instance,
                                device=device
                            )
                        except Device.DoesNotExist:
                            logger.error(f"Device not found: {device_id}")
                        except forms.ValidationError as e:
                            logger.error(f"Validation error adding device {device_id}: {e}")
                        except Exception as e:
                            logger.error(f"Error adding device to group: {e}")
                            
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing selected devices JSON: {e}")
                    raise forms.ValidationError(_('Error processing selected devices.'))
                except Exception as e:
                    logger.error(f"Unexpected error saving devices: {e}")
                    raise forms.ValidationError(f'Error saving devices: {str(e)}')
            else:
                # Clear all devices if none selected
                TestDeviceGroupDevice.objects.filter(group=instance).delete()
                
        return instance

# Admin Classes
@admin.register(TestDeviceGroup)
class TestDeviceGroupAdmin(BaseVersionAdmin):
    form = TestDeviceGroupAdminForm
    change_form_template = 'admin/test_management/testdevicegroup/change_form.html'
    
    list_display = [
        "name",
        "organization",
        "device_count",
        # "active_device_count",
        "created",
        "modified",
    ]
    
    list_filter = [
        DeviceGroupOrganizationFilter,
        # DeviceGroupActiveFilter,
    ]
    
    list_select_related = ["organization"]
    search_fields = ["name",  "organization__name"]
    ordering = ["-created"]
    
    fields = [
        "organization",
        "name",
        "description",
    ]
    
    readonly_fields = ["created", "modified"]
    autocomplete_fields = ["organization"]
    
    actions = ["delete_selected"]


    # Enable history button
    object_history_template = "reversion/object_history.html"
    
    class Media:
        js = ('admin/js/jquery.init.js',)
        css = {
            'all': ('test-management/css/device_group_form.css',)
        }
   
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
      
        org = request.user.organizations_owned
        if org:
            return qs.filter(organization__in=org)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Customize form fields
        if "organization" in form.base_fields:
            form.base_fields["organization"].help_text = _(
                "Select the organization for this device group"
            )
            
        if "name" in form.base_fields:
            form.base_fields["name"].widget.attrs.update({
                'placeholder': _('Enter Device Group Name'),
            })
            form.base_fields["name"].help_text = _(
                "Enter a name for this device group (3-100 characters)"
            )
        
        if "description" in form.base_fields:
            form.base_fields["description"].widget.attrs.update({
                'placeholder': _('Enter Description'),
                'rows': 4,
            })
            form.base_fields["description"].help_text = _(
                "Describe the purpose of this device group (max 500 characters)"
            )
            
        return form
    
    def device_count(self, obj):
        """Display total device count"""
        return obj.device_count
    device_count.short_description = _("Total Devices")
    
    def active_device_count(self, obj):
        """Display active device count"""
        count = obj.devices.filter(device___is_deactivated=False).count()
        if count == 0 and obj.device_count > 0:
            return format_html(
                '<span style="color: #dc3545;">{}</span>',
                count
            )
        return count
    active_device_count.short_description = _("Active Devices")
    
    # def get_queryset(self, request):
    #     """Filter queryset based on user permissions"""
    #     qs = super().get_queryset(request)
    #     # MultitenantOrgFilter will handle organization filtering
    #     return qs
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add devices to context"""
        extra_context = extra_context or {}
        
        obj = self.get_object(request, object_id)
        if obj:
                        # Get current devices in the group
            group_devices = TestDeviceGroupDevice.objects.filter(
                group=obj
            ).select_related('device', 'device__organization').order_by('device__name')
            
            selected_devices = []
            for group_device in group_devices:
                device = group_device.device
                selected_devices.append({
                    'id': str(device.id),
                    'name': device.name,
                    'mac_address': device.mac_address,
                    'last_ip': device.last_ip or '-',
                    'is_active': not device._is_deactivated,
                    'organization': device.organization.name
                })
            
            extra_context['selected_devices'] = json.dumps(selected_devices)
            extra_context['organization_id'] = str(obj.organization.id)
        
        return super().change_view(request, object_id, form_url, extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Override add view to add context"""
        extra_context = extra_context or {}
        # Will be populated by JavaScript based on selected organization
        extra_context['selected_devices'] = json.dumps([])
        return super().add_view(request, form_url, extra_context)
    
    def save_model(self, request, obj, form, change):
        """Save the model and handle device relationships"""
        super().save_model(request, obj, form, change)
        
        # Handle devices after the model is saved
        selected_devices_data = request.POST.get('selected_devices_data', '')
        
        if selected_devices_data:
            try:
                selected_ids = json.loads(selected_devices_data)
                
                # Clear existing devices
                TestDeviceGroupDevice.objects.filter(group=obj).delete()
                
                # Add new devices
                success_count = 0
                error_count = 0
                
                for device_id in selected_ids:
                    if device_id:
                        try:
                            device = Device.objects.get(
                                id=device_id,
                                organization=obj.organization  # Ensure same org
                            )
                            TestDeviceGroupDevice.objects.create(
                                group=obj,
                                device=device
                            )
                            success_count += 1
                        except Device.DoesNotExist:
                            # error_count += 1
                            logger.error(f"Device not found or wrong org: {device_id}")
                        except ValidationError as e:
                            error_count += 1
                            logger.error(f"Validation error: {e}")
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error adding device: {e}")
                
                # Show appropriate message
                # if success_count > 0:
                    # messages.success(
                    #     request,
                    #     f"Device group saved with {success_count} device(s)."
                    # )
                
                if error_count > 0:
                    messages.warning(
                        request,
                        f"{error_count} device(s) could not be added due to errors."
                    )
                    
            except json.JSONDecodeError:
                messages.error(request, "Error processing selected devices.")
            except Exception as e:
                messages.error(request, f"Unexpected error: {str(e)}")
        else:
            # Clear devices if none selected
            TestDeviceGroupDevice.objects.filter(group=obj).delete()
    
    def delete_queryset(self, request, queryset):
        """Delete device groups and their relationships"""
        # Relationships will be cascade deleted automatically
        count = queryset.count()
        queryset.delete()
        # self.message_user(
        #     request,
        #     ngettext(
        #         "Successfully deleted %d device group.",
        #         "Successfully deleted %d device groups.",
        #         count
        #     ) % count,
        #     messages.SUCCESS
        # )
    
    def changelist_view(self, request, extra_context=None):
        """Override to add custom title"""
        extra_context = extra_context or {}
        extra_context['title'] = _("Test Device Groups")
        return super().changelist_view(request, extra_context)
    
    def has_delete_permission(self, request, obj=None):
        """Check delete permission"""
        if not super().has_delete_permission(request, obj):
            return False
        # Add any additional checks here if needed
        return True
    
    def get_urls(self):
     """Add custom URLs for AJAX endpoints"""
     urls = super().get_urls()
     custom_urls = [
          path(
               'get-organization-devices/',
               self.admin_site.admin_view(self.get_organization_devices_view),
               name='test_management_testdevicegroup_get_org_devices',
          ),
     ]
     return custom_urls + urls

    def get_organization_devices_view(self, request):
      """Admin view wrapper for getting organization devices"""
      from .views import get_organization_devices
      return get_organization_devices(request)
    
    def get_organization_devices(self, request):
        """AJAX endpoint to get devices for an organization"""
        org_id = request.GET.get('organization_id')
        if not org_id:
            return JsonResponse({'error': 'Organization ID required'}, status=400)
        
        try:
            # Get devices for the organization
            devices = Device.objects.filter(
                organization_id=org_id,
                _is_deactivated=False  # Only active devices
            ).order_by('name')
            
            device_list = []
            for device in devices:
                device_list.append({
                    'id': str(device.id),
                    'name': device.name,
                    'mac_address': device.mac_address,
                    'last_ip': device.last_ip or '-',
                    'model': device.model or '-',
                })
            
            return JsonResponse({'devices': device_list})
            
        except Exception as e:
            logger.error(f"Error fetching organization devices: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    def recover_view(self, request, version_id, extra_context=None):
        extra_context = extra_context or {}
        # extra_context["categories"] = list(TestCategory.objects.values("id", "name"))
        version = self._get_version_object(version_id)

        if version:
            execution_obj = version._object_version.object
            
            # Now get related devices (live DB, not historical)
            related_versions = version.revision.version_set.filter(
            content_type__model="testdevicegroupdevice"
            )

            recovered_device_ids = [str(v._object_version.object.device_id) for v in related_versions]

            # 🔹 Re-use logic from get_available_devices
            devices_query = Device.objects.filter(id__in=recovered_device_ids).select_related("organization")
            devices_data = []
            for device in devices_query:
                is_deactivated = getattr(device, '_is_deactivated', False)
                
                devices_data.append({
                    'id': str(device.id),
                    'name': device.name,
                    'mac_address': getattr(device, 'mac_address', None) or 'N/A',
                    'last_ip': getattr(device, 'last_ip', None) or 'N/A',
                    'model': getattr(device, 'model', None) or 'Unknown',
                    'management_ip': getattr(device, 'management_ip', None) or 'N/A',
                    'is_active': not is_deactivated,
                })
            
            extra_context['recovered_devices_for_group'] = json.dumps(devices_data)

      
        extra_context['show_device_group_devices']= True
        extra_context["is_recover_view"]= True
        return super().recover_view(request, version_id, extra_context=extra_context)
    
    def _get_version_object(self, version_id):
        """
        Utility to fetch the Version object for the given version_id.
        This avoids duplicating queryset logic from reversion's internal code.
        """
        from reversion.models import Version
        try:
            return Version.objects.get(pk=version_id)
        except Version.DoesNotExist:
            return None


# Inline admin for viewing devices in a group (optional)
class TestDeviceGroupDeviceInline(admin.TabularInline):
    model = TestDeviceGroupDevice
    extra = 0
    fields = ['device', 'device_status', 'device_last_ip']
    readonly_fields = ['device_status', 'device_last_ip']
    
    def device_status(self, obj):
        """Show device status"""
        if obj.device._is_deactivated:
            return format_html(
                '<span style="color: #dc3545;">●</span> Inactive'
            )
        return format_html(
            '<span style="color: #28a745;">●</span> Active'
        )
    device_status.short_description = _("Status")
    
    def device_last_ip(self, obj):
        """Show device last IP"""
        return obj.device.last_ip or '-'
    device_last_ip.short_description = _("Last IP")
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False



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


if not reversion.is_registered(TestDeviceGroup):
    reversion.register(TestDeviceGroup)



if not reversion.is_registered(TestDeviceGroupDevice):
    reversion.register(TestDeviceGroupDevice)





