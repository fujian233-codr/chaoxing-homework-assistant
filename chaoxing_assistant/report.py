from __future__ import annotations

from pathlib import Path
from typing import Any

from .ai_tasks import assignment_folder, find_existing_archive
from .classifier import classify_course
from .models import AccountResult, Assignment
from .utils import now_local


def format_remaining(seconds: int | None, fallback: str = "未知") -> str:
    if seconds is None:
        return fallback or "未知"
    if seconds <= 0:
        return "已截止/待确认"
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days}天{hours}小时"
    if hours:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


def _assignment_sort_key(assignment: Assignment) -> tuple[int, int, str]:
    remaining = assignment.remaining_seconds
    if remaining is None:
        return (2, 10**12, assignment.title)
    return (0 if assignment.urgent else 1, remaining, assignment.title)


def build_account_report(
    result: AccountResult,
    settings: dict[str, Any],
    rules: dict[str, Any],
) -> str:
    checked_at = now_local().strftime("%Y-%m-%d %H:%M")
    lines = [f"【学习通作业汇总】账号：{result.display_name}", f"检查时间：{checked_at}"]
    if not result.ok:
        lines.extend(["", f"检查失败：{result.message}", "请人工登录学习通或稍后重试。"])
        return "\n".join(lines)

    archive_root = Path(settings.get("archive_root", "作业归档"))
    unsubmitted = sorted(
        [assignment for assignment in result.assignments if assignment.is_unsubmitted],
        key=_assignment_sort_key,
    )
    lines.append(f"未交作业：{len(unsubmitted)} 个")
    if result.skipped_courses:
        lines.append(f"提示：为降低风控风险，已跳过 {result.skipped_courses} 门课程。")
    if not unsubmitted:
        lines.append("当前未发现未交作业，继续保持。")
    else:
        pending_map = {str(item.get("assignment_id")): item for item in result.pending_ai}
        allowed_courses = set(settings.get("ai_allowed_courses", {}).get(result.account_id, []))
        for index, assignment in enumerate(unsubmitted, start=1):
            category = classify_course(assignment.course_name, rules)
            urgent_mark = "【24小时内截止】" if assignment.urgent else ""
            lines.extend(
                [
                    "",
                    f"{index}. {urgent_mark}{assignment.course_name} / {assignment.title}",
                    f"分类：{category.category}｜状态：{assignment.status}｜剩余：{format_remaining(assignment.remaining_seconds, assignment.remaining_text)}",
                ]
            )
            folder = assignment_folder(archive_root, result.display_name, _course_from_assignment(assignment), assignment)
            existing = find_existing_archive(folder)
            if assignment.assignment_id in pending_map:
                lines.append(f"AI初稿：待生成｜计划路径：{pending_map[assignment.assignment_id]['output_path']}")
            elif existing:
                lines.append(f"AI初稿/本地归档：{str(existing.resolve())}")
            elif str(assignment.course_id) in allowed_courses and assignment.work_type == "text":
                lines.append("AI初稿：本次未能生成，请查看运行日志")
            else:
                lines.append("AI初稿：不适用（课程未标记或作业类型待确认）")
                if not existing:
                    lines.append("本地归档：未找到")
    lines.extend(["", "说明：AI文件仅为初稿，请自行审阅修改后手动提交。"])
    return "\n".join(lines)


def _course_from_assignment(assignment: Assignment):
    from .models import Course

    return Course(
        account_id=assignment.account_id,
        course_id=assignment.course_id,
        class_id=assignment.class_id,
        cpi=assignment.cpi,
        name=assignment.course_name,
    )


def save_report(account_id: str, content: str) -> Path:
    directory = Path("reports")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{account_id}.txt"
    path.write_text(content + "\n", encoding="utf-8")
    return path
