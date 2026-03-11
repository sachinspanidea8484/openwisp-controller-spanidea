from rest_framework import serializers
from django.db import models
from ..swapper import load_model
from django.utils.translation import gettext_lazy as _
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from django.conf import settings
import os
from import_export.widgets import Widget
from django.core.exceptions import ValidationError
import requests
from urllib.parse import urlparse

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
        raise ValidationError("Python file is empty", field="python_script")

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise ValidationError(
            f"Syntax error at line {e.lineno}: {e.msg}",
            field="python_script"
        )

    has_defs = any(
        isinstance(n, (ast.FunctionDef, ast.ClassDef))
        for n in ast.walk(tree)
    )

    if not has_defs:
        raise ValidationError(
            "No function or class found in Python file",
            field="python_script"
        )

    compile(text, "<imported_script>", "exec")


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
      
        
             
def validate_robot_import(file_path):
    from robot.parsing import get_model

    try:
        model = get_model(file_path)
    except Exception as e:
        raise ValidationError(
            f"Robot parsing failed: {e}",
            field="robot_script"
        )

    if not model.sections:
        raise ValidationError(
            "Robot file has no sections",
            field="robot_script"
        )

    for section in model.sections:
        if "Test Cases" in str(section.header.data_tokens):
            return

    raise ValidationError(
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
            raise ValidationError(
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


def update_robot_file_tag(robot_file, new_test_case_id):
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
            raise serializers.ValidationError(_(f"Error updating robot file: {str(e)}"))
   
TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")

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
                raise Exception(
                        f"No test case found with id", field="test_case_id"
                    )
            system_generated= existing_testcase_data.is_system_test_case

            if test_case_id != existing_testcase_data.test_case_id:
                raise Exception(
                        f"User cannot change test case id", field="test_case_id"
                    )
            if test_type_mapping[test_type_from_file] != existing_testcase_data.test_type:
                raise Exception(
                        f"User cannot change test type", field="test_case_id"
                    )
            if existing_testcase_data.is_system_test_case:
                if not self.user or not self.user.is_superuser:
                    raise Exception(
                        f"Non-superuser cannot import system test case: {test_case_id}", field="test_case_id"
                    )
            if self.user != existing_testcase_data.created_by:
                if not self.user or not self.user.is_superuser:
                    raise Exception(
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

        python_path, extracted_description = store_script(
            row.get("python_script"),
            test_case_id=test_case_id,
            script_type="python",
            extract_description=True,
            system_generated= system_generated,
            test_type= test_type_from_file,
        )

        row["python_script"] = python_path

        if(not row.get("description")) and extracted_description : 
            row["description"]= extracted_description


import uuid
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_naive ,now
from rest_framework.exceptions  import ValidationError
def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False
    
def validate_schedule_time(schedule_time):
    dt = parse_datetime(schedule_time)
    if not dt:
        raise ValidationError({
           "schedule_time" :"Invalid schedule_time format. Use ISO-8601 with timezone."
        })
    if dt <= now():
        raise ValidationError({
            "schedule_time":"schedule_time must be a future datetime."
        })


    return dt

def schedule_execution(execution, schedule_time):
    if is_naive(schedule_time):
        schedule_time = make_aware(schedule_time)

    from ..models import ScheduledExecution

    ScheduledExecution.objects.update_or_create(
        execution=execution,
        defaults={
            "scheduled_time": schedule_time,
            "status": ScheduledExecution.Status.PENDING
        }
    )

    return schedule_time