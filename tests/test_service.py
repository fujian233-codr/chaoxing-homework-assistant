from pathlib import Path

from chaoxing_assistant.config_manager import DEFAULT_RULES
from chaoxing_assistant.models import AccountResult, Assignment, Course
from chaoxing_assistant.report import build_account_report
from chaoxing_assistant.service import select_courses


def test_select_courses_limits_active_courses() -> None:
    courses = [
        Course("me", str(index), "class", "cpi", f"课程{index}") for index in range(5)
    ]
    selected, skipped = select_courses(courses, {}, 2)
    assert len(selected) == 2
    assert skipped == 3


def test_failed_account_report_is_actionable() -> None:
    result = AccountResult("me", "我的账号", False, "学习通要求验证码")
    report = build_account_report(result, {"archive_root": "作业归档"}, DEFAULT_RULES)
    assert "检查失败" in report
    assert "验证码" in report


def test_unsubmitted_report_sorted_urgent_first() -> None:
    course = Course("me", "333", "111", "222", "数据结构")
    assignments = [
        Assignment("1", "me", "333", "111", "222", "数据结构", "作业一", "未交", remaining_seconds=86400 * 3),
        Assignment("2", "me", "333", "111", "222", "数据结构", "紧急作业", "未交", remaining_seconds=3600),
    ]
    result = AccountResult("me", "我的账号", True, assignments=assignments)
    report = build_account_report(result, {"archive_root": "作业归档"}, DEFAULT_RULES)
    assert report.index("紧急作业") < report.index("作业一")
    assert "24小时内截止" in report
