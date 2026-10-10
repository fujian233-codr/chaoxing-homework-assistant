import json
from pathlib import Path

from chaoxing_assistant.models import Course
from chaoxing_assistant.parsers import (
    parse_assignments,
    parse_course_payload,
    parse_remaining_seconds,
    parse_work_enc,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_course_payload() -> None:
    payload = json.loads((FIXTURES / "course_payload.json").read_text(encoding="utf-8"))
    courses = parse_course_payload("me", payload)
    assert len(courses) == 2
    assert courses[0].course_id == "333"
    assert courses[0].class_id == "111"
    assert courses[0].cpi == "222"
    assert courses[0].active
    assert not courses[1].active


def test_parse_work_enc_from_input() -> None:
    assert parse_work_enc('<input id="workEnc" value="abc123def456abc123def456abc12345">') == "abc123def456abc123def456abc12345"
    assert parse_work_enc("location.href='?enc=0123456789abcdef0123456789abcdef'") == "0123456789abcdef0123456789abcdef"


def test_parse_assignments_and_remaining_time() -> None:
    course = Course("me", "333", "111", "222", "数据结构")
    assignments, pages = parse_assignments(
        (FIXTURES / "work_list.html").read_text(encoding="utf-8"),
        course,
    )
    assert pages == 1
    assert len(assignments) == 3
    first = assignments[0]
    assert first.title == "社会实践报告"
    assert first.is_unsubmitted
    assert first.remaining_seconds == 1 * 86400 + 2 * 3600 + 30 * 60
    assert assignments[1].status == "已完成"
    assert parse_remaining_seconds("剩余90小时37分钟") == 90 * 3600 + 37 * 60

