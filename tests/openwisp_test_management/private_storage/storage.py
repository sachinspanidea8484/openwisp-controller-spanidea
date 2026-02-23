from urllib.parse import urljoin
import os
from pathlib import Path
from private_storage.storage.files import PrivateFileSystemStorage
from django.core.files.storage import FileSystemStorage

from django.conf import settings

file_system_private_storage = PrivateFileSystemStorage(
    location= settings.TEST_SCRIPT_MEDIA_ROOT,
    base_url= settings.TEST_SCRIPT_MEDIA_URL
)

zip_storage = PrivateFileSystemStorage(
    location=settings.TEST_SCRIPT_MEDIA_ROOT_ZIP,
    base_url=settings.TEST_SCRIPT_MEDIA_URL
)


class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        if self.exists(name):
            self.delete(name)
        return name
