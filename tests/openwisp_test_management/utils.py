import zipfile
from io import BytesIO
import os
import logging
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def build_testcase_scripts_zip(queryset):
    """
    Creates a ZIP containing:
    <test_case_id>/
        <test_case_id>.robot
        <test_case_id>.py

    - Validates file existence
    - Skips missing files
    - Logs warnings instead of crashing
    """

    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for tc in queryset:
            test_case_id = (tc.test_case_id or "").strip()

            # ✅ Validate Test Case ID
            if not test_case_id:
                logger.warning(f"Skipping TestCase {tc.pk}: missing test_case_id")
                continue

            folder_name = test_case_id

            # ================= ROBOT SCRIPT =================
            if tc.robot_script and tc.test_type == 1:
                robot_name = tc.robot_script.name  # storage-relative path

                if default_storage.exists(robot_name):
                    ext = os.path.splitext(robot_name)[1] or ".robot"
                    zip_path = f"{folder_name}/{folder_name}{ext}"

                    with default_storage.open(robot_name, "rb") as f:
                        zip_file.writestr(zip_path, f.read())
                else:
                    logger.warning(
                        f"Robot script missing for TestCase {test_case_id}: {robot_name}"
                    )

            # ================= PYTHON SCRIPT =================
            if tc.python_script:
                python_name = tc.python_script.name

                if default_storage.exists(python_name):
                    ext = os.path.splitext(python_name)[1] or ".py"
                    zip_path = f"{folder_name}/{folder_name}{ext}"

                    with default_storage.open(python_name, "rb") as f:
                        zip_file.writestr(zip_path, f.read())
                else:
                    logger.warning(
                        f"Python script missing for TestCase {test_case_id}: {python_name}"
                    )

    zip_buffer.seek(0)
    return zip_buffer