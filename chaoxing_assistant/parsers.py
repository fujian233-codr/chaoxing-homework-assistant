from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from .models import Assignment, Course


def parse_course_payload(account_id: str, payload: dict[str, Any]) -> list[Course]:
    courses: list[Course] = []
    if payload.get("result") not in (1, "1", None):
        raise ValueError(str(payload.get("msg") or "课程列表接口返回失败"))

    for channel in payload.get("channelList", []):
        content = channel.get("content", {})
        course_datas = content.get("course", {}).get("data", [])
        if not course_datas:
            continue
        course_data = course_datas[0]
        courses.append(
            Course(
                account_id=str(account_id),
                course_id=str(course_data.get("id", "")),
                class_id=str(content.get("id", "")),
                cpi=str(content.get("cpi", "")),
                name=str(course_data.get("name", "")).strip(),
                teacher=str(course_data.get("teacherfactor", "")).strip(),
                isretire=int(content.get("isretire", 0) or 0),
                end_date=str(content.get("endDate", "")).strip(),
            )
        )
    return [course for course in courses if course.course_id and course.class_id and course.cpi]


def parse_work_enc(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    element = soup.find(id="workEnc")
    if element and element.get("value"):
        return str(element["value"]).strip()
    match = re.search(r"enc=([a-fA-F0-9]{32})", html)
    return match.group(1) if match else None


def parse_remaining_seconds(text: str) -> int | None:
    if not text or "剩余" not in text:
        return None
    days = hours = minutes = seconds = 0
    day_match = re.search(r"(\d+)\s*天", text)
    hour_match = re.search(r"(\d+)\s*[小小]?时", text)
    minute_match = re.search(r"(\d+)\s*分", text)
    second_match = re.search(r"(\d+)\s*秒", text)
    if day_match:
        days = int(day_match.group(1))
    if hour_match:
        hours = int(hour_match.group(1))
    if minute_match:
        minutes = int(minute_match.group(1))
    if second_match:
        seconds = int(second_match.group(1))
    if not (day_match or hour_match or minute_match or second_match):
        return None
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _query_value(url: str, name: str) -> str:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get(name, [])
    return str(values[0]) if values else ""


def _parse_total_pages(soup: BeautifulSoup) -> int:
    numbers: list[int] = []
    for item in soup.select("#page li"):
        text = item.get_text(" ", strip=True)
        if text in {"上一页", "下一页"}:
            continue
        if text.isdigit():
            numbers.append(int(text))
    return max(numbers, default=1)


def parse_assignments(
    html: str,
    course: Course,
    checked_at: str = "",
) -> tuple[list[Assignment], int]:
    soup = BeautifulSoup(html, "html.parser")
    assignments: list[Assignment] = []
    seen: set[str] = set()

    for item in soup.select("li[data]"):
        detail_url = str(item.get("data", "")).strip()
        if not detail_url:
            continue
        assignment_id = _query_value(detail_url, "workId") or _query_value(detail_url, "jobId")
        if not assignment_id:
            continue
        if assignment_id in seen:
            continue
        seen.add(assignment_id)

        title_node = item.select_one(".overHidden2") or item.select_one(".title")
        status_node = item.select_one(".status")
        time_node = item.select_one(".time")
        title = (title_node.get("title") if title_node and title_node.get("title") else title_node.get_text(" ", strip=True) if title_node else "") or "未命名作业"
        status = status_node.get_text(" ", strip=True) if status_node else "未知"
        remaining_text = time_node.get_text(" ", strip=True) if time_node else ""
        assignments.append(
            Assignment(
                assignment_id=assignment_id,
                account_id=course.account_id,
                course_id=course.course_id,
                class_id=course.class_id,
                cpi=course.cpi,
                course_name=course.name,
                title=title,
                status=status,
                remaining_text=remaining_text,
                remaining_seconds=parse_remaining_seconds(remaining_text),
                detail_url=detail_url,
                checked_at=checked_at,
            )
        )
    return assignments, _parse_total_pages(soup)


def parse_assignment_detail(html: str, max_chars: int = 6000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for selector in (".noshow", "script", "style", "noscript"):
        for node in soup.select(selector):
            node.decompose()
    candidates: list[tuple[int, str]] = []
    for node in soup.select(".question, .homework, .work-detail, .detail, .content, .container"):
        text = node.get_text("\n", strip=True)
        if text:
            candidates.append((len(text), text))
    text = max(candidates, key=lambda pair: pair[0])[1] if candidates else soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars].strip()


def parse_deadline_from_detail(html: str) -> int | None:
    patterns = [
        r"截止[时间：:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2})",
        r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2})\s*截止",
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if not match:
            continue
        raw = match.group(1).replace("/", "-")
        try:
            from datetime import datetime

            value = datetime.strptime(raw, "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        from .utils import now_local

        return max(0, int((value - now_local().replace(tzinfo=None)).total_seconds()))
    return None


def load_course_fixture(path: str) -> list[Course]:
    from pathlib import Path

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_course_payload(payload.get("account_id", "fixture"), payload)
