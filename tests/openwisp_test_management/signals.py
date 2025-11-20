import os
import zipfile
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TestCase

@receiver(post_save, sender=TestCase)
def extract_zip_after_upload(sender, instance, created, **kwargs):

    if not created:
        return
    
    if instance.file:

        file_path = instance.file.path  # Full uploaded zip path
        

        # if test type is device
        if instance.test_type==2:
            try:
            # Only extract if file is a valid ZIP
                if zipfile.is_zipfile(file_path):

                    # Extract everything directly into: /opt/openwisp/media/test_case/
                    extract_to = settings.TEST_SCRIPT_MEDIA_ROOT

                    # Ensure folder exists
                    os.makedirs(extract_to, exist_ok=True)

                    # Extract
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            filename= os.path.basename(member.filename)
                            if not filename:
                                continue

                            base,ext= os.path.splitext(filename)
                            new_filename= f"{instance.test_case_id}{ext}"
                            dest_path= os.path.join(extract_to, new_filename)

                            with zip_ref.open(member) as source, open(dest_path,"wb") as target:
                                target.write(source.read())
                        # zip_ref.extractall(extract_to)

                    print(f"Extracted ZIP contents to: {extract_to}")
            except Exception as e:
                print("[ERROR] Device Test Script Upload : ",e)
        # if test type is robot
        elif instance.test_type==1:
            pass