# import zipfile
# import requests

# from io import BytesIO
# import os
# import logging
# from django.core.files.storage import default_storage

# logger = logging.getLogger(__name__)
# from .settings import EXECUTOR_SERVER_IP ,OPENWISP_SERVER_IP ,MEDIA_URL





# def build_testcase_scripts_zip(queryset):

#     zip_buffer = BytesIO()
 
#     with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
 
#         # ================= TEST CASE FILES =================

#         for tc in queryset:

#             test_case_id = (tc.test_case_id or "").strip()
 
#             if not test_case_id:

#                 logger.warning(f"Skipping TestCase {tc.pk}: missing test_case_id")

#                 continue
 
#             folder_name = test_case_id
 
#             if tc.robot_script and tc.test_type == 1:

#                 robot_name = tc.robot_script.name

#                 if default_storage.exists(robot_name):

#                     ext = os.path.splitext(robot_name)[1] or ".robot"

#                     with default_storage.open(robot_name, "rb") as f:

#                         zip_file.writestr(

#                             f"{folder_name}/{folder_name}{ext}", f.read()

#                         )
 
#             if tc.python_script:

#                 python_name = tc.python_script.name

#                 if default_storage.exists(python_name):

#                     ext = os.path.splitext(python_name)[1] or ".py"

#                     with default_storage.open(python_name, "rb") as f:

#                         zip_file.writestr(

#                             f"{folder_name}/{folder_name}{ext}", f.read()

#                         )
 
#         # ================= API BUNDLE (ROOT LEVEL) =================

#         api_zip_buffer = fetch_api_zip()
 
#         if api_zip_buffer:

#             with zipfile.ZipFile(api_zip_buffer, "r") as api_zip:

#                 for member in api_zip.infolist():

#                     if member.is_dir():

#                         continue
 
#                     # ✅ avoid directory traversal

#                     filename = os.path.basename(member.filename)

#                     if not filename:

#                         continue
 
#                     zip_file.writestr(

#                         f"api_bundle/{filename}",

#                         api_zip.read(member.filename)

#                     )
 
#     zip_buffer.seek(0)

#     return zip_buffer
 
 
# def fetch_api_zip():

#     url = f"${EXECUTOR_SERVER_IP}/"
    
 
#     try:

#         response = requests.get(url, timeout=30)

#         response.raise_for_status()
 
#         if "zip" not in response.headers.get("Content-Type", ""):

#             logger.warning("API did not return a ZIP file")

#             return None
 
#         return BytesIO(response.content)
 
#     except requests.RequestException as e:

#         logger.error(f"API ZIP fetch failed: {e}")

#         return None
 








# def build_testcase_scripts_zip_old(queryset):
#     """
#     Creates a ZIP containing:
#     <test_case_id>/
#         <test_case_id>.robot
#         <test_case_id>.py

#     - Validates file existence
#     - Skips missing files
#     - Logs warnings instead of crashing
#     """

#     zip_buffer = BytesIO()

#     with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
#         for tc in queryset:
#             test_case_id = (tc.test_case_id or "").strip()

#             # ✅ Validate Test Case ID
#             if not test_case_id:
#                 logger.warning(f"Skipping TestCase {tc.pk}: missing test_case_id")
#                 continue

#             folder_name = test_case_id

#             # ================= ROBOT SCRIPT =================
#             if tc.robot_script:
#                 robot_name = tc.robot_script.name  # storage-relative path

#                 if default_storage.exists(robot_name):
#                     ext = os.path.splitext(robot_name)[1] or ".robot"
#                     zip_path = f"{folder_name}/{folder_name}{ext}"

#                     with default_storage.open(robot_name, "rb") as f:
#                         zip_file.writestr(zip_path, f.read())
#                 else:
#                     logger.warning(
#                         f"Robot script missing for TestCase {test_case_id}: {robot_name}"
#                     )

#             # ================= PYTHON SCRIPT =================
#             if tc.python_script:
#                 python_name = tc.python_script.name

#                 if default_storage.exists(python_name):
#                     ext = os.path.splitext(python_name)[1] or ".py"
#                     zip_path = f"{folder_name}/{folder_name}{ext}"

#                     with default_storage.open(python_name, "rb") as f:
#                         zip_file.writestr(zip_path, f.read())
#                 else:
#                     logger.warning(
#                         f"Python script missing for TestCase {test_case_id}: {python_name}"
#                     )

#     zip_buffer.seek(0)
#     return zip_buffer



import zipfile
import requests
from io import BytesIO
import os
import logging
from django.core.files.storage import default_storage
from django.conf import settings
from pathlib import Path

logger = logging.getLogger(__name__)

# Configuration
EXECUTOR_SERVER_IP = getattr(
    settings, "EXECUTOR_SERVER_IP", "http://172.17.0.1:8080"
)


def build_all_testcases_zip(queryset, include_media_test_case=True):
    """
    Create All_TestCase.zip containing:
      - Device(NB).zip (from OpenWISP)
      - Robot_Framework.zip (from executor server)
    
    Args:
        queryset: Django queryset of test cases
        include_media_test_case: bool
            - True = Download ALL .py files from media/test_case/ (ignore database)
            - False = Download ONLY test cases from database (by test_case_id)
        
    Returns:
        BytesIO containing the complete zip
    """
    logger.info(f"Building All_TestCase.zip... (include_media_test_case={include_media_test_case})")
    
    # Main ZIP buffer
    main_zip_buffer = BytesIO()
    
    with zipfile.ZipFile(main_zip_buffer, "w", zipfile.ZIP_DEFLATED) as main_zip:
        
        # ================= 1. CREATE Device(NB).zip =================
        logger.info("Creating Device(NB).zip from OpenWISP test cases...")
        device_zip_buffer = build_device_testcases_zip(queryset, include_media_test_case)
        
        if device_zip_buffer:
            main_zip.writestr("Device(NB).zip", device_zip_buffer.getvalue())
            logger.info("✓ Added Device(NB).zip to main archive")
        else:
            logger.warning("⚠ Device(NB).zip is empty or failed")
        
        # ================= 2. FETCH Robot_Framework.zip =================
        logger.info("Fetching Robot_Framework.zip from executor server...")
        robot_zip_buffer = fetch_robot_framework_zip()
        
        if robot_zip_buffer:
            main_zip.writestr("Robot_Framework.zip", robot_zip_buffer.getvalue())
            logger.info("✓ Added Robot_Framework.zip to main archive")
        else:
            logger.warning("⚠ Robot_Framework.zip fetch failed or empty")
    
    main_zip_buffer.seek(0)
    logger.info(f"✓ All_TestCase.zip created successfully ({len(main_zip_buffer.getvalue())} bytes)")
    
    return main_zip_buffer


def build_device_testcases_zip(queryset, include_media_test_case=True):
    """
    Build Device(NB).zip containing ONLY Python files.
    
    Structure:
        Device(NB).zip/
            Device/
                test_case_001.py
                test_case_002.py
                test_case_003.py
    
    Args:
        queryset: Django queryset of test cases
        include_media_test_case: bool
            - True = Download ALL .py files from media/test_case/ directory
            - False = Download ONLY files matching test_case_id in database
        
    Returns:
        BytesIO containing Device(NB).zip
    """
    logger.info(f"Building Device(NB) test cases zip (include_media_test_case={include_media_test_case})...")
    
    zip_buffer = BytesIO()
    file_count = 0
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        if include_media_test_case:
            # TRUE: Download ALL .py files from media/test_case/ directory
            logger.info("Mode: Download ALL files from media/test_case/")
            
            media_path = Path(default_storage.location) / "test_case"
            
            if not media_path.exists():
                logger.error(f"media/test_case directory not found: {media_path}")
                return zip_buffer
            
            # Get all .py files from media/test_case/
            for file_path in media_path.glob("*.py"):
                try:
                    filename = file_path.name
                    
                    with open(file_path, "rb") as f:
                        zip_file.writestr(f"Device/{filename}", f.read())
                        file_count += 1
                        logger.debug(f"Added from media: Device/{filename}")
                
                except Exception as e:
                    logger.error(f"Failed to add {file_path}: {e}")
            
            logger.info(f"Added {file_count} files from media/test_case/")
        
        else:
            # FALSE: Download ONLY files matching database test_case_id
            logger.info("Mode: Download ONLY files matching database test_case_id")
            
            for tc in queryset:
                test_case_id = (tc.test_case_id or "").strip()
                
                if not test_case_id:
                    logger.warning(f"Skipping TestCase {tc.pk}: missing test_case_id")
                    continue
                
                # Check if python_script exists in database
                if tc.python_script and tc.test_type == 2:
                    python_name = tc.python_script.name
                    
                    if default_storage.exists(python_name):
                        try:
                            ext = os.path.splitext(python_name)[1] or ".py"
                            filename = f"{test_case_id}{ext}"
                            
                            with default_storage.open(python_name, "rb") as f:
                                file_path = f"Device/{filename}"
                                zip_file.writestr(file_path, f.read())
                                file_count += 1
                                logger.debug(f"Added from DB: {file_path}")
                        
                        except Exception as e:
                            logger.error(f"Failed to add python script for {test_case_id}: {e}")
                    else:
                        logger.warning(f"Python script not found: {python_name}")
            
            logger.info(f"Added {file_count} files matching database test_case_id")
    
    zip_buffer.seek(0)
    logger.info(f"✓ Device(NB).zip created with {file_count} files ({len(zip_buffer.getvalue())} bytes)")
    
    return zip_buffer
def fetch_robot_framework_zip():
    """
    Fetch Robot_Framework.zip from executor server.
    
    Calls: GET {EXECUTOR_SERVER_IP}/api/v1/export/test-cases
    
    Returns:
        BytesIO containing Robot_Framework.zip, or None if failed
    """
    url = f"{EXECUTOR_SERVER_IP}/api/v1/export/test-cases"
    
    logger.info(f"Fetching Robot Framework test cases from: {url}")
    
    try:
        response = requests.get(url, timeout=60)  # Increased timeout for large files
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        if "zip" not in content_type and "octet-stream" not in content_type:
            logger.warning(f"Unexpected Content-Type: {content_type}")
            # Still try to process as it might be a zip
        
        # Verify it's actually a zip file
        zip_buffer = BytesIO(response.content)
        
        # Test if it's a valid zip
        try:
            with zipfile.ZipFile(zip_buffer, 'r') as test_zip:
                file_list = test_zip.namelist()
                logger.info(f"✓ Received valid ZIP with {len(file_list)} files")
        except zipfile.BadZipFile:
            logger.error("Received data is not a valid ZIP file")
            return None
        
        zip_buffer.seek(0)
        logger.info(f"✓ Robot Framework ZIP fetched successfully ({len(response.content)} bytes)")
        
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


# ================= ALTERNATIVE: If you need the old function too =================

def build_testcase_scripts_zip_old(queryset):
    """
    OLD FUNCTION - Creates a single ZIP with test cases + api_bundle.
    Kept for backward compatibility.
    """
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        # ================= TEST CASE FILES =================
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
                        zip_file.writestr(
                            f"{folder_name}/{folder_name}{ext}", f.read()
                        )
            
            if tc.python_script:
                python_name = tc.python_script.name
                if default_storage.exists(python_name):
                    ext = os.path.splitext(python_name)[1] or ".py"
                    with default_storage.open(python_name, "rb") as f:
                        zip_file.writestr(
                            f"{folder_name}/{folder_name}{ext}", f.read()
                        )
        
        # ================= API BUNDLE (ROOT LEVEL) =================
        api_zip_buffer = fetch_robot_framework_zip()
        
        if api_zip_buffer:
            with zipfile.ZipFile(api_zip_buffer, "r") as api_zip:
                for member in api_zip.infolist():
                    if member.is_dir():
                        continue
                    
                    # Avoid directory traversal
                    filename = os.path.basename(member.filename)
                    if not filename:
                        continue
                    
                    zip_file.writestr(
                        f"api_bundle/{filename}",
                        api_zip.read(member.filename)
                    )
    
    zip_buffer.seek(0)
    return zip_buffer