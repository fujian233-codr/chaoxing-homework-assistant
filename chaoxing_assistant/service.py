from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from .ai_tasks import build_pending_tasks, classify_assignment_work
from .chaoxing_client import ChaoxingAuthError, ChaoxingClient, ChaoxingError
from .config_manager import get_account, load_settings
from .models import AccountResult, Assignment
from .secrets import get_account_password
from .storage import Storage
from .utils import timestamp


def select_courses(
    courses: list[Any],
    account: dict[str, Any],
    max_courses: int,
) -> tuple[list[Any], int]:
    active = [course for course in courses if course.active]
    configured = account.get("course_ids") or []
    if configured:
        wanted = {str(item) for item in configured}
        active = [course for course in active if str(course.course_id) in wanted]
    active.sort(key=lambda course: (course.end_date, course.name))
    selected = active[:max_courses]
    return selected, max(0, len(active) - len(selected))


def run_account_check(
    settings: dict[str, Any],
    account_id: str,
    storage: Storage | None = None,
    client_override: ChaoxingClient | None = None,
) -> AccountResult:
    storage = storage or Storage()
    account = get_account(settings, account_id)
    display_name = str(account.get("display_name") or account_id)
    username = str(account.get("username", ""))
    password = get_account_password(account_id)
    if not username or not password:
        return AccountResult(
            account_id=account_id,
            display_name=display_name,
            ok=False,
            message="缺少账号用户名或 Windows Credential Manager 密码",
        )

    try:
        client = client_override or ChaoxingClient(
            username=username,
            password=password,
            timeout=int(settings.get("request_timeout_seconds", 15)),
            max_retry=int(settings.get("max_retry", 2)),
            delay_range=(
                float(settings.get("request_delay_min_seconds", 0.8)),
                float(settings.get("request_delay_max_seconds", 1.5)),
            ),
        )
        client.login()
        all_courses = client.get_courses(account_id)
        selected, skipped = select_courses(
            all_courses, account, int(settings.get("max_courses_per_account", 12))
        )
        allowed_course_ids = list(settings.get("ai_allowed_courses", {}).get(account_id, []))
        allowed_set = {str(item) for item in allowed_course_ids}
        assignments: list[Assignment] = []
        checked_at = timestamp()

        for index, course in enumerate(selected):
            storage.upsert_course(course)
            enc = client.get_work_enc(course)
            course_assignments = client.get_assignments(
                course,
                enc=enc,
                checked_at=checked_at,
                max_pages=int(settings.get("max_homework_pages", 5)),
            )
            for assignment in course_assignments:
                updated = assignment
                if assignment.is_unsubmitted and str(course.course_id) in allowed_set:
                    try:
                        requirements = client.get_assignment_detail(assignment)
                        updated = replace(assignment, requirements=requirements)
                    except (ChaoxingError, ChaoxingAuthError):
                        updated = assignment
                    work_type, ai_eligible, ai_reason = classify_assignment_work(updated)
                    updated = replace(
                        updated,
                        work_type=work_type,
                        ai_eligible=ai_eligible,
                        ai_reason=ai_reason,
                    )
                else:
                    updated = replace(
                        assignment,
                        work_type="not_applicable",
                        ai_eligible=False,
                        ai_reason=(
                            "课程未标记允许AI"
                            if str(course.course_id) not in allowed_set
                            else "作业已提交"
                        ),
                    )
                assignments.append(updated)
            if index < len(selected) - 1:
                client.polite_delay()

        archive_root = Path(settings.get("archive_root", "作业归档"))
        pending = build_pending_tasks(
            assignments=[item for item in assignments if item.ai_eligible],
            courses=selected,
            allowed_course_ids=allowed_course_ids,
            archive_root=archive_root,
            account_name=display_name,
        )
        pending_outputs = {
            str(item["assignment_id"]): str(item["output_path"]) for item in pending
        }
        for assignment in assignments:
            storage.upsert_assignment(
                assignment,
                output_path=pending_outputs.get(str(assignment.assignment_id), ""),
            )
            if str(assignment.assignment_id) in pending_outputs:
                storage.record_ai_task(
                    account_id=account_id,
                    assignment_id=assignment.assignment_id,
                    status="pending_generation",
                    output_path=pending_outputs[str(assignment.assignment_id)],
                    draft_path="",
                )
        return AccountResult(
            account_id=account_id,
            display_name=display_name,
            ok=True,
            message="检查成功",
            courses=selected,
            assignments=assignments,
            skipped_courses=skipped,
            pending_ai=pending,
        )
    except ChaoxingAuthError as exc:
        return AccountResult(account_id=account_id, display_name=display_name, ok=False, message=str(exc))
    except ChaoxingError as exc:
        return AccountResult(account_id=account_id, display_name=display_name, ok=False, message=str(exc))
    except Exception as exc:
        return AccountResult(account_id=account_id, display_name=display_name, ok=False, message=f"未知错误：{exc}")


def check_accounts(
    account_ids: list[str] | None = None,
    settings_path: Path | None = None,
    storage: Storage | None = None,
) -> tuple[dict[str, Any], list[AccountResult], Storage]:
    settings = load_settings(settings_path or Path("config/settings.json"))
    storage = storage or Storage()
    configured_ids = [str(account["id"]) for account in settings.get("accounts", [])]
    selected_ids = account_ids or configured_ids
    unknown = [item for item in selected_ids if item not in configured_ids]
    if unknown:
        raise KeyError("未配置的账号：" + ", ".join(unknown))
    results = [run_account_check(settings, account_id, storage=storage) for account_id in selected_ids]
    run_id = str(uuid.uuid4())
    storage.record_run(
        run_id=run_id,
        mode="check",
        overall_ok=all(result.ok for result in results),
        account_results=[
            {
                "account_id": result.account_id,
                "ok": result.ok,
                "message": result.message,
                "course_count": len(result.courses),
                "assignment_count": len(result.assignments),
                "pending_ai_count": len(result.pending_ai),
            }
            for result in results
        ],
    )
    return settings, results, storage
