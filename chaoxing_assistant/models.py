from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Course:
    account_id: str
    course_id: str
    class_id: str
    cpi: str
    name: str
    teacher: str = ""
    isretire: int = 0
    end_date: str = ""

    @property
    def active(self) -> bool:
        return self.isretire == 0

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Assignment:
    assignment_id: str
    account_id: str
    course_id: str
    class_id: str
    cpi: str
    course_name: str
    title: str
    status: str
    remaining_text: str = ""
    remaining_seconds: int | None = None
    detail_url: str = ""
    requirements: str = ""
    work_type: str = "unknown"
    ai_eligible: bool = False
    ai_reason: str = "课程未标记允许AI"
    output_path: str = ""
    checked_at: str = ""

    @property
    def is_unsubmitted(self) -> bool:
        return "未交" in self.status or "未提交" in self.status

    @property
    def urgent(self) -> bool:
        return self.remaining_seconds is not None and 0 <= self.remaining_seconds <= 24 * 3600


@dataclass
class AccountResult:
    account_id: str
    display_name: str
    ok: bool
    message: str = ""
    courses: list[Course] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    skipped_courses: int = 0
    pending_ai: list[dict[str, Any]] = field(default_factory=list)
