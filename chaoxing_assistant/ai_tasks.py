from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import Assignment, Course
from .utils import sanitize_filename


TEXTUAL_KEYWORDS = re.compile(
    r"报告|论文|心得|总结|讨论|作文|案例分析|读后感|实践|观后感|调研|随笔|综述|演讲稿|策划书|说明书|文献",
    re.IGNORECASE,
)
OBJECTIVE_KEYWORDS = re.compile(
    r"测验|考试|选择|填空|判断|客观题|单选|多选|互评|投票|签到|随堂练习",
    re.IGNORECASE,
)


def classify_assignment_work(assignment: Assignment) -> tuple[str, bool, str]:
    text = f"{assignment.title}\n{assignment.requirements}"
    if OBJECTIVE_KEYWORDS.search(text):
        return "objective", False, "测验/客观题/互评类不生成"
    if TEXTUAL_KEYWORDS.search(assignment.title):
        return "text", True, "标题命中文本作业类型"
    if TEXTUAL_KEYWORDS.search(assignment.requirements):
        return "text", True, "作业要求命中文本作业类型"
    return "unknown", False, "无法确认作业类型，仅提醒"


def assignment_folder(root: Path, account_name: str, course: Course, assignment: Assignment) -> Path:
    return root / sanitize_filename(account_name) / sanitize_filename(course.name) / sanitize_filename(assignment.title)


def output_docx_path(
    root: Path,
    account_name: str,
    course: Course,
    assignment: Assignment,
    occupied: set[Path] | None = None,
) -> Path:
    folder = assignment_folder(root, account_name, course, assignment)
    base = sanitize_filename(assignment.title)
    path = folder / f"{base}.docx"
    occupied = occupied or set()
    if path.exists() or path in occupied:
        path = folder / f"{base}_{sanitize_filename(assignment.assignment_id, 24)}.docx"
    return path


def find_existing_archive(folder: Path) -> Path | None:
    if not folder.exists():
        return None
    files = [item for item in folder.rglob("*") if item.is_file() and item.suffix.lower() in {".docx", ".doc", ".pdf", ".md", ".txt"}]
    if not files:
        return None
    files.sort(key=lambda item: (item.stat().st_mtime, str(item)), reverse=True)
    return files[0]


def is_nonempty_docx(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def build_pending_tasks(
    assignments: list[Assignment],
    courses: list[Course],
    allowed_course_ids: list[str],
    archive_root: Path,
    account_name: str,
) -> list[dict[str, Any]]:
    allowed = {str(item) for item in allowed_course_ids}
    course_map = {course.course_id: course for course in courses}
    pending: list[dict[str, Any]] = []
    occupied: set[Path] = set()

    for assignment in assignments:
        if not assignment.is_unsubmitted:
            continue
        course = course_map.get(assignment.course_id)
        if not course:
            continue
        if str(course.course_id) not in allowed:
            continue
        existing = find_existing_archive(
            assignment_folder(archive_root, account_name, course, assignment)
        )
        if existing and existing.suffix.lower() == ".docx" and is_nonempty_docx(existing):
            continue
        output = output_docx_path(archive_root, account_name, course, assignment, occupied)
        occupied.add(output)
        if is_nonempty_docx(output):
            continue
        pending.append(
            {
                "assignment_id": assignment.assignment_id,
                "account_id": assignment.account_id,
                "account_name": account_name,
                "course_id": assignment.course_id,
                "course_name": assignment.course_name,
                "title": assignment.title,
                "status": assignment.status,
                "remaining_seconds": assignment.remaining_seconds,
                "remaining_text": assignment.remaining_text,
                "detail_url": assignment.detail_url,
                "requirements": assignment.requirements,
                "output_path": str(output.resolve()),
                "draft_path": str((Path("ai_drafts") / f"{assignment.assignment_id}.md").resolve()),
            }
        )
    return pending


def write_pending_file(items: list[dict[str, Any]], path: Path = Path("ai_pending.json")) -> Path:
    path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
