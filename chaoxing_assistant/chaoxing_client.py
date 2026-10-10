from __future__ import annotations

import base64
import random
import time
from typing import Any
from urllib.parse import urljoin

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from requests import Session

from .models import Assignment, Course
from .parsers import parse_assignments, parse_assignment_detail, parse_course_payload, parse_work_enc


class ChaoxingError(RuntimeError):
    pass


class ChaoxingAuthError(ChaoxingError):
    pass


class ChaoxingClient:
    AES_KEY = b"u2oh6Vu^HWe4_AES"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        username: str,
        password: str,
        timeout: int = 15,
        max_retry: int = 2,
        delay_range: tuple[float, float] = (0.8, 1.5),
    ) -> None:
        self.username = username
        self.password = password
        self.timeout = timeout
        self.max_retry = max_retry
        self.delay_range = delay_range
        self.session = Session()
        self.session.headers.update(
            {
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            }
        )

    def _encrypt(self, value: str) -> str:
        data = value.encode("utf-8")
        padding = 16 - len(data) % 16
        data += bytes([padding]) * padding
        encryptor = Cipher(algorithms.AES(self.AES_KEY), modes.CBC(self.AES_KEY)).encryptor()
        encrypted = encryptor.update(data) + encryptor.finalize()
        return base64.b64encode(encrypted).decode("ascii")

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retry + 1):
            if attempt:
                time.sleep(min(2**attempt, 5))
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if response.status_code >= 500:
                    last_error = ChaoxingError(f"HTTP {response.status_code}")
                    continue
                return response
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
        raise ChaoxingError(f"请求失败：{url}，原因：{last_error}")

    @staticmethod
    def _looks_like_captcha(response: requests.Response) -> bool:
        if response.url and any(
            keyword in response.url.lower() for keyword in ("captcha", "verify", "validate")
        ):
            return True
        text = response.text[:3000].lower()
        return "验证码" in text or "图形验证" in text or "滑动验证" in text

    def login(self) -> None:
        response = self._request(
            "POST",
            "https://passport2.chaoxing.com/fanyalogin",
            data={
                "fid": "-1",
                "uname": self._encrypt(self.username),
                "password": self._encrypt(self.password),
                "refer": "https%3A%2F%2Fi.chaoxing.com",
                "t": True,
                "forbidotherlogin": 0,
                "validate": "",
                "doubleFactorLogin": 0,
                "independentId": 0,
            },
            headers={"Referer": "https://i.chaoxing.com/"},
        )
        if self._looks_like_captcha(response):
            raise ChaoxingAuthError("学习通要求验证码或触发风控，需要人工登录处理")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ChaoxingAuthError("学习通登录响应异常，可能需要人工验证") from exc
        if payload.get("status") is not True:
            message = str(payload.get("msg2") or payload.get("msg") or "账号或密码错误")
            raise ChaoxingAuthError(f"学习通登录失败：{message}")

    def get_courses(self, account_id: str) -> list[Course]:
        response = self._request(
            "GET",
            "https://mooc1-api.chaoxing.com/mycourse/backclazzdata",
            params={"view": "json", "rss": "1"},
            headers={"Referer": "https://i.chaoxing.com/"},
        )
        if self._looks_like_captcha(response):
            raise ChaoxingAuthError("读取课程时触发验证码或风控")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ChaoxingError("课程列表响应不是 JSON，登录态可能已失效") from exc
        return parse_course_payload(account_id, payload)

    def get_work_enc(self, course: Course) -> str:
        response = self._request(
            "GET",
            "https://mooc1.chaoxing.com/visit/stucoursemiddle",
            params={
                "courseid": course.course_id,
                "clazzid": course.class_id,
                "cpi": course.cpi,
                "ismooc2": "1",
                "v": "2",
            },
            headers={"Referer": "https://i.chaoxing.com/"},
            allow_redirects=True,
        )
        if self._looks_like_captcha(response):
            raise ChaoxingAuthError(f"读取课程 {course.name} 时触发验证码或风控")
        enc = parse_work_enc(response.text)
        if not enc:
            raise ChaoxingError(f"无法解析课程 {course.name} 的作业令牌")
        return enc

    def polite_delay(self) -> None:
        time.sleep(random.uniform(*self.delay_range))

    def get_assignments(
        self,
        course: Course,
        enc: str,
        checked_at: str,
        max_pages: int = 5,
    ) -> list[Assignment]:
        collected: list[Assignment] = []
        page = 1
        while page <= max_pages:
            response = self._request(
                "GET",
                "https://mooc1.chaoxing.com/mooc-ans/mooc2/work/list",
                params={
                    "courseId": course.course_id,
                    "classId": course.class_id,
                    "cpi": course.cpi,
                    "enc": enc,
                    "pageNum": page,
                },
                headers={"Referer": "https://mooc1.chaoxing.com/"},
            )
            if self._looks_like_captcha(response):
                raise ChaoxingAuthError(f"读取课程 {course.name} 作业时触发验证码或风控")
            assignments, total_pages = parse_assignments(response.text, course, checked_at=checked_at)
            collected.extend(assignments)
            if page >= total_pages:
                break
            page += 1
            self.polite_delay()
        return collected

    def get_assignment_detail(self, assignment: Assignment) -> str:
        if not assignment.detail_url:
            return ""
        url = urljoin("https://mooc1.chaoxing.com/", assignment.detail_url)
        response = self._request("GET", url, headers={"Referer": "https://mooc1.chaoxing.com/"})
        if self._looks_like_captcha(response):
            raise ChaoxingAuthError(f"读取作业 {assignment.title} 详情时触发验证码或风控")
        return parse_assignment_detail(response.text)
