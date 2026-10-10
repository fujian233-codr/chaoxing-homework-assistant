from __future__ import annotations

import time
from dataclasses import dataclass

import requests


MAX_BYTES_PER_MESSAGE = 1800


@dataclass(frozen=True)
class NotificationResult:
    ok: bool
    segments: int
    message: str


def split_text_for_wecom(text: str, max_bytes: int = MAX_BYTES_PER_MESSAGE) -> list[str]:
    if not text:
        return []
    segments: list[str] = []
    current = ""
    current_bytes = 0
    for char in text:
        char_size = len(char.encode("utf-8"))
        if current and current_bytes + char_size > max_bytes:
            segments.append(current)
            current = char
            current_bytes = char_size
        else:
            current += char
            current_bytes += char_size
    if current:
        segments.append(current)
    return segments


class WeComNotifier:
    def __init__(self, webhook: str, timeout: int = 15, max_retry: int = 2):
        if not webhook.startswith("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="):
            raise ValueError("企业微信 Webhook 格式不正确")
        self.webhook = webhook
        self.timeout = timeout
        self.max_retry = max_retry

    def send_text(self, text: str) -> NotificationResult:
        segments = split_text_for_wecom(text)
        if not segments:
            return NotificationResult(True, 0, "空消息未发送")
        for index, segment in enumerate(segments, start=1):
            payload = {
                "msgtype": "text",
                "text": {"content": segment},
            }
            last_error: Exception | None = None
            sent = False
            for attempt in range(self.max_retry + 1):
                if attempt:
                    time.sleep(min(2**attempt, 5))
                try:
                    response = requests.post(self.webhook, json=payload, timeout=self.timeout)
                    body = response.json()
                    if response.status_code == 200 and body.get("errcode") == 0:
                        sent = True
                        break
                    last_error = RuntimeError(
                        f"HTTP {response.status_code}, errcode={body.get('errcode')}, errmsg={body.get('errmsg')}"
                    )
                    if response.status_code < 500 and body.get("errcode") not in (-1, 42001):
                        break
                except (requests.RequestException, ValueError) as exc:
                    last_error = exc
            if not sent:
                return NotificationResult(
                    False,
                    index - 1,
                    f"第 {index}/{len(segments)} 段发送失败：{last_error}",
                )
        return NotificationResult(True, len(segments), "发送成功")
