from pathlib import Path

from chaoxing_assistant.ai_tasks import (
    build_pending_tasks,
    classify_assignment_work,
    output_docx_path,
)
from chaoxing_assistant.classifier import classify_course
from chaoxing_assistant.config_manager import DEFAULT_RULES
from chaoxing_assistant.models import Assignment, Course


def make_assignment(title: str, requirements: str = "", assignment_id: str = "1") -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        account_id="me",
        course_id="333",
        class_id="111",
        cpi="222",
        course_name="数据结构",
        title=title,
        status="未交",
        requirements=requirements,
    )


def test_course_classification() -> None:
    assert classify_course("数据结构", DEFAULT_RULES).category == "专业课"
    assert classify_course("形势与政策", DEFAULT_RULES).category == "通识公共"
    assert classify_course("神秘课程", DEFAULT_RULES).category == "其他"


def test_assignment_type_detection() -> None:
    assert classify_assignment_work(make_assignment("读书心得"))[0] == "text"
    assert classify_assignment_work(make_assignment("第四章测验"))[0] == "objective"
    assert classify_assignment_work(make_assignment("普通任务"))[0] == "unknown"


def test_build_pending_tasks_for_allowed_text_assignment(tmp_path: Path) -> None:
    course = Course("me", "333", "111", "222", "数据结构")
    assignment = make_assignment("实践报告", requirements="撰写报告", assignment_id="999")
    pending = build_pending_tasks([assignment], [course], ["333"], tmp_path, "我的账号")
    assert len(pending) == 1
    assert pending[0]["assignment_id"] == "999"
    assert pending[0]["output_path"].endswith(".docx")


def test_pending_skips_existing_docx(tmp_path: Path) -> None:
    course = Course("me", "333", "111", "222", "数据结构")
    assignment = make_assignment("实践报告", assignment_id="999")
    output = output_docx_path(tmp_path, "我的账号", course, assignment)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"not empty")
    assert build_pending_tasks([assignment], [course], ["333"], tmp_path, "我的账号") == []

