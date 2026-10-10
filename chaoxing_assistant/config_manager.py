from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .utils import timestamp


SETTINGS_FILE = Path("config/settings.json")
RULES_FILE = Path("config/classification_rules.json")
EXAMPLE_SETTINGS = Path("config/settings.example.json")
EXAMPLE_RULES = Path("config/classification_rules.example.json")


DEFAULT_SETTINGS: dict[str, Any] = {
    "accounts": [],
    "default_webhook_ref": "wecom_default",
    "archive_root": "作业归档",
    "max_courses_per_account": 12,
    "request_delay_min_seconds": 0.8,
    "request_delay_max_seconds": 1.5,
    "request_timeout_seconds": 15,
    "max_retry": 2,
    "max_homework_pages": 5,
    "ai_policy": {
        "enabled": True,
        "disclosure_required": False,
        "scope": "marked_courses_text_assignments",
        "confirmed_by_user": True,
        "confirmed_at": "2026-10-10",
        "note": "用户确认课程允许AI生成且无需披露；系统仅对显式标记课程生成文本作业初稿。",
    },
    "ai_allowed_courses": {},
}


DEFAULT_RULES: dict[str, Any] = {
    "rules": [
        {
            "pattern": "数据结构|算法|操作系统|计算机组成|数据库|计算机网络|编译原理|软件工程|机器学习|深度学习|人工智能|程序设计|离散数学|数值分析|信息安全|密码学",
            "category": "专业课",
            "priority": 2,
        },
        {
            "pattern": "马克思|毛概|思想|形势与政策|思政|军事理论|心理健康|体育|大学英语|英语|就业|创业|美育|劳动教育|安全教育|通识|素养",
            "category": "通识公共",
            "priority": 1,
        },
    ],
    "fallback": {"category": "其他", "priority": 0},
}


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(default, ensure_ascii=False))
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def load_settings(path: Path = SETTINGS_FILE) -> dict[str, Any]:
    settings = _read_json(path, DEFAULT_SETTINGS)
    merged = json.loads(json.dumps(DEFAULT_SETTINGS, ensure_ascii=False))
    merged.update(settings)
    return merged


def save_settings(settings: dict[str, Any], path: Path = SETTINGS_FILE) -> None:
    _write_json_atomic(path, settings)


def load_rules(path: Path = RULES_FILE) -> dict[str, Any]:
    rules = _read_json(path, DEFAULT_RULES)
    if "rules" not in rules or "fallback" not in rules:
        raise ValueError(f"分类规则文件格式不正确：{path}")
    return rules


def init_config(force_examples: bool = False) -> tuple[Path, Path]:
    if not EXAMPLE_SETTINGS.exists() or force_examples:
        _write_json_atomic(EXAMPLE_SETTINGS, DEFAULT_SETTINGS)
    if not EXAMPLE_RULES.exists() or force_examples:
        _write_json_atomic(EXAMPLE_RULES, DEFAULT_RULES)

    if not SETTINGS_FILE.exists():
        _write_json_atomic(SETTINGS_FILE, DEFAULT_SETTINGS)
    if not RULES_FILE.exists():
        _write_json_atomic(RULES_FILE, DEFAULT_RULES)
    return SETTINGS_FILE, RULES_FILE


def backup_settings(path: Path = SETTINGS_FILE) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"settings.backup-{timestamp().replace(':', '')}.json")
    shutil.copy2(path, backup)
    return backup


def get_account(settings: dict[str, Any], account_id: str) -> dict[str, Any]:
    for account in settings.get("accounts", []):
        if account.get("id") == account_id:
            return account
    raise KeyError(f"找不到账号配置：{account_id}")


def set_course_ai_permission(
    settings: dict[str, Any], account_id: str, course_id: str, allowed: bool
) -> dict[str, Any]:
    get_account(settings, account_id)
    course_id = str(course_id)
    permissions: dict[str, list[str]] = settings.setdefault("ai_allowed_courses", {})
    current = list(permissions.get(account_id, []))
    if allowed:
        if course_id not in current:
            current.append(course_id)
    else:
        current = [item for item in current if item != course_id]
    permissions[account_id] = current
    return settings

