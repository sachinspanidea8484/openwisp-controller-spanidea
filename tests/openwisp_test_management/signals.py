import os
import zipfile
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TestCase
# from base.models import FileUpload
@receiver(post_save, sender=TestCase)
def extract_zip_after_upload(sender, instance, created, **kwargs):
    """
    Automatically extract ZIP files after upload.
    """
    
    if not created:
        return

    file_field = instance.file
    file_path = file_field.path  # Local path on disk
    # print("file_path",file_path)
    # Only proceed if it's a zip file
    if zipfile.is_zipfile(file_path):
        extract_to = os.path.join(os.path.dirname(file_path), "extracted")

        os.makedirs(extract_to, exist_ok=True)

        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

        print(f"✅ Extracted ZIP contents to: {extract_to}")
