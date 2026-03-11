import zipfile
import requests
from io import BytesIO
import os
import logging
from django.core.files.storage import default_storage
from django.conf import settings
from pathlib import Path

logger = logging.getLogger(__name__)

EXECUTOR_SERVER_IP = getattr(settings, "EXECUTOR_SERVER_IP", "http://172.17.0.1:8080")


def build_all_testcases_zip(queryset, include_media_test_case=True):
    main_zip_buffer = BytesIO()

    with zipfile.ZipFile(main_zip_buffer, "w", zipfile.ZIP_DEFLATED) as main_zip:

        device_zip_buffer = build_device_testcases_zip(queryset, include_media_test_case)
        if device_zip_buffer:
            main_zip.writestr("Device(NB).zip", device_zip_buffer.getvalue())
        else:
            logger.warning("Device(NB).zip is empty or failed")

        robot_zip_buffer = fetch_robot_framework_zip()
        if robot_zip_buffer:
            main_zip.writestr("Robot_Framework.zip", robot_zip_buffer.getvalue())
        else:
            logger.warning("Robot_Framework.zip fetch failed or empty")

    main_zip_buffer.seek(0)
    return main_zip_buffer


def build_device_testcases_zip(queryset, include_media_test_case=True):
    zip_buffer = BytesIO()
    file_count = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:

        if include_media_test_case:
            media_path = Path(default_storage.location) / "test_case"

            if not media_path.exists():
                logger.error(f"media/test_case directory not found: {media_path}")
                return zip_buffer

            for file_path in media_path.glob("*.py"):
                try:
                    with open(file_path, "rb") as f:
                        zip_file.writestr(f"Device/{file_path.name}", f.read())
                        file_count += 1
                except Exception as e:
                    logger.error(f"Failed to add {file_path}: {e}")

        else:
            for tc in queryset:
                test_case_id = (tc.test_case_id or "").strip()

                if not test_case_id:
                    logger.warning(f"Skipping TestCase {tc.pk}: missing test_case_id")
                    continue

                if tc.python_script and tc.test_type == 2:
                    python_name = tc.python_script.name

                    if default_storage.exists(python_name):
                        try:
                            ext = os.path.splitext(python_name)[1] or ".py"
                            filename = f"{test_case_id}{ext}"

                            with default_storage.open(python_name, "rb") as f:
                                zip_file.writestr(f"Device/{filename}", f.read())
                                file_count += 1

                        except Exception as e:
                            logger.error(f"Failed to add python script for {test_case_id}: {e}")
                    else:
                        logger.warning(f"Python script not found: {python_name}")

    zip_buffer.seek(0)
    logger.info(f"Device(NB).zip created with {file_count} files ({len(zip_buffer.getvalue())} bytes)")
    return zip_buffer


def fetch_robot_framework_zip():
    url = f"{EXECUTOR_SERVER_IP}/api/v1/export/test-cases"

    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "zip" not in content_type and "octet-stream" not in content_type:
            logger.warning(f"Unexpected Content-Type: {content_type}")

        zip_buffer = BytesIO(response.content)

        try:
            with zipfile.ZipFile(zip_buffer, 'r') as test_zip:
                logger.info(f"Received valid ZIP with {len(test_zip.namelist())} files")
        except zipfile.BadZipFile:
            logger.error("Received data is not a valid ZIP file")
            return None

        zip_buffer.seek(0)
        return zip_buffer

    except requests.Timeout:
        logger.error(f"Timeout fetching Robot Framework ZIP from {url}")
        return None

    except requests.ConnectionError as e:
        logger.error(f"Connection error to executor server: {e}")
        return None

    except requests.HTTPError as e:
        logger.error(f"HTTP error fetching Robot Framework ZIP: {e}")
        logger.error(f"Response status: {e.response.status_code}")
        logger.error(f"Response body: {e.response.text[:500]}")
        return None

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None

    except Exception as e:
        logger.error(f"Unexpected error fetching Robot Framework ZIP: {e}", exc_info=True)
        return None


def build_testcase_scripts_zip_old(queryset):
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:

        for tc in queryset:
            test_case_id = (tc.test_case_id or "").strip()

            if not test_case_id:
                logger.warning(f"Skipping TestCase {tc.pk}: missing test_case_id")
                continue

            folder_name = test_case_id

            if tc.robot_script and tc.test_type == 1:
                robot_name = tc.robot_script.name
                if default_storage.exists(robot_name):
                    ext = os.path.splitext(robot_name)[1] or ".robot"
                    with default_storage.open(robot_name, "rb") as f:
                        zip_file.writestr(f"{folder_name}/{folder_name}{ext}", f.read())

            if tc.python_script:
                python_name = tc.python_script.name
                if default_storage.exists(python_name):
                    ext = os.path.splitext(python_name)[1] or ".py"
                    with default_storage.open(python_name, "rb") as f:
                        zip_file.writestr(f"{folder_name}/{folder_name}{ext}", f.read())

        api_zip_buffer = fetch_robot_framework_zip()

        if api_zip_buffer:
            with zipfile.ZipFile(api_zip_buffer, "r") as api_zip:
                for member in api_zip.infolist():
                    if member.is_dir():
                        continue

                    filename = os.path.basename(member.filename)
                    if not filename:
                        continue

                    zip_file.writestr(f"api_bundle/{filename}", api_zip.read(member.filename))

    zip_buffer.seek(0)
    return zip_buffer