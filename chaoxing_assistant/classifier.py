from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CourseCategory:
    category: str
    priority: int


def classify_course(course_name: str, rules: dict[str, Any]) -> CourseCategory:
    fallback = rules.get("fallback", {"category": "其他", "priority": 0})
    for rule in rules.get("rules", []):
        pattern = str(rule.get("pattern", ""))
        if pattern and re.search(pattern, course_name, flags=re.IGNORECASE):
            return CourseCategory(str(rule.get("category", "其他")), int(rule.get("priority", 0)))
    return CourseCategory(str(fallback.get("category", "其他")), int(fallback.get("priority", 0)))
