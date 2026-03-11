import json
import logging
import os
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Load system test cases from XLSX into database."

    DEFAULT_XLSX = os.path.join(
        settings.MEDIA_ROOT, "system", "system_test_cases.xlsx"
    )

    TEST_TYPE_MAP = {
        "device": 2,
        "robot framework": 1,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--file", type=str, default=self.DEFAULT_XLSX,
            help="Path to XLSX file",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Preview without writing to DB",
        )
        parser.add_argument(
            "--force-update", action="store_true",
            help="Update existing system test cases",
        )
        parser.add_argument(
            "--skip-file-check", action="store_true",
            help="Skip checking if script files exist on disk",
        )
        parser.add_argument(
            "--admin-username", type=str, default=None,
            help="Superadmin username (default: first superuser)",
        )

    def handle(self, *args, **options):
        start_time = time.time()

        xlsx_path = options["file"]
        dry_run = options["dry_run"]
        force_update = options["force_update"]
        skip_file_check = options["skip_file_check"]
        admin_username = options["admin_username"]

        logger.info("load_system_test_cases started | file=%s", xlsx_path)

        if not os.path.exists(xlsx_path):
            self.stdout.write(self.style.WARNING(
                f"XLSX not found at '{xlsx_path}' — skipping."
            ))
            return

        try:
            import openpyxl
        except ImportError:
            raise CommandError("openpyxl is required: pip install openpyxl")

        from openwisp_test_management.swapper import load_model

        TestCategory = load_model("TestCategory")
        TestCase = load_model("TestCase")

        admin_user = self._get_admin_user(admin_username)
        self.stdout.write(f"Admin: {admin_user.username} (pk={admin_user.pk})")

        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if len(rows) < 2:
            self.stdout.write(self.style.WARNING("XLSX has no data rows."))
            return

        headers = [str(h).strip().lower() if h else "" for h in rows[0]]
        data_rows = rows[1:]

        required_cols = {"name", "test_case_id", "category_name", "description", "test_type"}
        missing = required_cols - set(headers)
        if missing:
            raise CommandError(f"Missing XLSX columns: {missing}")

        self.stdout.write(f"Processing {len(data_rows)} rows...")

        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
        error_details = []

        with transaction.atomic():
            sid = transaction.savepoint() if dry_run else None

            for row_idx, row_values in enumerate(data_rows, start=2):
                row = dict(zip(headers, row_values))

                if not any(row.values()):
                    continue

                test_case_id = str(row.get("test_case_id") or "").strip()
                if not test_case_id:
                    error_details.append(f"Row {row_idx}: empty test_case_id")
                    stats["errors"] += 1
                    continue

                try:
                    self._process_row(
                        row=row,
                        row_idx=row_idx,
                        admin_user=admin_user,
                        TestCategory=TestCategory,
                        TestCase=TestCase,
                        force_update=force_update,
                        skip_file_check=skip_file_check,
                        stats=stats,
                    )
                except Exception as exc:
                    msg = f"Row {row_idx} [{test_case_id}]: {exc}"
                    error_details.append(msg)
                    stats["errors"] += 1
                    logger.error("load_system_test_cases | %s", msg)

            if dry_run:
                transaction.savepoint_rollback(sid)

        elapsed = round(time.time() - start_time, 2)
        self._print_summary(stats, error_details, dry_run, elapsed)

    def _process_row(
        self, *, row, row_idx, admin_user,
        TestCategory, TestCase, force_update, skip_file_check, stats,
    ):
        test_case_id = str(row.get("test_case_id", "")).strip()
        name = str(row.get("name", "")).strip() or test_case_id
        category_name = str(row.get("category_name", "")).strip() or "Default Category"
        description = str(row.get("description", "")).strip()
        test_type_raw = str(row.get("test_type", "")).strip().lower()
        params_raw = row.get("params", None)
        is_file_raw = row.get("is_file_required", False)

        MAX_NAME_LEN = 50
        if len(name) > MAX_NAME_LEN:
            logger.warning(
                "load_system_test_cases | %s: name truncated (%d -> %d chars)",
                test_case_id, len(name), MAX_NAME_LEN,
            )
            name = name[:MAX_NAME_LEN]

        test_type = self.TEST_TYPE_MAP.get(test_type_raw)
        if test_type is None:
            raise ValueError(
                f"Unknown test_type '{test_type_raw}'. "
                f"Valid: {list(self.TEST_TYPE_MAP.keys())}"
            )

        params = self._parse_params(params_raw)

        if isinstance(is_file_raw, bool):
            is_config_push = is_file_raw
        else:
            is_config_push = str(is_file_raw).strip().upper() in ("TRUE", "1", "YES")

        category, cat_created = TestCategory.objects.get_or_create(
            name=category_name,
            defaults={
                "code": category_name.lower().replace(" ", "_")[:50],
                "description": category_name,
            },
        )
        if cat_created:
            logger.info("load_system_test_cases | Category created: %s", category_name)

        python_path, robot_path = self._resolve_script_paths(
            test_case_id=test_case_id,
            test_type=test_type,
            skip_file_check=skip_file_check,
        )

        existing = TestCase.objects.filter(test_case_id=test_case_id).first()

        if existing:
            if not force_update:
                stats["skipped"] += 1
                return

            existing.name = name
            existing.category = category
            existing.description = description
            existing.test_type = test_type
            existing.params = params
            existing.is_configuration_push_required = is_config_push
            existing.is_active = True
            existing.is_system_test_case = True
            existing.python_script = python_path
            existing.robot_script = robot_path if test_type == 1 else None
            existing.save()

            stats["updated"] += 1
            logger.info("load_system_test_cases | Updated: %s", test_case_id)
            return

        tc = TestCase()
        tc.name = name
        tc.test_case_id = test_case_id
        tc.category = category
        tc.description = description
        tc.test_type = test_type
        tc.params = params
        tc.is_configuration_push_required = is_config_push
        tc.is_active = True
        tc.is_system_test_case = True
        tc.created_by = admin_user
        tc.python_script = python_path
        tc.robot_script = robot_path if test_type == 1 else None
        tc.save()

        stats["created"] += 1
        logger.info("load_system_test_cases | Created: %s", test_case_id)

    def _resolve_script_paths(self, *, test_case_id, test_type, skip_file_check):
        python_path = None
        robot_path = None

        if test_type == 2:
            python_path = f"test_case/{test_case_id}.py"
        elif test_type == 1:
            python_path = f"test_case_robot/{test_case_id}.py"
            robot_path = f"test_case_robot/{test_case_id}.robot"

        if not skip_file_check:
            self._check_file_exists(python_path, "Python script", test_case_id)
            if robot_path:
                self._check_file_exists(robot_path, "Robot script", test_case_id)

        return python_path, robot_path

    def _check_file_exists(self, relative_path, label, test_case_id):
        if not relative_path:
            return
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        if not os.path.exists(full_path):
            logger.warning(
                "load_system_test_cases | %s missing for '%s': %s",
                label, test_case_id, full_path,
            )

    def _get_admin_user(self, username=None):
        if username:
            try:
                return User.objects.get(username=username, is_superuser=True)
            except User.DoesNotExist:
                raise CommandError(f"Superuser '{username}' not found.")

        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if not user:
            raise CommandError("No superuser exists.")
        return user

    def _parse_params(self, raw):
        if raw is None or raw == "":
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw or raw == "{}":
                return {}

            raw = raw.replace('\u201c', '"').replace('\u201d', '"')
            raw = raw.replace('\u2018', "'").replace('\u2019', "'")

            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("params must be a JSON object")
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(
                    "load_system_test_cases | Invalid JSON in params, "
                    "defaulting to empty dict. Error: %s", e.msg,
                )
                return {}
        return {}

    def _print_summary(self, stats, error_details, dry_run, elapsed):
        self.stdout.write("")
        self.stdout.write("=" * 50)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing saved"))

        self.stdout.write(f"  Created : {stats['created']}")
        self.stdout.write(f"  Updated : {stats['updated']}")
        self.stdout.write(f"  Skipped : {stats['skipped']}")
        self.stdout.write(f"  Errors  : {stats['errors']}")
        self.stdout.write(f"  Time    : {elapsed}s")
        self.stdout.write("=" * 50)

        if error_details:
            self.stdout.write(self.style.ERROR("Errors:"))
            for err in error_details:
                self.stdout.write(self.style.ERROR(f"  - {err}"))

        total = stats["created"] + stats["updated"] + stats["skipped"]
        logger.info(
            "load_system_test_cases | Done in %ss | "
            "created=%d updated=%d skipped=%d errors=%d total=%d",
            elapsed, stats["created"], stats["updated"],
            stats["skipped"], stats["errors"], total,
        )