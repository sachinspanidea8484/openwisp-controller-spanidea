import logging

import reversion
from django import forms
from django.conf import settings
from django.utils import timezone
from uuid import UUID
from django.core.exceptions import ValidationError
from django.core.validators import (
    MinLengthValidator,
    MaxLengthValidator
)
from django.contrib.admin.widgets import AdminFileWidget
from django.templatetags.static import static
from django.template.response import TemplateResponse
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.db import transaction
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from reversion.admin import VersionAdmin
import json
from django.urls import path
from django.shortcuts import get_object_or_404, render
import traceback
from django.core.validators import validate_email
import json
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportMixin
from django.core.validators import RegexValidator
from openwisp_controller.config.models import Device
from django.db.models import Prefetch
from reversion.models import Version
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.db.models import Q
import os
import requests
from urllib.parse import urlparse
from rest_framework.authtoken.models import Token

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
from import_export.widgets import Widget
from django.utils.safestring import mark_safe
from .forms import ExecutionArtifactFormSet
from .utils import build_all_testcases_zip
from import_export.exceptions import ImportError

logger = logging.getLogger(__name__)
TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteCase = load_model("TestSuiteCase")
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCaseExecution = load_model("TestCaseExecution")
ExecutionArtifact= load_model("ExecutionArtifact")

TestDeviceGroup = load_model("TestDeviceGroup")
TestDeviceGroupDevice = load_model("TestDeviceGroupDevice")


from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.formats import base_formats
from django.db import models


class ScriptValidationError(ValidationError):
    def __init__(self, message, field=None):
        self.field = field
        super().__init__(message)

class BaseAdmin(TimeReadonlyAdminMixin, admin.ModelAdmin):
    save_on_top = True


class BaseVersionAdmin(TimeReadonlyAdminMixin, VersionAdmin):
    history_latest_first = True
    save_on_top = True
    list_per_page= 10

class TestTypeChoices(models.IntegerChoices):
    ROBOT_FRAMEWORK = 1, _('Robot Framework')
    AGENT = 2, _('Device')

class ChoicesWidget(Widget):
    def __init__(self, choices):
        self.choices = dict(choices)
        self.reverse_choices = {v: k for k, v in self.choices.items()}

    def render(self, value, obj=None, **kwargs):
        """Convert integer to readable text for export"""
        return self.choices.get(value, "")

    def clean(self, value, row=None, **kwargs):
        """Convert readable text to integer for import"""
        return self.reverse_choices.get(value, None)

def extract_description_from_python(content: bytes) -> str | None:
    START_MARKER = "# START_DESCRIPTION"
    END_MARKER = "# END_DESCRIPTION"

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None

    start = text.find(START_MARKER)
    end = text.find(END_MARKER)

    if start == -1 or end == -1 or end <= start:
        return None

    extracted = text[start + len(START_MARKER):end].strip()

    lines = extracted.splitlines()
    cleaned_lines = []

    for line in lines:
        # Remove leading "#" and spaces
        cleaned = line.lstrip().lstrip("#").strip()
        if cleaned:
            cleaned_lines.append(cleaned)

    return "\n".join(cleaned_lines) if cleaned_lines else None


def _update_robot_content(content: bytes, test_case_id: str) -> bytes:
    import re

    text = content.decode("utf-8")

    # ----------------------------
    # STEP 1: Update [Tags]
    # ----------------------------
    existing_tag_pattern = r'^(\s*\[Tags\]\s+)(\S+)(\s+.*)?$'
    empty_tag_pattern = r'^\s*\[Tags\]\s*$'

    if re.search(existing_tag_pattern, text, re.MULTILINE):
        
        text = re.sub(
            existing_tag_pattern,
            rf'\1{test_case_id}\3',
            text,
            count=1,
            flags=re.MULTILINE,
        )
    elif re.search(empty_tag_pattern, text, re.MULTILINE):
        
        text = re.sub(
            empty_tag_pattern,
            rf'[Tags]    {test_case_id}',
            text,
            count=1,
            flags=re.MULTILINE,
        )

    # ----------------------------
    # STEP 2: Update Library path (FIRST only)
    # ----------------------------
    # library_pattern = r'(Library\s+\.\./\.\./resources/keywords/)([A-Za-z0-9_\-]+)(\.py)' v1
    library_pattern = r'(Library\s+(?:\.\./)+resources/keywords/)([A-Za-z0-9_\-]+)(\.py)'
    match = re.search(library_pattern, text)

    if match:
        old_name = match.group(2)
        if old_name != test_case_id:
            text = (
                text[:match.start()]
                + f"{match.group(1)}{test_case_id}{match.group(3)}"
                + text[match.end():]
            )

    return text.encode("utf-8")

def validate_python_import(content : bytes):
    import ast

    text = content.decode("utf-8", errors="strict")

    if not text.strip():
        raise ScriptValidationError("Python file is empty", field="python_script")

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise ScriptValidationError(
            f"Syntax error at line {e.lineno}: {e.msg}",
            field="python_script"
        )

    has_defs = any(
        isinstance(n, (ast.FunctionDef, ast.ClassDef))
        for n in ast.walk(tree)
    )

    if not has_defs:
        raise ScriptValidationError(
            "No function or class found in Python file",
            field="python_script"
        )

    compile(text, "<imported_script>", "exec")

        
        
             
def validate_robot_import(file_path):
    from robot.parsing import get_model

    try:
        model = get_model(file_path)
    except Exception as e:
        raise ScriptValidationError(
            f"Robot parsing failed: {e}",
            field="robot_script"
        )

    if not model.sections:
        raise ScriptValidationError(
            "Robot file has no sections",
            field="robot_script"
        )

    for section in model.sections:
        if "Test Cases" in str(section.header.data_tokens):
            return

    raise ScriptValidationError(
        "Missing *** Test Cases *** section",
        field="robot_script"
    )

def _get_system_script_path(test_case_id, script_type, test_type):
    if test_type=="Robot Framework" and script_type=="python":
        return os.path.join(settings.MEDIA_ROOT, "test_case_robot", f"{test_case_id}.py")
    elif script_type == "robot":
        return os.path.join(settings.MEDIA_ROOT, "test_case_robot", f"{test_case_id}.robot")
    return os.path.join(settings.MEDIA_ROOT, "test_case", f"{test_case_id}.py")

def store_script(
    source,
    *,
    test_case_id,
    script_type,  # "robot" | "python"
    extract_description=False,
    system_generated=False,
    test_type,
):
    """
    Stores script in a deterministic location with deterministic filename.

    Handles:
    - External URLs
    - Server-hosted URLs
    - Relative MEDIA paths
    """
    if system_generated:
        system_path = _get_system_script_path(test_case_id, script_type, test_type)
        
        if not os.path.exists(system_path):
            raise ScriptValidationError(
                f"System {script_type} script not found at '{system_path}'",
                field= "robot_script" if script_type =="robot" else "python_script"
            )

        with open(system_path, "rb") as f:
            content = f.read()

        extracted_description = None

        if script_type == "python":
            validate_python_import(content)
            if extract_description:
                extracted_description = extract_description_from_python(content)

        # DO NOT rewrite
        relative_path = os.path.relpath(system_path, settings.MEDIA_ROOT)

        return relative_path, extracted_description
    
    if not source:
        return None, None

    if script_type not in ("robot", "python"):
        raise ValueError("script_type must be 'robot' or 'python'")

    # Target path
    if script_type == "robot":
        subdir = "test_case_robot"
        ext = ".robot"
    elif script_type == "python" and test_type=="Robot Framework":
        subdir = "test_case_robot"
        ext = ".py"
    else:
        subdir = "test_case"
        ext = ".py"

    filename = f"{test_case_id}{ext}"
    relative_path = os.path.join(subdir, filename)
    dest_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    source = str(source).strip()

    site_url = str(getattr(settings, "OPENWISP_SERVER_IP", "")).rstrip("/")
    media_url = str(settings.MEDIA_URL).rstrip("/")

    content = None

    # --------------------------------------------------
    #  1 External URL : download
    # --------------------------------------------------
    if source.startswith("http"):
        parsed = urlparse(source)

        # Hosted on our server
        if site_url and source.startswith(site_url):
            src_path = parsed.path
            if src_path.startswith(media_url):
                src_path = src_path[len(media_url):].lstrip("/")
            src_full = os.path.join(settings.MEDIA_ROOT, src_path)
            if not os.path.exists(src_full):
                raise ValidationError(
                    f" File does not exist at '{source}'"
                )
            with open(src_full, "rb") as f:
                content = f.read()
        else:
            try:
                response = requests.get(source, timeout=15)
                response.raise_for_status()
                content = response.content
            except requests.RequestException as e:
                raise ValidationError(
                    f"Failed to download script ({e})"
                )
    # --------------------------------------------------
    # 2 Relative path : read content
    # --------------------------------------------------
    else:
        src_full = os.path.join(settings.MEDIA_ROOT, source.lstrip("/"))
        if not os.path.exists(src_full):
            raise ValidationError(
                f" File does not exist at '{source}'"
            )

        if not os.path.isfile(src_full):
            raise ValidationError(
                f"Path is not a file '{source}'"
            )
        with open(src_full, "rb") as f:
            content = f.read()

    # update tag and python file path in robot files
    if script_type == "robot":
        content = _update_robot_content(content, test_case_id)

    extracted_description = None
    #update description of test case from py file ONLY if it is not present
    if script_type == "python" :
        validate_python_import(content)
    if script_type == "python" and extract_description:
        extracted_description = extract_description_from_python(content)
   
    # --------------------------------------------------
    # 3 ALWAYS rewrite destination 
    # --------------------------------------------------
    with open(dest_path, "wb") as f:
        f.write(content)
    
    if script_type == "robot":
        validate_robot_import(dest_path) 

    return relative_path, extracted_description

class TestCasesResource(resources.ModelResource):

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    category= fields.Field(
        column_name="category_name",
        attribute="category",
        widget=ForeignKeyWidget(TestCategory,"name")
    )
    test_type = fields.Field(
        column_name="test_type",
        attribute="test_type",
        widget=ChoicesWidget(TestTypeChoices.choices),
    )
    is_configuration_push_required = fields.Field(
        column_name="is_file_required",
        attribute="is_configuration_push_required",
    )
    robot_script = fields.Field(column_name="robot_script", attribute="robot_script")
    python_script = fields.Field(column_name="python_script", attribute="python_script")
    class Meta:
        model = TestCase
        fields = (
            "id",
            "name",
            "test_case_id",
            "category",
            "description",
            "is_active",
            "test_type",
            "params",
            "is_configuration_push_required",
            "robot_script",
            "python_script",
            # "is_system_test_case"
            # "file"
        )
        export_order = (
            "id",
            "name",
            "test_case_id",
            "category",
            "description",
            "is_active",
            "test_type",
            "params",
            "is_configuration_push_required",
            "robot_script",
            "python_script",
            # "is_system_test_case",
        )
    
   
    
    def _build_file_url(self, value):
        if not value:
            return ""

        site_url = str(
            getattr(settings, "OPENWISP_SERVER_IP", "")
        ).rstrip("/")

        media_url = str(settings.MEDIA_URL).rstrip("/")
        return f"{site_url}{media_url}/{value}"

    def dehydrate_robot_script(self, obj):
        return self._build_file_url(obj.robot_script)

    def dehydrate_python_script(self, obj):
        return self._build_file_url(obj.python_script)

    def before_import_row(self, row, **kwargs):
        """
        Ensure category exists before import.
        - If category_name is missing -> use default.
        - If category_name is given but doesn't exist -> create it.
        """
        category_name = row.get("category_name")

        if not category_name or str(category_name).strip() == "":
            category_name = "Default Category"
            row["category_name"] = category_name  # ensure widget never sees ""

        # Ensure the category exists (create if missing)
        TestCategory.objects.get_or_create(
            name=category_name,
            defaults={
                "code": category_name.lower().replace(" ", "_"),
                "description": f"Auto-created category '{category_name}'",
            },
        )

        if row.get('description') is None:
            row['description'] = ''
        
        test_case_id = row.get("test_case_id")
        test_type_from_file = row.get("test_type")
        test_type_mapping= {"Device" : 2 , "Robot Framework": 1}
        pk= row.get("id")
        system_generated=False
        if pk:
            existing_testcase_data = TestCase.objects.get(id= pk)
            if not existing_testcase_data:
                raise ScriptValidationError(
                        f"No test case found with id", field="test_case_id"
                    )
            system_generated= existing_testcase_data.is_system_test_case

            if test_case_id != existing_testcase_data.test_case_id:
                raise ScriptValidationError(
                        f"User cannot change test case id", field="test_case_id"
                    )
            if test_type_mapping[test_type_from_file] != existing_testcase_data.test_type:
                raise ScriptValidationError(
                        f"User cannot change test type", field="test_case_id"
                    )
            if existing_testcase_data.is_system_test_case:
                if not self.user or not self.user.is_superuser:
                    raise ScriptValidationError(
                        f"Non-superuser cannot import system test case: {test_case_id}", field="test_case_id"
                    )
            if self.user != existing_testcase_data.created_by:
                if not self.user or not self.user.is_superuser:
                    raise ScriptValidationError(
                        f"User doesn't have permission to edit the testcase: {test_case_id}", field="test_case_id"
                    )
                
        if test_type_from_file == "Device":
            row["robot_script"]= None
        else:
            row["robot_script"] , extracted_description = store_script(
                row.get("robot_script"),
                test_case_id=test_case_id,
                script_type="robot",
                system_generated= system_generated,
                test_type= test_type_from_file,
            )
            if not row["robot_script"]:
                raise ScriptValidationError("Robot script is missing", field="robot_script")
        python_path, extracted_description = store_script(
            row.get("python_script"),
            test_case_id=test_case_id,
            script_type="python",
            extract_description=True,
            system_generated= system_generated,
            test_type= test_type_from_file,
        )
        if not python_path:
                raise ScriptValidationError("python script is missing", field="python_script")
        row["python_script"] = python_path

        if(not row.get("description")) and extracted_description : 
            row["description"]= extracted_description


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
        "code",    # code visible only in Add/Edit form
        "description",
        "related_testcases"
    ]
    readonly_fields = ["created", "modified", "related_testcases"]
    
    # Enable history button
    object_history_template = "reversion/object_history.html"
    
    actions = ["delete_selected", "recover_deleted"]
    

    def related_testcases(self, obj):
        # return "test"
        testcases= obj.test_cases.all()
        if not testcases.exists():
            return "No test case assigned."
        html = """
        <style>
            .field-related_testcases .readonly{
                width: 90%;
            }
            .related-testcases-table th,td{
                width: 30%;
            }
        </style>
        <table class="related-testcases-table" style="width:90%">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Test Case ID</th>
                    <th>Type</th>
                </tr>
            </thead>
            <tbody>
        """

        for tc in testcases:
            html += f"""
            <tr>
                <td class="readonly-name-col">
                    <div class="readonly-test-case-name">{tc.name}</div>
                </td>
                <td class="readonly-id-col">
                    <div class="readonly-test-case-id">{tc.test_case_id}</div>
                </td>
                <td class="readonly-type-col">
                    <span class="readonly-test-type-badge">{tc.get_test_type_display()}</span>
                </td>
            </tr>
            """

        html += "</tbody></table>"

        return mark_safe(html)
    related_testcases.short_description = "Related Test Cases"

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
        print("=" * 50)
        print("DEBUG: FormattedJSONField.prepare_value()")
        print(f"Input value type: {type(value)}")
        print(f"Input value: {repr(value)}")
        
        if value is None or value == '':
            print("Returning empty string")
            return ''
        
        try:
            # Handle dict
            if isinstance(value, dict):
                parsed = value
                print(f"Value is dict: {parsed}")
            # Handle string
            elif isinstance(value, str):
                value = value.strip()
                if not value or value == '{}':
                    print("Empty string or empty object")
                    return ''
                parsed = json.loads(value)
                print(f"Parsed from string: {parsed}")
            else:
                print(f"Unexpected type, returning as-is: {type(value)}")
                return value
            
            # Format with proper indentation
            formatted = json.dumps(parsed, indent=4, ensure_ascii=False, sort_keys=True)
            print(f"Formatted output:\n{formatted}")
            return formatted
            
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error formatting JSON: {e}")
            print(f"Returning original value")
            return value
        finally:
            print("=" * 50)

    def to_python(self, value):
        """Convert widget value to Python object"""
        print("=" * 50)
        print("DEBUG: FormattedJSONField.to_python()")
        print(f"Input: {repr(value)}")
        
        if value in (None, '', '{}'):
            print("Returning empty dict")
            result = {}
        elif isinstance(value, dict):
            print("Already a dict")
            result = value
        else:
            print(f"Returning string for validation: {repr(value)}")
            result = value  # Return as string for clean_params to handle
        
        print(f"Output: {repr(result)}")
        print("=" * 50)
        return result
    
allowed_test_case_id = RegexValidator(
    regex=r'^[A-Za-z0-9_\-.:/]+$',
    message=_("Only letters, numbers, underscores (_), hyphens (-), dots (.), colons (:), and slashes (/) are allowed.")
)

class TestCaseAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'description' in self.fields:
            self.fields['description'].widget.attrs.update({'rows': 15, 'cols': 5})

    test_case_id = forms.CharField(
        validators=[
            RegexValidator(
                regex=r'^[A-Za-z][A-Za-z0-9_\-.:/]*$',
                message=_(
                    "Test Case ID must start with a letter and contain only "
                    "letters, numbers, _, -, ., :, /"
                )
            ),
            MinLengthValidator(3, message=_("Test Case ID must be at least 3 characters long.")),
            MaxLengthValidator(20, message=_("Test Case ID must not exceed 20 characters."))
        ],
        widget=forms.TextInput(attrs={
            'pattern': r'[A-Za-z][A-Za-z0-9_\-.:/]{2,19}',
            'title': _("Example: TC-001, LOGIN-TC-01, API:TC:01"),
            'placeholder': _('Enter Test Case ID')
        })
    )

    params = FormattedJSONField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 15,
            'cols': 67,
            'placeholder': _('Enter Parameters in JSON format (e.g., {"key": "value"})'),
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
        widgets = {
            'robot_script': forms.ClearableFileInput(attrs={'accept': '.robot'}),
            'python_script': forms.ClearableFileInput(attrs={'accept': '.py'}),
        }

    def clean_test_case_id(self):
        test_case_id = self.cleaned_data.get("test_case_id")

        if not test_case_id:
            return test_case_id

        qs = TestCase.objects.filter(test_case_id=test_case_id)

        # Exclude current object during edit
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(
                _("Test Case ID '%(id)s' already exists. Please use a unique ID."),
                params={"id": test_case_id},
            )

        if test_case_id in ["Device", "Robot"]:
            raise forms.ValidationError(
                _("'%(id)s' is not a valid test case id."),
                params={"id": test_case_id},
            )
        return test_case_id
    

    def extract_tag_from_robot_file(self, robot_file):
        """Extract test case ID from [Tags] line, returns None if empty"""
        try:
            if hasattr(robot_file, 'read'):
                robot_file.seek(0)
                content = robot_file.read().decode('utf-8')
                robot_file.seek(0)
            else:
                content = robot_file
            
            import re
            # Match [Tags] line (with or without content)
            tag_pattern = r'\[Tags\]\s*(.*)$'
            match = re.search(tag_pattern, content, re.MULTILINE)
            
            if match:
                tag_content = match.group(1).strip()
                if tag_content:
                    # Return only first word/ID
                    return tag_content.split()[0]
                else:
                    # [Tags] exists but empty
                    return None
            return None  # No [Tags] found
        except Exception as e:
            return None
    
    def update_robot_file_tag(self, robot_file, new_test_case_id):
        """
        Update [Tags] AND Library path in robot file
        """
        try:
            if hasattr(robot_file, 'read'):
                robot_file.seek(0)
                content = robot_file.read().decode('utf-8')
            else:
                with open(robot_file.path, 'r') as f:
                    content = f.read()
            
            import re
            
            # STEP 1: Update [Tags]
            existing_tag_pattern = r'(\[Tags\]\s+)([A-Za-z0-9_\-.:/]+)(.*?)$'
            empty_tag_pattern = r'(\[Tags\])\s*$'
            
            if re.search(existing_tag_pattern, content, re.MULTILINE):
                content = re.sub(
                    existing_tag_pattern,
                    rf'\1{new_test_case_id}\3',
                    content,
                    count=1,
                    flags=re.MULTILINE
                )
            elif re.search(empty_tag_pattern, content, re.MULTILINE):
                content = re.sub(
                    empty_tag_pattern,
                    rf'\1    {new_test_case_id}',
                    content,
                    count=1,
                    flags=re.MULTILINE
                )
            
            # STEP 2: Update Library path (FIRST occurrence only)
            # library_pattern = r'(Library\s+\.\./\.\./resources/keywords/)([A-Za-z0-9_\-]+)(\.py)' v1
            library_pattern = r'(Library\s+(?:\.\./)+resources/keywords/)([A-Za-z0-9_\-]+)(\.py)'
            matches = list(re.finditer(library_pattern, content))
            
            if matches:
                first_match = matches[0]
                old_filename = first_match.group(2)
                
                # Only replace if it's different
                if old_filename != new_test_case_id:
                    content = content[:first_match.start()] + \
                            f'{first_match.group(1)}{new_test_case_id}{first_match.group(3)}' + \
                            content[first_match.end():]
            
            # Create updated file
            from io import BytesIO
            from django.core.files.uploadedfile import InMemoryUploadedFile
            
            file_io = BytesIO(content.encode('utf-8'))
            updated_file = InMemoryUploadedFile(
                file_io,
                'robot_script',
                robot_file.name if hasattr(robot_file, 'name') else 'updated.robot',
                'text/plain',
                len(content.encode('utf-8')),
                None
            )
            return updated_file
            
        except Exception as e:
            raise forms.ValidationError(_(f"Error updating robot file: {str(e)}"))
    def update_python_library_path_in_robot(self, robot_file, test_case_id):
        """
        Replace ../../resources/keywords/<any_name>.py with ../../resources/keywords/<test_case_id>.py
        - Only replaces the FIRST occurrence
        - Skips connection_manager.py or any file NOT directly in keywords/
        - Handles edge cases safely
        """
        try:
            if hasattr(robot_file, 'read'):
                robot_file.seek(0)
                content = robot_file.read().decode('utf-8')
            else:
                with open(robot_file.path, 'r') as f:
                    content = f.read()
            
            import re
            
            # Pattern to match: Library    ../../resources/keywords/<filename>.py
            # BUT NOT: Library    ../../resources/keywords/execution/connection_manager.py
            pattern = r'(Library\s+\.\./\.\./resources/keywords/)([a-zA-Z0-9_\-]+)(\.py)'
            
            # Find all matches
            matches = list(re.finditer(pattern, content))
            
            if not matches:
                # No matching library found, return original
                return robot_file
            
            # Get the first match
            first_match = matches[0]
            old_filename = first_match.group(2)
            
            # Skip if it's already the test case ID
            if old_filename == test_case_id:
                return robot_file
            
            # Replace ONLY the first occurrence
            updated_content = content[:first_match.start()] + \
                            f'{first_match.group(1)}{test_case_id}{first_match.group(3)}' + \
                            content[first_match.end():]
            
            # Create updated file
            from io import BytesIO
            from django.core.files.uploadedfile import InMemoryUploadedFile
            
            file_io = BytesIO(updated_content.encode('utf-8'))
            updated_file = InMemoryUploadedFile(
                file_io,
                'robot_script',
                robot_file.name if hasattr(robot_file, 'name') else 'updated.robot',
                'text/plain',
                len(updated_content.encode('utf-8')),
                None
            )
            return updated_file
            
        except Exception as e:
            raise forms.ValidationError(_(f"Error updating library path: {str(e)}"))
    

    def validate_robot_file_syntax(self, robot_file):
        """
        STANDARD WAY: Validate robot file using robot.parsing
        Falls back to basic validation if robot library not available
        """
        try:
            MAX_ROBOT_FILE_SIZE = 1000 * 1024  # 1000 KB

            if robot_file.size > MAX_ROBOT_FILE_SIZE:
                       return False, "Robot file is too large (max 1MB allowed).", "robot_framework"



            robot_file.seek(0)

            if hasattr(robot_file, 'read'):
                robot_file.seek(0)
                content = robot_file.read().decode('utf-8')
                robot_file.seek(0)
            else:
                with open(robot_file.path, 'r') as f:
                    content = f.read()
            
            # METHOD 1: Use robot.parsing (Most Standard)
            try:
                from robot.parsing import get_model
                import tempfile
                import os
                validation_method = "robot_framework"
                
                # Create temporary file (robot library needs actual file)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.robot', delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                
                try:
                    # Parse the robot file
                    model = get_model(tmp_path)
                    
                    # Detailed validation
                    errors = []
                    
                    # Check for test cases
                    if not model.sections:
                        errors.append("No sections found in robot file")
                    
                    has_test_cases = False
                    for section in model.sections:
                        if hasattr(section, 'header') and section.header:
                            if 'Test Cases' in str(section.header.data_tokens):
                                has_test_cases = True
                                break
                    
                    if not has_test_cases:
                        errors.append("No '*** Test Cases ***' section found")
                    
                    if errors:
                        return False, "; ".join(errors), validation_method
                    
                    return True, None, validation_method

                    
                finally:
                    # Clean up temp file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                        
            except ImportError:
                # METHOD 2: Fallback - Basic regex validation
                is_valid, error, _ = self._basic_robot_validation(content)
                return is_valid, error, "fallback_regex"
                
        except Exception as e:
            return False, f"Error validating robot file: {str(e)}" ,"robot_framework"
    
    def _basic_robot_validation(self, content):
        """Fallback validation when robot library not available"""
        import re
        errors = []
        
        # Check for required sections
        required_sections = [
            r'\*\*\* Test Cases \*\*\*',
            r'\[Tags\]'
        ]
        
        if not re.search(required_sections[0], content):
            errors.append("Missing '*** Test Cases ***' section")
        
        if not re.search(required_sections[1], content):
            errors.append("Missing '[Tags]' in test case")
        
        # Check for basic syntax errors
        if '***' in content:
            # Validate section headers
            section_pattern = r'\*\*\* \w+( \w+)* \*\*\*'
            invalid_sections = re.findall(r'\*\*\*[^\*]+\*\*\*', content)
            for section in invalid_sections:
                if not re.match(section_pattern, section):
                    errors.append(f"Invalid section header: {section}")
        
        return len(errors) == 0, "; ".join(errors) if errors else None, "fallback_regex"

    
    def validate_python_file_syntax(self, python_file):
        """
        STANDARD WAY: Validate Python file using ast and compile
        """
        try:
            MAX_PYTHON_FILE_SIZE = 1000 * 1024  # 1000 KB

            if python_file.size > MAX_PYTHON_FILE_SIZE:
                        return False, "Python file too large (max 1MB allowed).", "python_ast"




            if hasattr(python_file, 'read'):
                python_file.seek(0)
                content = python_file.read().decode('utf-8')
                python_file.seek(0)
            else:
                with open(python_file.path, 'r') as f:
                    content = f.read()
            
            # METHOD 1: AST parsing (catches syntax errors)
            import ast
            try:
                tree = ast.parse(content)
                
                # METHOD 2: Additional validation - check for common issues
                errors = []
                
                validation_method = "python_ast"

                # Check if file is not empty
                if not content.strip():
                    errors.append("Python file is empty")
                
                # Check for basic Python structure
                if not any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in ast.walk(tree)):
                    errors.append("No functions or classes found - file may be incomplete")
                
                if errors:
                    return False, "; ".join(errors), validation_method
                
                # METHOD 3: Try to compile (catches more subtle errors)
                compile(content, '<string>', 'exec')

                
                return True, None,validation_method
                
            except SyntaxError as e:
                error_msg = f"Syntax Error at line {e.lineno}: {e.msg}"
                if e.text:
                    error_msg += f"\n  Code: {e.text.strip()}"
                    if e.offset:
                        error_msg += f"\n  " + " " * (e.offset - 1) + "^"
                return False, error_msg, "python_ast"

            
            except Exception as e:
                return False, f"Error validating Python file: {str(e)}" ,"python_ast"
                
        except Exception as e:
            return False, f"Error validating Python file: {str(e)}" ,"python_ast"

    def get_system_python_script(self, test_case_id, test_type):
        rel_path=  f"test_case_robot/{test_case_id}.py" if test_type== TestTypeChoices.ROBOT_FRAMEWORK else f"test_case/{test_case_id}.py"
        abs_path= os.path.join(settings.MEDIA_ROOT, rel_path)
        if not os.path.exists(abs_path):
            raise forms.ValidationError(
                _("System Python script not found for the given test case with id '%(id)s' "),
                params={"id": test_case_id},
            )
        return rel_path

    def get_system_robot_script(self, test_case_id):
        rel_path= f"test_case_robot/{test_case_id}.robot"
        abs_path= os.path.join(settings.MEDIA_ROOT, rel_path)
        if not os.path.exists(abs_path):
            raise forms.ValidationError(
                _("System Robot Framework script not found for the given test case with id '%(id)s' "),
                params={"id": test_case_id},
            )
        return rel_path
        
    
    def clean(self):
        cleaned_data = super().clean()
        test_type = cleaned_data.get("test_type")
        python_script = cleaned_data.get("python_script")
        robot_script = cleaned_data.get("robot_script")
        test_case_id = cleaned_data.get("test_case_id")
        is_system_test_case = cleaned_data.get("is_system_test_case")
        is_superuser= self.request.user.is_superuser

        # Validate Python script
        if python_script:
            if not python_script.name.endswith(".py"):
                self.add_error("python_script", "Only .py files allowed.")
            else:
                is_valid, error_msg, _ = self.validate_python_file_syntax(python_script)
                if not is_valid:
                    self.add_error(
                        "python_script",
                        f"Python validation failed:\n{error_msg}"
                    )
        elif is_superuser and test_case_id and is_system_test_case:
            cleaned_data["python_script"]= self.get_system_python_script(test_case_id, test_type)
        else:
            self.add_error("python_script", "Python Script is Required.")
        
        # Robot Framework validation
        if test_type == TestTypeChoices.ROBOT_FRAMEWORK:
            if not robot_script:
                if is_superuser and test_case_id and is_system_test_case:
                    cleaned_data["robot_script"]= self.get_system_robot_script(test_case_id)
                else:
                    self.add_error("robot_script", "Robot Script is Required for Robot Framework.")
            elif not robot_script.name.endswith(".robot"):
                self.add_error("robot_script", "Only .robot files allowed.")
            else:
                # Validate robot file syntax FIRST
                is_valid, error_msg ,method = self.validate_robot_file_syntax(robot_script)
                if not is_valid:
                  self.add_error("robot_script", f"[{method}] {error_msg}")

                else:
                    # Check for [Tags] line
                    import re
                    robot_script.seek(0)
                    content = robot_script.read().decode('utf-8')
                    robot_script.seek(0)
                    
                    if not re.search(r'\[Tags\]', content):
                        self.add_error(
                            "robot_script",
                            "Robot file must contain a [Tags] line in test case. "
                            "Example:\n    [Tags]    TEST_ID"
                        )
                    else:
                        # Extract existing tag
                        extracted_tag = self.extract_tag_from_robot_file(robot_script)
                        
                        # **MAIN LOGIC: Add or Update Tag**
                        if not self.instance.pk:  # NEW test case
                            if test_case_id:
                                # User entered ID, add/update it in robot file
                                cleaned_data['robot_script'] = self.update_robot_file_tag(
                                    robot_script, test_case_id
                                )
                            elif extracted_tag:
                                # No user ID, use robot file's tag
                                cleaned_data['test_case_id'] = extracted_tag
                            else:
                                # Both empty
                                self.add_error(
                                    "test_case_id",
                                    "Please enter a Test Case ID"
                                )
                        else:  # EDIT existing test case
                            if test_case_id != self.instance.test_case_id:
                                # User changed ID, update robot file
                                cleaned_data['robot_script'] = self.update_robot_file_tag(
                                    robot_script, test_case_id
                                )
                            elif extracted_tag and extracted_tag != test_case_id:
                                # Robot file changed but ID different, sync it
                                cleaned_data['robot_script'] = self.update_robot_file_tag(
                                    robot_script, test_case_id
                                )
                            elif not extracted_tag:
                                # Robot file has empty [Tags], add current ID
                                cleaned_data['robot_script'] = self.update_robot_file_tag(
                                    robot_script, test_case_id
                                )
        
        elif test_type == TestTypeChoices.AGENT:
            self.instance.robot_script = None
            cleaned_data["robot_script"] = None
        
        return cleaned_data
    def clean_params(self):
        """Validate params field - must be valid JSON dict or empty"""
        params = self.cleaned_data.get('params', '')
        
        print("=" * 50)
        print("DEBUG: clean_params() started")
        print(f"Raw params type: {type(params)}")
        print(f"Raw params value: {repr(params)}")
        print("=" * 50)
        
        # Handle empty values
        if params in (None, '', '{}', {}):
            print("Params is empty - returning empty dict")
            return {}
        
        # If already a dict (shouldn't happen but handle it)
        if isinstance(params, dict):
            print(f"Params is already a dict: {params}")
            return params
        
        # Must be string at this point
        if not isinstance(params, str):
            print(f"Params is not a string, it's: {type(params)}")
            raise ValidationError(
                _("Parameters must be a valid JSON object.")
            )
        
        # Clean whitespace
        params = params.strip()
        print(f"Trimmed params: {repr(params)}")
        
        if not params:
            print("Params is empty after trim - returning empty dict")
            return {}
        
        # Try to parse JSON
        try:
            parsed = json.loads(params)
            print(f"JSON parsed successfully: {parsed}")
            print(f"Parsed type: {type(parsed)}")
            
            # Must be a dictionary (object), not array or primitive
            if not isinstance(parsed, dict):
                print(f"Parsed JSON is not a dict, it's: {type(parsed)}")
                raise ValidationError(
                    _("Parameters must be a JSON object (key-value pairs), not an array or primitive value. "
                      "Example: {\"username\": \"admin\", \"timeout\": 30}")
                )
            
            print(f"Final validated params: {parsed}")
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}")
            print(f"Error at position {e.pos}: {e.msg}")
            raise ValidationError(
                _(f"Invalid JSON format: {e.msg} at position {e.pos}. "
                  f"Please enter valid JSON like: {{\"key\": \"value\"}}")
            )
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise ValidationError(
                _(f"Error validating parameters: {str(e)}")
            )
        
class ForceDownloadFileWidget(AdminFileWidget):
    def __init__(self, attrs=None):
        super().__init__(attrs=attrs)

    def render(self, name, value, attrs=None, renderer=None):
        html = super().render(name, value, attrs, renderer)

        if value:
            # Safely add download attribute without breaking markup
            html = html.replace(
                '<a href="', '<a download href="', 1
            )

        return mark_safe(html)
    
# @admin.register(TestCase)
class TestCaseAdmin(BaseVersionAdmin):
    form = TestCaseAdminForm
    list_display = [
        "name_with_tooltip",              # 1st - Test Case Name
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
        # "is_system_test_case",
        "robot_script",
        "python_script",
        "params",  # ADD THIS - NEW FIELD
        "json_file",
        "description",
        "is_active",
        "is_configuration_push_required"
    ]
    readonly_fields = ["created", "modified","test_script_guidelines"]
    autocomplete_fields = ["category"]
    
    # Enable history button
    object_history_template = "reversion/object_history.html"
    change_list_template = 'admin/test_management/import_export/testcase/change_list.html'
    actions = ["delete_selected", "recover_deleted", "activate_cases", "deactivate_cases"]

    def get_readonly_fields(self, request, obj=None):
        # obj is None when adding, and not None when editing
        if obj:
            return self.readonly_fields + ["test_type" , "test_case_id", "is_system_test_case"]
        return self.readonly_fields
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs
        # Superusers see everything
        if request.user.is_superuser:
            return qs

        # Normal users see only their own test cases
        return qs.filter( Q(created_by=request.user) | Q(is_system_test_case=True)) 
    
    def python_script_download(self, obj):
        if obj and obj.python_script:
            name = os.path.basename(obj.python_script.name)
            return format_html('<a href="{}" download>{}</a>', obj.python_script.url, name)
        return "-"

    python_script_download.short_description = "Python Script"


    def robot_script_download(self, obj):
        if obj and obj.robot_script:
            name = os.path.basename(obj.robot_script.name)
            return format_html('<a href="{}" download>{}</a>', obj.robot_script.url, name)
        return "-"

    robot_script_download.short_description = "Robot Script"

    def has_view_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        if obj is None:
            # Allow access to the change list page
            return True

        if request.user.is_superuser:
            return True

        # Only owner can modify
        return obj.created_by == request.user

        # if obj and not request.user.is_superuser:
        #     return obj.created_by == request.user
        # return super().has_change_permission(request, obj)
    
    def name_with_tooltip(self,obj):
        tooltip_text= obj.description or "No description available"

        return format_html(
            '<span title="{}" style="cursor:help;">{}</span>',
            tooltip_text,
            obj.name
        )
    name_with_tooltip.short_description= "name"
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


    def test_script_guidelines(self, obj=None):
        url = static("guidelines/test_script_guidelines.docx")
        return format_html(
            '<a href="{}" download class="">Download Test Script Guidelines</a>',
            url
        )

    test_script_guidelines.short_description = "Guidelines"

    def get_fieldsets(self, request, obj=None):
        guidelines_url = static("guidelines/test_script_guidelines.docx")

        robot_field = "robot_script"
        python_field = "python_script"

        if obj and not self.has_change_permission(request, obj):
            robot_field = "robot_script_download"
            python_field = "python_script_download"

        base_fields = [
            "category",
            "name",
            "test_case_id",
            "test_type",
        ]

        fieldsets = [
            (
                None,
                {"fields": tuple(base_fields)},
            ),
            (
                format_html(
                    '<div style="display:flex; justify-content:space-between; align-items:center;">'
                    '<span>{}</span>'
                    '<a href="{}" download class="guidelines-link">'
                    'Download Test Script Guidelines'
                    '</a>'
                    '</div>',
                    _("Test Scripts"),
                    guidelines_url,
                ),
                {
                    "fields": (
                        robot_field,
                        python_field,
                    ),
                },
            ),
            (
                _("Additional Details"),
                {
                    "fields": (
                        "params",
                        "json_file",
                        "description",
                        "is_active",
                        "is_configuration_push_required",
                    ),
                },
            ),
        ]

        return fieldsets


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
        if obj is None:
            return True

        if request.user.is_superuser:
            return True

        # Only owner can delete and only if deletable
        return obj.created_by == request.user and obj.is_deletable
        # if obj and not request.user.is_superuser:
        #     return obj.created_by == request.user and obj.is_deletable
        # return super().has_delete_permission(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.request= request
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

        for field_name, accept in (
            ("python_script", ".py"),
            ("robot_script", ".robot"),
        ):
            if field_name in form.base_fields:
                form.base_fields[field_name].widget = ForceDownloadFileWidget(
                    attrs={"accept": accept}
                )

        return form


    
    def save_model(self, request, obj, form, change):
        """Override save to ensure robot file is synced before saving"""
        # Save the object first
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        
        # If robot file exists and needs update, it's already handled in form.clean()
        # This is just a safety hook for future enhancements
        if obj.test_type == TestTypeChoices.ROBOT_FRAMEWORK and obj.robot_script:
            # Log the synchronization for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Test case {obj.test_case_id} saved with robot script")

    class Media:
        js = ('test-management/js/json_file_handler.js', 'test-management/js/testcase_toggle_scripts.js',  'test-management/js/testcase_id_check.js','https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',)  # Add custom JavaScript
        css = {
            'all': ('test-management/css/json_file_handler.css','test-management/css/testcase_admin.css',)  # Optional custom CSS
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
        restricted_test_case= [obj for obj in queryset if obj.created_by != request.user and not request.user.is_superuser ]
        if restricted_test_case:
            msg = _("User doesn't have permission to delete test case(s): %s") % (
                ", ".join([str(obj) for obj in restricted_test_case])
            )
            self.message_user(request, msg, messages.ERROR)
            return
        
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

    
from django.shortcuts import redirect
from django.urls import reverse

    
class TestCasesExportable(ImportExportMixin, TestCaseAdmin):
    resource_class= TestCasesResource
    actions = TestCaseAdmin.actions + ["export_selected_redirect" ]

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        return {"user": request.user}
    
    def export_selected_redirect(self, request, queryset):
        """
            this function help to navigate to export page from actions
        """
        if not queryset.exists():
            self.message_user(request, "No test cases selected.", level=messages.WARNING)
            return
        
        # make a single key for current session and store ids in it
        key = f"export_ids_{self.model._meta.label_lower}"
        request.session[key] = [str(pk) for pk in queryset.values_list("pk", flat=True)]

        opts = self.model._meta
        export_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_export",
            current_app=self.admin_site.name,
        )
        # redirect to the export URL manually
        return redirect(export_url)
    
    

    def get_export_queryset(self, request):
        """
        Filter exported queryset based on ids stored in session
        """
        qs = super().get_export_queryset(request)
        key = f"export_ids_{self.model._meta.label_lower}"

        if request.method=="GET":
            ids = request.session.get(key, None)
        else:
            ids= request.session.pop(key,None)

        if ids:
            qs = qs.filter(pk__in=ids)
        
        return qs
    export_selected_redirect.short_description = "Export selected test cases"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "export-all-scripts/",
                self.admin_site.admin_view(self.export_all_scripts),
                name="testcase_export_all_scripts",
            ),
        ]
        return custom_urls + urls

    def export_all_scripts(self, request):
        queryset = self.get_queryset(request)

        zip_buffer = build_all_testcases_zip(queryset, True)

        response = HttpResponse(
            zip_buffer,
            content_type="application/zip"
        )
        response["Content-Disposition"] = (
            'attachment; filename="all_testcase_scripts.zip"'
        )
        return response

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
        "test_case_count",
        "is_active",
        "created",
        "modified",
    ]
    
    list_filter = [
        TestSuiteActiveFilter,
    ]
    
    search_fields = ["name", "description"]
    ordering = ["-created"]

    
    fields = [
        "name",
        "description",
        "is_active",
    ]
    
    readonly_fields = ["created", "modified"]
    
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


    def test_case_count(self, obj):
        """Display count of test cases in this suite"""
        return obj.test_case_count
    test_case_count.short_description = _("Test Cases")

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Superusers see everything
        if request.user.is_superuser:
            return qs

        # Normal users see only their own test cases
        return qs.filter(created_by=request.user)
    
    def has_view_permission(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return obj.created_by == request.user
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return obj.created_by == request.user
        return super().has_change_permission(request, obj)
    
    
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
        if not change and not obj.created_by:
            obj.created_by = request.user
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
        extra_context["show_test_case_selection"]= True
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
    


from django.contrib.admin.widgets import FilteredSelectMultiple

class TestCaseFilteredWidget(FilteredSelectMultiple):
    def render(self, name, value, attrs=None, renderer=None):
        html = super().render(name, value, attrs, renderer)
        # Add JSON with testcase flags
        data = {
            str(obj.pk): obj.is_configuration_push_required
            for obj in self.testcase_queryset
        }
        json_data= json.dumps(data)

        script = f"""
        <script id="testcase-config-json" type="application/json">
            {json_data}
        </script>
        """

        return mark_safe(html + script)

class TestSuiteExecutionAdminForm(forms.ModelForm):
    """Custom form for TestSuiteExecution admin"""
    
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['test_selection_type'].widget= forms.RadioSelect(choices=self.fields['test_selection_type'].choices)
        self.fields['device_selection'].widget = forms.RadioSelect(choices=self.fields['device_selection'].choices)
        self.fields['individual_test_cases'].widget.can_add_related= False

        if getattr(self.instance, "status", None) not in [0,4]:
            self.fields['device_selection'].disabled = True
            self.fields['test_selection_type'].disabled = True
            self.fields['name'].disabled = True
            self.fields['test_suite'].disabled = True
            if 'individual_test_cases' in self.fields:
                self.fields['individual_test_cases'].disabled = True

        
        # Store selected devices data for later use
        self._selected_devices_data = None
        self._device_group=None

        # Customize test_suite field
        if "test_suite" in self.fields:
            self.fields["test_suite"].required=False
            self.fields["test_suite"].help_text = _(
                "Select a test Group to execute (required if selection type is 'Test Group')"
            )
            self.fields["test_suite"].queryset = TestSuite.objects.filter(
                is_active=True
            )
        if "individual_test_cases" in self.fields:
            self.fields["individual_test_cases"].required = False
            self.fields["individual_test_cases"].help_text = _(
                "Select individual test cases (required if selection type is 'Individual Test Cases')"
            )
            if(self.instance.pk and self.instance.test_selection_type==0 and self.instance.test_case_execution_order):
                ordered_ids = [UUID(i) for i in self.instance.test_case_execution_order]

                qs = TestCase.objects.filter(id__in=ordered_ids, is_active=True)
                from django.db.models import Case, When

                preserved_order = Case(
                    *[When(id=pk, then=pos) for pos, pk in enumerate(ordered_ids)]
                )
    
    class Meta:
        model = TestSuiteExecution
        fields = ['name','test_selection_type','test_suite','individual_test_cases', 'device_selection']
        labels = {
            'name' : _('Enter Execution Name'),
            'test_selection_type' : _('Test Case Selection Type'),
            'test_suite': _('Select Test Group'),
            'individual_test_cases': _('Select Test Cases'),
            'device_selection' :_('Device Selection Type'),
        }
    def _get_selected_testcases_from_cleaned_data(self, cleaned_data):
        test_selection_type = cleaned_data.get("test_selection_type")
        test_suite = cleaned_data.get("test_suite")
        individual_test_cases = cleaned_data.get("individual_test_cases")

        if test_selection_type == 1 and test_suite:
            return test_suite.test_cases.filter(
                is_configuration_push_required=True
            )

        if test_selection_type == 0 and individual_test_cases:
            return individual_test_cases.filter(
                is_configuration_push_required=True
            )

        return TestCase.objects.none()
    def clean(self):
        """Custom validation"""
        print(">>> CLEAN METHOD STARTED <<<")
        cleaned_data = super().clean()


        test_selection_type= cleaned_data.get('test_selection_type')
        test_suite = cleaned_data.get('test_suite')
        individual_test_cases= cleaned_data.get('individual_test_cases')

        if test_selection_type==1: 
            if not test_suite:
                print(">>> ERROR: No test suite selected <<<")
                raise forms.ValidationError({
                    'test_suite': _('Please select a test group to execute.')
                })
            cleaned_data['individual_test_cases']= TestCase.objects.none()
        elif test_selection_type==0:
            ordered_ids = self.data.getlist("individual_test_cases")
            cleaned_data["_ordered_test_case_ids"] = ordered_ids
            if not individual_test_cases or individual_test_cases.count()==0 :
                if self.instance.pk and self.instance.individual_test_cases.exists():
                    cleaned_data["individual_test_cases"]=self.instance.individual_test_cases.all()
                else:
                    print(">>> ERROR: No test cases selected <<<")
                    raise forms.ValidationError({
                        'individual_test_cases': _('Please select atleast one test case to execute.')
                    })
            cleaned_data['test_suite']=None

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


        if selected_devices_data:
            try:
                selected_device_data = json.loads(selected_devices_data)
                selected_device_ids= [d["id"] for d in selected_device_data]
                print(f">>> Parsed device IDs: {selected_device_ids} <<<")
                
                if not selected_device_ids or len(selected_device_ids) == 0:
                    print(">>> ERROR: No devices selected <<<")
                    raise forms.ValidationError({
                        '__all__': _('At least one device must be selected for execution.')
                    })
                
                # Validate that all selected devices exist and are working
                valid_devices = Device.objects.filter(
                    id__in=selected_device_ids,
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
    
    #NOTE: currently not is use 
    def create_test_case_executions(self, instance):
        """
        Create TestCaseExecution entries for individual test case mode
        This links individual test cases to devices for execution
        """
        print(f">>> CREATE_TEST_CASE_EXECUTIONS METHOD STARTED for instance: {instance.id} <<<")
        
        # Only for individual test case selection
        if instance.test_selection_type != 0:
            print(">>> Skipping create_test_case_executions (using test suite mode) <<<")
            return
        
        # Get all execution devices
        execution_devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=instance
        ).select_related('device')
        
        if not execution_devices.exists():
            print(">>> WARNING: No execution devices found <<<")
            return
        
        # Get individual test cases
        individual_test_cases = instance.individual_test_cases.all()
        
        if not individual_test_cases.exists():
            print(">>> WARNING: No individual test cases found <<<")
            return
        
        print(f">>> Found {execution_devices.count()} devices and {individual_test_cases.count()} test cases <<<")
        
        # Clear existing test case executions for this execution
        deleted_count = TestCaseExecution.objects.filter(
            test_suite_execution=instance
        ).delete()
        print(f">>> Deleted {deleted_count[0]} existing TestCaseExecution entries <<<")
        
        # Create TestCaseExecution for each device × test case combination
        created_count = 0
        for execution_device in execution_devices:
            order = 1
            for test_case in individual_test_cases:
                try:
                    TestCaseExecution.objects.create(
                        test_suite_execution=instance,
                        device=execution_device.device,
                        test_case=test_case,
                        execution_order=order,
                        status='pending'
                    )
                    created_count += 1
                    order += 1
                    print(f">>> Created TestCaseExecution: Device={execution_device.device.name}, TestCase={test_case.name} <<<")
                except Exception as e:
                    error_msg = f"Error creating TestCaseExecution: {e}"
                    logger.error(error_msg)
                    print(f">>> ERROR: {error_msg} <<<")
        
        print(f">>> Successfully created {created_count} TestCaseExecution entries <<<")
        
        # Update testcase_count
        instance.testcase_count = individual_test_cases.count()
        instance.save(update_fields=['testcase_count'])
        print(f">>> Updated testcase_count to {instance.testcase_count} <<<")

    def save_devices(self, instance):
        """Save devices for the test suite execution"""
        print(f">>> SAVE_DEVICES METHOD STARTED for instance: {instance.id} <<<")
        
        # Use stored device data or get from form data
        selected_devices_data = self._selected_devices_data or self.data.get('selected_devices_data', '')
        print(f">>> Processing selected devices data: {selected_devices_data} <<<")
        
        if selected_devices_data:
            try:
                selected_device_data = json.loads(selected_devices_data)
                selected_device_ids= [d["id"] for d in selected_device_data]
                print(f">>> Parsed device IDs for saving: {selected_device_ids} <<<")
                
                # Clear existing devices for this execution
                deleted_count = TestSuiteExecutionDevice.objects.filter(test_suite_execution=instance).delete()
                print(f">>> Deleted {deleted_count[0]} existing TestSuiteExecutionDevice entries <<<")
                
                # Create new TestSuiteExecutionDevice entries
                successful_devices = 0
                for device_data in selected_device_data:
                    device_id= device_data["id"]
                    connection_protocol= device_data["protocol"]
                    print(f">>> Processing device ID: {device_id}  {connection_protocol}<<<")
                    try:
                        device = Device.objects.get(id=device_id)
                        print(f">>> Found device: {device} (ID: {device.id}) <<<")
                        
                        execution_device = TestSuiteExecutionDevice.objects.create(
                            test_suite_execution=instance,
                            device=device,
                            connection_protocol=connection_protocol,
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
        instance.save()
        self.save_m2m()
        ordered_ids = self.cleaned_data.get("_ordered_test_case_ids")
        
        if instance.test_selection_type == 0 and ordered_ids:
            instance.test_case_execution_order = ordered_ids
            instance.save(update_fields=["test_case_execution_order"])
            
        self.save_devices(instance)
        if instance.test_selection_type ==0 :
            instance.testcase_count = instance.individual_test_cases.all().count()
            instance.save(update_fields=['testcase_count'])
       
        print(f">>> SAVE METHOD COMPLETED. Returning instance: {instance} <<<")
        return instance


@admin.register(TestSuiteExecution)
class TestSuiteExecutionAdmin(BaseVersionAdmin):
    form = TestSuiteExecutionAdminForm
    
    change_form_template = 'admin/test_management/testsuitexecution/change_form.html'
    list_display = [
        "name",
        "active_device_count",
        "testcase_count",
        "created",
        "view_history",
     ]
    list_filter = [
        TestExecutionStatusFilter,
        "test_selection_type",
        "created",
        ("test_suite", admin.RelatedOnlyFieldListFilter),
    ]
    list_select_related = ["test_suite", "device_group"]
    search_fields = ["name", "test_suite__name"]
    ordering = ["-created"]
    
    fields = [
        "name",
        "test_selection_type",
        "test_suite",
        "individual_test_cases",
        "device_selection",
    ]
    autocomplete_fields=["test_suite"]
    
    filter_horizontal=["individual_test_cases"]
    readonly_fields = ["created", "modified", "device_count", "testcase_count"]
    actions = ["execute_or_reexecute_test_suite"]

    def get_actions(self, request):
       
        actions = super().get_actions(request)
        show = getattr(settings, "SHOW_RE_EXECUTION")
        if not show:
            actions.pop("re_execute_test_suite", None)

        return actions
    class Media:
        js = ('admin/js/jquery.init.js',
              'test-management/js/selection_toggle.js')
    
    class Meta:
        verbose_name = _("Test Execution")  # Change from "Test Suite Execution"
        verbose_name_plural = _("Test Executions")  # Change from "Test Suite Executions"
    
    def active_device_count(self, obj):
        """Return human readable execution status"""
        return obj.active_device_count
    active_device_count.short_description = _("Device Count")
   
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.request = request   
        return form
    
    def test_selection_display(self, obj):
        """Display test selection type with icon"""
        if obj.test_selection_type == 1:
            return format_html(
                '<span title="Test Group">Group</span>'
            )
        else:
            return format_html(
                '<span title="Individual Test Cases">Individual</span>'
            )
    test_selection_display.short_description = _("Selection Type")
    test_selection_display.admin_order_field = "test_selection_type"

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

        if db_field.name == "individual_test_cases":
            obj_id = request.resolver_match.kwargs.get("object_id")
            if obj_id:
                obj = self.get_object(request, obj_id)
                if obj and obj.status not in [0, 4]:
                    formfield.widget.attrs["disabled"] = True

        return formfield
   
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "individual_test_cases":

            # Base queryset
            qs = db_field.related_model.objects.all()

            # Restrict for non‑superusers
            if not request.user.is_superuser:
                qs = qs.filter(Q(created_by=request.user) | Q(is_system_test_case=True))

            widget = TestCaseFilteredWidget(
                verbose_name="Test Cases",
                is_stacked=False,
            )
            widget.testcase_queryset = qs

            kwargs["queryset"] = qs
            kwargs["widget"] = widget

            return super().formfield_for_manytomany(db_field, request, **kwargs)

        return super().formfield_for_manytomany(db_field, request, **kwargs)
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
        wants_execute = "_save_execute" in request.POST
        wants_schedule = "_schedule_execution" in request.POST

        if wants_execute:
            self.message_user(
                request,
                f"Execution saved successfully. Please upload the required files to start execution.",
                messages.SUCCESS
            )
            return HttpResponseRedirect(
            reverse("admin:execution_config_push", args=[obj.pk]) + "?execute=1"
            )
        if wants_schedule:
            schedule_datetime = request.POST.get("schedule_datetime")
            if schedule_datetime:
                request.session["execution_schedule_time"]= schedule_datetime
                self.message_user(
                    request,
                    f"Execution saved successfully. Please upload the required files to schedule execution.",
                    messages.SUCCESS
                )
                return HttpResponseRedirect(
                    reverse("admin:execution_config_push", args=[obj.pk]) + "?schedule=1"
                    )
            
        self.message_user(
                    request,
                    f"Execution saved successfully. Please upload the required files.",
                    messages.SUCCESS
                )
        return HttpResponseRedirect(
                reverse("admin:execution_config_push", args=[obj.pk])
            )

    # “Save & execute” after CHANGE call
    def response_change(self, request, obj):
        wants_execute = "_save_execute" in request.POST
        wants_schedule = "_schedule_execution" in request.POST

        if wants_execute:
            self.message_user(
                request,
                f"Execution saved successfully. Please upload the required files to start execution.",
                messages.SUCCESS
            )
            return HttpResponseRedirect(
                reverse("admin:execution_config_push", args=[obj.pk]) + "?execute=1"
            )
        if wants_schedule:
            schedule_datetime = request.POST.get("schedule_datetime")
            if schedule_datetime:
                request.session["execution_schedule_time"]= schedule_datetime
                self.message_user(
                    request,
                    f"Execution saved successfully. Please upload the required files to schedule execution.",
                    messages.SUCCESS
                )
                return HttpResponseRedirect(
                    reverse("admin:execution_config_push", args=[obj.pk]) + "?schedule=1"
                )
        self.message_user(
                request,
                f"Execution saved successfully. Please upload the required files.",
                messages.SUCCESS
            )
        return HttpResponseRedirect(
                reverse("admin:execution_config_push", args=[obj.pk])
            )
    
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
        if obj.test_selection_type==1 and obj.test_suite:
            return format_html(
                '<a href="../testsuite/{}/change/">{}</a>',
                obj.test_suite.pk,
                obj.test_suite.name
            )
        elif obj.test_selection_type==0:
            count= obj.individual_test_cases.count()
            return format_html(
                '<span title="Individual test cases">{} test case(s)</span>',
                count
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
                '<path:object_id>/all-history/',
                self.admin_site.admin_view(self.execution_all_history_view),
                name='test_management_testexecution_all_history'
            ),
            path(
                '<path:object_id>/history/',
                self.admin_site.admin_view(self.execution_history_view),
                name='test_management_testexecution_history'
            ),
            path(
                "<uuid:pk>/config-push/",
                self.admin_site.admin_view(self.config_push_view),
                name="execution_config_push",
            ),
        ]
        return custom_urls + urls

    def execution_all_history_view(self, request, object_id):
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
        if execution.test_selection_type ==1 and execution.test_suite:
            test_source_name= execution.test_suite.name
        else:
            test_source_name= f"Individual Tests ({execution.testcase_count})"
        
        context = dict(
        self.admin_site.each_context(request),  # REQUIRED
        title="All History",
        execution=execution,
        execution_id=str(execution.pk),
        execution_devices=execution_devices,
        device_executions=device_executions,
        test_case_executions=test_case_executions,
        opts=self.model._meta,                  # REQUIRED
        original=execution,                     # REQUIRED
        preserved_filters=self.get_preserved_filters(request),
        has_view_permission=True,
        )

        return TemplateResponse(
            request,
            'admin/test_management/testexecution/all_executions_history.html',
            context,
        )
    
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
        if execution.test_selection_type ==1 and execution.test_suite:
            test_source_name= execution.test_suite.name
        else:
            test_source_name= f"Individual Tests ({execution.testcase_count})"
        
        context = dict(
        self.admin_site.each_context(request),  # REQUIRED
        title="Test Execution History",
        execution=execution,
        execution_id=str(execution.pk),
        execution_devices=execution_devices,
        device_executions=device_executions,
        test_case_executions=test_case_executions,
        opts=self.model._meta,                  # REQUIRED
        original=execution,                     # REQUIRED
        preserved_filters=self.get_preserved_filters(request),
        has_view_permission=True,
        show_re_execution= getattr(settings, "SHOW_RE_EXECUTION"),
        execution_history_auto_refresh_time= getattr(settings, "EXECUTION_HISTORY_AUTO_REFRESH_TIME"),

        )

        return TemplateResponse(
            request,
            'admin/test_management/testexecution/execution_history.html',
            context,
        )
        
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(
            parent_execution__isnull=True
        ).prefetch_related("re_executions")

        if request.user.is_superuser:
            return qs

        return qs.filter(created_by=request.user)
    
    def has_view_permission(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return obj.created_by == request.user
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return obj.created_by == request.user
        return super().has_change_permission(request, obj)

    def _history_url(self, obj):
        opts = obj._meta
        return reverse(
            f"admin:{opts.app_label}_{opts.model_name}_history",
            args=[obj.pk],
        )


    def view_history_links(self, obj):
        """
        Show: 0 1 2 3 ...
        0 = history of the original execution
        1..n = histories of its re-executions (ordered)
        """
        if not obj.pk or obj.parent_execution_id:
            return "-"

        root = obj.parent_execution if obj.parent_execution_id else obj

        links = []
        # "0" -> root execution history
        links.append(format_html('<a href="{}">0</a>', self._history_url(root)))

        # "1..n" -> re-executions history
        reexecs = root.re_executions.all().order_by("re_execution_index", "created", "pk")

        # If you always set re_execution_index, use it; otherwise fallback to enumeration
        for idx, rex in enumerate(reexecs, start=1):
            label = rex.re_execution_index if rex.re_execution_index is not None else idx
            links.append(format_html('<a href="{}">{}</a>', self._history_url(rex), label))

        # join with spaces
        return format_html(" ".join(["{}"] * len(links)), *links)

    view_history_links.short_description = _("History")

    def _build_artifacts(self, execution):
        from .models import ExecutionArtifact, TestSuiteExecutionDevice

        devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        )

        testcases = execution.get_configuration_selected_test_cases()
        ExecutionArtifact.objects.filter(
                execution=execution
            ).exclude(
                testcase__in=testcases
            ).delete()
        for d in devices:
            for tc in testcases:
                ExecutionArtifact.objects.get_or_create(
                    execution=execution,
                    device_id=d.device_id,  # SAFE
                    testcase=tc,
                )
    def _missing_config_artifacts(self, execution):
        """
        Returns queryset of ExecutionArtifact
        where config_file is missing but required.
        """
        return execution.artifacts.filter(
            testcase__is_configuration_push_required=True,
            config_file__isnull=True,
        )
    
    def config_push_view(self, request, pk):
        execution = get_object_or_404(TestSuiteExecution, pk=pk)
        execute_after_save= request.GET.get("execute")=="1"
        schedule_ater_save= request.GET.get("schedule")=="1"
        
        self._build_artifacts(execution)
        
        if request.method == "POST":
            raw_emails = request.POST.get("notification_emails", "").strip()

            # Validate emails
            try:
                if raw_emails:
                    for email in raw_emails.split(","):
                        validate_email(email.strip())
            except ValidationError:
                self.message_user(
                    request,
                    "One or more email addresses are invalid.",
                    messages.ERROR,
                )
                return redirect(request.path)
            
            formset = ExecutionArtifactFormSet(
                request.POST,
                request.FILES,
                instance=execution,
            )
            if formset.is_valid():

                has_error = False

                for form in formset.forms:
                    uploaded_file = form.cleaned_data.get("config_file")
                    existing_file = form.instance.config_file

                    if not uploaded_file and not existing_file:
                        form.add_error(
                            "config_file",
                            "Configuration file is required."
                        )
                        has_error = True

                if not has_error:
                    # VALIDATE BEFORE SAVE
                    total_forms = formset.total_form_count()
                    config_required = total_forms > 0
                    formset.save()
                    execution.notification_emails = raw_emails
                    execution.save(update_fields=["notification_emails"])

                    schedule_time= request.session.get("execution_schedule_time")
                    if execute_after_save:
                        self._start_execution(request, execution, False)
                    if schedule_ater_save and schedule_time:
                        self._schedule_execution(
                            request,
                            execution,
                            schedule_time,
                        )
                        request.session.pop("execution_schedule_time", None)
 
                    self.message_user(
                        request,
                        "Additional Details saved successfully.",
                        messages.SUCCESS,
                    )

                    return HttpResponseRedirect(
                        reverse("admin:test_management_testsuiteexecution_changelist")
                    )

        else:
            formset = ExecutionArtifactFormSet(instance=execution)
        
        context = dict(
            self.admin_site.each_context(request),  # REQUIRED
            title="Additional Details",
            execution=execution,
            opts=self.model._meta,                  # REQUIRED
            original=execution,                     # REQUIRED
            formset=formset
        )

        return TemplateResponse(
            request,
            'admin/test_management/config_push.html',
            context,
            
        )
        
    
    def view_history(self, obj):
        """Add history view link"""
        if not obj.pk:
            return "-"

        url = reverse(
            "admin:test_management_testexecution_all_history",
            args=[obj.pk],
        )
        return format_html('<a href="{}" class="viewlink">View History</a>', url)
    view_history.short_description = _("History")
    view_history.allow_tags = True

    @admin.action(description=_("Re-Execute Selected Test Executions"))
    def re_execute_test_suite(self, request, queryset):
        """Create replica of executions and execute immediately"""
        from .tasks import execute_test_suite as execute_test_suite_task
        from .models import ExecutionArtifact
        
        re_executed_count = 0
        failed_count = 0
        
        # Store successfully created executions to trigger AFTER all transactions complete
        executions_to_trigger = []
        not_executed_executions=[]
        error_cnt=0
        for original in queryset:
            try:
                with transaction.atomic():
                    # Get root execution
                    root = original.parent_execution or original
                    if not root.is_executed:
                        not_executed_executions.append(root.name)
                        error_cnt += 1
                        continue
                    # Calculate next re_execution_index
                    existing_count = root.re_executions.count()
                    new_index = existing_count + 1
                    
                    # Clone the execution
                    new_execution = TestSuiteExecution(
                        name=f"{root.name}_{new_index}",
                        test_selection_type=original.test_selection_type,
                        test_suite=original.test_suite,
                        test_case_execution_order=original.test_case_execution_order,
                        device_selection=original.device_selection,
                        device_group=original.device_group,
                        notification_emails=original.notification_emails,
                        parent_execution=root,
                        re_execution_index=new_index,
                        created_by=request.user,
                        is_executed=False,
                    )
                    new_execution.save()
                    
                    # Copy M2M for individual test cases
                    if original.test_selection_type == 0:
                        new_execution.individual_test_cases.set(
                            original.individual_test_cases.all()
                        )
                    
                    # Clone devices
                    for dev in TestSuiteExecutionDevice.objects.filter(
                        test_suite_execution=original
                    ):
                        if not dev.device.is_deleted:
                            TestSuiteExecutionDevice.objects.create(
                                test_suite_execution=new_execution,
                                device=dev.device,
                                connection_protocol=dev.connection_protocol,
                                status='pending'
                            )
                    
                    # Clone artifacts (config files)
                    for artifact in ExecutionArtifact.objects.filter(
                        execution=original
                    ):
                        ExecutionArtifact.objects.create(
                            execution=new_execution,
                            device=artifact.device,
                            testcase=artifact.testcase,
                            config_file=artifact.config_file,
                            is_pushed=False
                        )
                    
                    # Update counts
                    new_execution.device_count = TestSuiteExecutionDevice.objects.filter(
                        test_suite_execution=new_execution
                    ).count()
                    new_execution.testcase_count = (
                        new_execution.test_suite.test_case_count 
                        if new_execution.test_selection_type == 1 and new_execution.test_suite
                        else new_execution.individual_test_cases.count()
                    )
                    new_execution.is_executed = True
                    new_execution.save(update_fields=['device_count', 'testcase_count', 'is_executed'])
                    
                    execution_id = str(new_execution.id)

                    token, _ = Token.objects.get_or_create(user=request.user)

                    transaction.on_commit(
                        lambda eid=execution_id: execute_test_suite_task.delay(eid, str(token.key))
                    )
                    re_executed_count += 1
                    logger.info(f"Re-executed {original.id} -> {new_execution.id}")
                        
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to re-execute {original.id}: {e}", exc_info=True)
                self.message_user(
                        request,
                        f"Failed to re-execute {original}: {str(e)}",
                        messages.ERROR
                )
     
        
        if re_executed_count > 0:
            self.message_user(
                request,
                ngettext(
                        "%d test execution was re-executed.",
                        "%d test executions were re-executed.",
                        re_executed_count,
                ) % re_executed_count,
                messages.SUCCESS,
            )
        if error_cnt > 0:
            execution_names = ", ".join(not_executed_executions)
            self.message_user(
                request,
                ngettext(
                    "The following execution was never executed and cannot be re-executed: %(names)s. "
                    "Please execute it first.",
                    "The following executions were never executed and cannot be re-executed: %(names)s. "
                    "Please execute them first.",
                    error_cnt,
                ) % {
                    "names": execution_names
                },
                messages.WARNING,
            )       
      



    def save_model(self, request, obj, form, change):
        print(f">>> ADMIN save_model called. Change: {obj} <<<")
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        print(f">>> Object saved with ID: {obj.id} <<<")
        # Ensure devices are saved
        if hasattr(form, 'save_devices'):
            form.save_devices(obj)

     

        # FIX: absolute import
        from openwisp_test_management.swapper import load_model
        TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")

        obj.device_count = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=obj
        ).count()
        if obj.test_selection_type == 1 and obj.test_suite_id:
            obj.testcase_count = obj.test_suite.test_case_count
        else:
            obj.testcase_count = obj.individual_test_cases.count()

        obj.save(update_fields=["device_count", "testcase_count"])

        print(f">>> ADMIN save_model completed. Updated device_count={obj.device_count}, testcase_count={obj.testcase_count} <<<")
    
    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        """Prevent deletion of executed test suites"""
        if obj and obj.is_executed:
            return False
        return super().has_delete_permission(request, obj)
    
    @admin.action(description=_("Execute Selected Test Executions"))
    def execute_test_suite(self, request, queryset, from_action_execution=True):
        """Execute test suites using Celery tasks"""
        from .tasks import execute_test_suite as execute_test_suite_task
        from .models import ScheduledExecution
        
        logger.info(f"Execute action triggered for {queryset.count()} items")
        
        active_scheduled = queryset.none()
        future_scheduled = queryset.none()
        overdue_scheduled = queryset.none()

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

            if future_scheduled.exists():
                future_scheduled.update(
                    status=ScheduledExecution.Status.CANCELLED
                )
            to_execute = queryset.filter(is_executed=False)
        
        # Currently running/queued
        if active_scheduled.exists():
            count = active_scheduled.count()
            if request:
                self.message_user(
                    request,
                    _(f"{count} test Group(s) are currently running or queued. Skipping these."),
                    messages.WARNING
                )
            
       
        
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
                if execution.test_selection_type==1:
                    test_count= execution.test_suite.test_cases.filter(test_type=1).count()
                else:
                    test_count = execution.individual_test_cases.count()

                device_count = execution.active_device_count
                
                
                if device_count == 0:
                    logger.warning(f"No devices for execution {execution.id}")
                    if request:
                        self.message_user(
                            request,
                            f"Skipped {execution}: No devices configured",
                            messages.WARNING
                        )
                    continue
               
                required_config= set(
                    (UUID(r["device_id"]), UUID(r["testcase_id"]))
                    for r in execution.get_required_artifacts()
                )
                existing_config = set(
                    ExecutionArtifact.objects
                    .filter(execution=execution, config_file__isnull= False)
                    .exclude(config_file="")
                    .values_list("device_id", "testcase_id")
                )
                missing= required_config - existing_config 
               
                if missing and request:
                    self.message_user(
                            request,
                            f"Missing execution artifacts for execution : {execution.name}",
                            messages.WARNING
                        )
                    continue

                # Mark as executed
                execution.is_executed = True
                execution.save()
                
                token, _ = Token.objects.get_or_create(user=request.user)
                # Launch Celery task
                result = execute_test_suite_task.delay(str(execution.id), str(token.key))
                
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
        extra_context['TEST_MANAGEMENT_SSH_ENABLED'] = getattr(
            settings, 'TEST_MANAGEMENT_SSH_ENABLED', True
        )
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
            ScheduledExecution=load_model("ScheduledExecution")
            scheduled_dt = None
            if obj and obj.status == 4:
                # Get the most recent scheduled execution (if multiple)
                scheduled = ScheduledExecution.objects.filter(execution=obj).order_by('-scheduled_time').first()
                if scheduled and scheduled.scheduled_time:
                    # Convert to local timezone & ISO format for <input type="datetime-local">
                    local_dt = timezone.localtime(scheduled.scheduled_time)
                    scheduled_dt = local_dt.strftime('%Y-%m-%dT%H:%M')
            
            # Pass it to the template context
            extra_context['scheduled_datetime'] = scheduled_dt
            extra_context["notification_emails"]= obj.notification_emails
            related_devices = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution=obj
            ).select_related("device")

            device_protocol_map={
                str(dev.device_id) : dev.connection_protocol for dev in related_devices
            }

            device_manager = Device.all_objects if obj.status != 0 else Device.objects
            devices_query = device_manager.filter(
                id__in=device_protocol_map.keys()
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

                if device.is_deleted:
                    device_status= "Deleted"
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
                    "connection_protocol" :device_protocol_map.get(str(device.id),0),
                })

            extra_context["execution_devices_json"] = json.dumps(devices_data)
            if obj.test_case_execution_order:
                extra_context["ordered_testcase_ids"] = obj.test_case_execution_order
        return super().change_view(request, object_id, form_url, extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['TEST_MANAGEMENT_SSH_ENABLED'] = getattr(
            settings, 'TEST_MANAGEMENT_SSH_ENABLED', True
        )
        return super().add_view(request, form_url, extra_context)
    
    def recover_view(self, request, version_id, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_execution_device_details'] = True
        extra_context["is_recover_view"]= True
        version = self._get_version_object(version_id)

        if version:

            # Add device_group info if it exists
            execution_obj = version._object_version.object 
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
            device_protocol_map = { str(v._object_version.object.device_id) : getattr(v._object_version.object, "connection_protocol") for v in related_versions }       

            #  Re-use logic from get_available_devices
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
                    'connection_protocol' : device_protocol_map.get(str(device.id),0),
                })
            

            extra_context['execution_devices_json'] = json.dumps(devices_data)

        return super().recover_view(request, version_id, extra_context=extra_context)

    @admin.action(description=_("Execute / Re-Execute Selected Test Executions"))
    def execute_or_reexecute_test_suite(self, request, queryset):
        from .tasks import execute_test_suite as execute_test_suite_task
        from .models import ScheduledExecution, ExecutionArtifact
        from django.db import transaction
        from django.utils import timezone

        executed_count = 0
        reexecuted_count = 0
        skipped_count = 0
        failed_count = 0

        for execution in queryset:
            try:
                # -----------------------------------------
                # 1. Detect scheduling state
                # -----------------------------------------
                schedules = ScheduledExecution.objects.filter(execution=execution)

                active_schedule = schedules.filter(
                    status__in=[
                        ScheduledExecution.Status.QUEUED,
                        ScheduledExecution.Status.IN_PROCESS
                    ]
                ).exists()

                future_schedule = schedules.filter(
                    status=ScheduledExecution.Status.PENDING,
                    scheduled_time__gt=timezone.now()
                )

                overdue_schedule = schedules.filter(
                    status=ScheduledExecution.Status.PENDING,
                    scheduled_time__lte=timezone.now()
                )

                if active_schedule:
                    skipped_count += 1
                    continue

                # -----------------------------------------
                # 2. Cancel future schedule if exists
                # -----------------------------------------
                if future_schedule.exists():
                    future_schedule.update(status=ScheduledExecution.Status.CANCELLED)
                
                if overdue_schedule.exists():
                    overdue_schedule.update(status=ScheduledExecution.Status.CANCELLED)

                # -----------------------------------------
                # 3. If NOT executed : Execute
                # -----------------------------------------
                if not execution.is_executed:

                    device_count = execution.active_device_count
                    if device_count == 0:
                        self.message_user(
                            request,
                            f"Skipped {execution}: No devices configured",
                            messages.WARNING
                        )
                        skipped_count += 1
                        continue

                    required_config = {
                        (UUID(r["device_id"]), UUID(r["testcase_id"]))
                        for r in execution.get_required_artifacts()
                    }

                    existing_config = set(
                        ExecutionArtifact.objects
                        .filter(execution=execution, config_file__isnull=False)
                        .exclude(config_file="")
                        .values_list("device_id", "testcase_id")
                    )

                    if required_config - existing_config:
                        self.message_user(
                            request,
                            f"Missing execution artifacts for {execution.name}",
                            messages.WARNING
                        )
                        skipped_count += 1
                        continue

                    execution.is_executed = True
                    execution.save(update_fields=["is_executed"])

                    token, _ = Token.objects.get_or_create(user=request.user)
                    transaction.on_commit(
                        lambda eid=str(execution.id): execute_test_suite_task.delay(eid, str(token.key))
                    )

                    executed_count += 1
                    continue

                # -----------------------------------------
                # 4. If already executed : Re-execute
                # -----------------------------------------
                with transaction.atomic():
                    root = execution.parent_execution or execution
                    new_index = root.re_executions.count() + 1

                    new_execution = TestSuiteExecution.objects.create(
                        name=f"{root.name}_{new_index}",
                        test_selection_type=execution.test_selection_type,
                        test_suite=execution.test_suite,
                        test_case_execution_order=execution.test_case_execution_order,
                        device_selection=execution.device_selection,
                        device_group=execution.device_group,
                        notification_emails=execution.notification_emails,
                        parent_execution=root,
                        re_execution_index=new_index,
                        created_by=request.user,
                        is_executed=True,
                    )

                    if execution.test_selection_type == 0:
                        new_execution.individual_test_cases.set(
                            execution.individual_test_cases.all()
                        )

                    for dev in TestSuiteExecutionDevice.objects.filter(
                        test_suite_execution=execution
                    ):
                        if not dev.device.is_deleted:
                            TestSuiteExecutionDevice.objects.create(
                                test_suite_execution=new_execution,
                                device=dev.device,
                                connection_protocol=dev.connection_protocol,
                                status="pending"
                            )

                    for artifact in ExecutionArtifact.objects.filter(execution=execution):
                        ExecutionArtifact.objects.create(
                            execution=new_execution,
                            device=artifact.device,
                            testcase=artifact.testcase,
                            config_file=artifact.config_file,
                            is_pushed=False
                        )

                    new_execution.device_count = TestSuiteExecutionDevice.objects.filter(
                        test_suite_execution=new_execution
                    ).count()

                    new_execution.testcase_count = (
                        new_execution.test_suite.test_case_count
                        if new_execution.test_selection_type == 1
                        else new_execution.individual_test_cases.count()
                    )

                    new_execution.save(
                        update_fields=["device_count", "testcase_count"]
                    )

                    token, _ = Token.objects.get_or_create(user=request.user)
                    transaction.on_commit(
                        lambda eid=str(new_execution.id): execute_test_suite_task.delay(eid, str(token.key))
                    )

                    reexecuted_count += 1

            except Exception as e:
                failed_count += 1
                logger.error(f"Execution failed for {execution.id}: {e}", exc_info=True)
                self.message_user(
                    request,
                    f"Failed to process {execution}: {str(e)}",
                    messages.ERROR
                )

        # -----------------------------------------
        # Final admin feedback
        # -----------------------------------------
        if executed_count:
            self.message_user(
                request,
                f"{executed_count} execution(s) started",
                messages.SUCCESS
            )

        if reexecuted_count:
            self.message_user(
                request,
                f"{reexecuted_count} execution(s) re-executed",
                messages.SUCCESS
            )

        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count} execution(s) skipped (already running / invalid)",
                messages.WARNING
            )

        if failed_count:
            self.message_user(
                request,
                f"{failed_count} execution(s) failed",
                messages.ERROR
            )


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
        "created",
        "modified",
    ]
    
    list_filter = [
        DeviceGroupOrganizationFilter,
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
                            logger.error(f"Device not found or wrong org: {device_id}")
                        except ValidationError as e:
                            error_count += 1
                            logger.error(f"Validation error: {e}")
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error adding device: {e}")
                
                
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
        version = self._get_version_object(version_id)

        if version:
            execution_obj = version._object_version.object
            
            # Now get related devices (live DB, not historical)
            related_versions = version.revision.version_set.filter(
            content_type__model="testdevicegroupdevice"
            )

            recovered_device_ids = [str(v._object_version.object.device_id) for v in related_versions]

            # Re-use logic from get_available_devices
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

# admin.site.register(TestCategory, TestCategoryExportable)
admin.site.register(TestCase,TestCasesExportable)
# Register models with reversion for history tracking
if not reversion.is_registered(TestCategory):
    reversion.register(TestCategory)
    
if not reversion.is_registered(TestCase):
    reversion.register(TestCase)    


# Register models with reversion for history tracking
if not reversion.is_registered(TestSuite):
    reversion.register(TestSuite)


if not reversion.is_registered(TestSuiteExecution):
    reversion.register(TestSuiteExecution)


if not reversion.is_registered(TestDeviceGroup):
    reversion.register(TestDeviceGroup)



if not reversion.is_registered(TestDeviceGroupDevice):
    reversion.register(TestDeviceGroupDevice)





