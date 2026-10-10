import json
from pathlib import Path

import pytest

from chaoxing_assistant.config_manager import (
    DEFAULT_SETTINGS,
    load_settings,
    save_settings,
    set_course_ai_permission,
)
from chaoxing_assistant.docx_builder import build_docx_from_draft
from chaoxing_assistant.models import Assignment


def make_assignment() -> Assignment:
    return Assignment(
        assignment_id="999",
        account_id="me",
        course_id="333",
        class_id="111",
        cpi="222",
        course_name="数据结构",
        title="实践报告",
        status="未交",
        requirements="写一份报告",
    )


def test_ai_permission_persists(tmp_path: Path) -> None:
    settings = json.loads(json.dumps(DEFAULT_SETTINGS, ensure_ascii=False))
    settings["accounts"] = [{"id": "me", "display_name": "我", "username": "13800000000"}]
    path = tmp_path / "settings.json"
    save_settings(settings, path)
    loaded = load_settings(path)
    set_course_ai_permission(loaded, "me", "333", True)
    save_settings(loaded, path)
    assert load_settings(path)["ai_allowed_courses"]["me"] == ["333"]


def test_docx_generation_and_overwrite_protection(tmp_path: Path) -> None:
    assignment = make_assignment()
    draft = tmp_path / "draft.md"
    draft.write_text("# 标题\n\n- 第一点\n\n正文内容", encoding="utf-8")
    output = tmp_path / "out" / "实践报告.docx"
    build_docx_from_draft(assignment, draft, output)
    assert output.is_file() and output.stat().st_size > 0
    with pytest.raises(FileExistsError):
        build_docx_from_draft(assignment, draft, output)
    build_docx_from_draft(assignment, draft, output, force=True)
