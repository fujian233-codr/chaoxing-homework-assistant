import json
from pathlib import Path

from chaoxing_assistant.config_manager import DEFAULT_RULES
from chaoxing_assistant.models import Assignment, Course
from chaoxing_assistant.parsers import parse_assignments
from chaoxing_assistant.report import build_account_report
from chaoxing_assistant.service import run_account_check
from chaoxing_assistant.storage import Storage


FIXTURES = Path(__file__).parent / "fixtures"


class FakeClient:
    def __init__(self, courses: list[Course]):
        self.courses = courses

    def login(self) -> None:
        return None

    def get_courses(self, account_id: str) -> list[Course]:
        return self.courses

    def get_work_enc(self, course: Course) -> str:
        return "0123456789abcdef0123456789abcdef"

    def get_assignments(self, course: Course, enc: str, checked_at: str, max_pages: int) -> list[Assignment]:
        assignments, _ = parse_assignments(
            (FIXTURES / "work_list.html").read_text(encoding="utf-8"),
            course,
            checked_at=checked_at,
        )
        return assignments

    def get_assignment_detail(self, assignment: Assignment) -> str:
        return "请结合课程内容撰写报告，不少于1000字。"

    def polite_delay(self) -> None:
        return None


def test_full_offline_check_with_ai_pending(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("chaoxing_assistant.service.get_account_password", lambda _: "password")
    settings = {
        "accounts": [
            {
                "id": "me",
                "display_name": "我的账号",
                "username": "13800000000",
            }
        ],
        "archive_root": str(tmp_path / "archive"),
        "max_courses_per_account": 12,
        "request_timeout_seconds": 1,
        "max_retry": 0,
        "request_delay_min_seconds": 0,
        "request_delay_max_seconds": 0,
        "max_homework_pages": 1,
        "ai_allowed_courses": {"me": ["333"]},
    }
    course = Course("me", "333", "111", "222", "数据结构")
    storage = Storage(tmp_path / "state.sqlite3")
    result = run_account_check(
        settings=settings,
        account_id="me",
        storage=storage,
        client_override=FakeClient([course]),
    )
    assert result.ok, result.message
    assert len(result.courses) == 1
    assert len(result.assignments) == 3
    assert len(result.pending_ai) == 1
    assert result.pending_ai[0]["assignment_id"] == "1001"
    report = build_account_report(result, settings, DEFAULT_RULES)
    assert "社会实践报告" in report
    assert "待生成" in report
    assert storage.get_assignment("me", "1001") is not None
