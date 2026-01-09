import os
import zipfile
from django.conf import settings
from django.db.models.signals import post_save , pre_save
from django.dispatch import receiver
from .models import TestCase

@receiver(post_save, sender=TestCase)
def extract_zip_after_upload(sender, instance, created, **kwargs):

    if not created:
        return
    
    pass
    # if instance.file:

    #     file_path = instance.file.path  # Full uploaded zip path
        

    #     # if test type is device
    #     if instance.test_type==2:
    #         try:
    #         # Only extract if file is a valid ZIP
    #             if zipfile.is_zipfile(file_path):

    #                 # Extract everything directly into: /opt/openwisp/media/test_case/
    #                 extract_to = settings.TEST_SCRIPT_MEDIA_ROOT

    #                 # Ensure folder exists
    #                 os.makedirs(extract_to, exist_ok=True)

    #                 # Extract
    #                 with zipfile.ZipFile(file_path, 'r') as zip_ref:
    #                     for member in zip_ref.infolist():
    #                         filename= os.path.basename(member.filename)
    #                         if not filename:
    #                             continue

    #                         base,ext= os.path.splitext(filename)
    #                         new_filename= f"{instance.test_case_id}{ext}"
    #                         dest_path= os.path.join(extract_to, new_filename)

    #                         with zip_ref.open(member) as source, open(dest_path,"wb") as target:
    #                             target.write(source.read())
    #                     # zip_ref.extractall(extract_to)

    #                 print(f"Extracted ZIP contents to: {extract_to}")
    #         except Exception as e:
    #             print("[ERROR] Device Test Script Upload : ",e)
    #     # if test type is robot
    #     elif instance.test_type==1:
    #         pass


@receiver(post_save, sender=TestCase)
def robot_framework_server_push(sender, instance, created, **kwargs):
    if instance.test_type== 1:
        print(">>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<<<,,")
        print("file upload", instance)


@receiver(pre_save, sender=TestCase)
def capture_old_testcase_id(sender, instance, **kwargs):
    if not instance.pk:
        return

    old = sender.objects.filter(pk=instance.pk).values("test_case_id").first()
    instance._old_test_case_id = old["test_case_id"] if old else None


@receiver(post_save, sender=TestCase)
def handle_id_and_file_changes(sender, instance, created, **kwargs):
    if created:
        return

    old_id = getattr(instance, "_old_test_case_id", None)
    new_id = instance.test_case_id

    if not old_id or old_id == new_id:
        return

    base_path = settings.MEDIA_ROOT

    for field in ("python_script", "robot_script"):
        file_field = getattr(instance, field)

        if not file_field:
            continue

        #  File was replaced → DO NOTHING
        if file_field._file is not None and not file_field._committed:
            continue

        old_rel_path = file_field.name
        dir_name = os.path.dirname(old_rel_path)
        ext = os.path.splitext(old_rel_path)[1]

        old_abs = os.path.join(base_path, old_rel_path)
        new_rel = os.path.join(dir_name, f"{new_id}{ext}")
        new_abs = os.path.join(base_path, new_rel)

        if os.path.exists(old_abs):
            os.rename(old_abs, new_abs)

        setattr(instance, field, new_rel)

    sender.objects.filter(pk=instance.pk).update(
        python_script=instance.python_script,
        robot_script=instance.robot_script,
    )