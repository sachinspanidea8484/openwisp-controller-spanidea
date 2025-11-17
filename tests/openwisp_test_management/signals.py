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

    file_path = instance.file.path  # Full uploaded zip path

    # Only extract if file is a valid ZIP
    if zipfile.is_zipfile(file_path):

        # Extract everything directly into: /opt/openwisp/media/test_case/
        extract_to = settings.TEST_SCRIPT_MEDIA_ROOT

        # Ensure folder exists
        os.makedirs(extract_to, exist_ok=True)

        # Extract
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

        print(f"✅ Extracted ZIP contents to: {extract_to}")
