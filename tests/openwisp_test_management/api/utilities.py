from rest_framework import serializers
from django.db import models
from django.utils.translation import gettext_lazy as _

class TestTypeChoices(models.IntegerChoices):
    ROBOT_FRAMEWORK = 1, _('Robot Framework')
    AGENT = 2, _('Device')



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
            library_pattern = r'(Library\s+\.\./\.\./resources/keywords/)([a-zA-Z0-9_\-]+)(\.py)'
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