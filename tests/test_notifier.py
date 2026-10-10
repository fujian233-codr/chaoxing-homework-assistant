import pytest

from chaoxing_assistant.notifier import NotificationResult, WeComNotifier, split_text_for_wecom


def test_split_by_utf8_bytes() -> None:
    text = "中" * 1000 + "a" * 100
    segments = split_text_for_wecom(text)
    assert len(segments) > 1
    assert all(len(segment.encode("utf-8")) <= 1800 for segment in segments)
    assert "".join(segments) == text


def test_wecom_notifier_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status_code = 200

        def json(self):
            return {"errcode": 0, "errmsg": "ok"}

    monkeypatch.setattr("chaoxing_assistant.notifier.requests.post", lambda *args, **kwargs: Response())
    result = WeComNotifier("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test").send_text("hello")
    assert result == NotificationResult(True, 1, "发送成功")


def test_wecom_notifier_rejects_invalid_url() -> None:
    with pytest.raises(ValueError):
        WeComNotifier("https://example.com/hook")

