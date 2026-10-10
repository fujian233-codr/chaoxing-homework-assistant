from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .ai_tasks import write_pending_file
from .chaoxing_client import ChaoxingClient
from .config_manager import (
    SETTINGS_FILE,
    backup_settings,
    get_account,
    init_config,
    load_rules,
    load_settings,
    save_settings,
    set_course_ai_permission,
)
from .docx_builder import build_docx_command
from .notifier import WeComNotifier
from .report import build_account_report, save_report
from .secrets import get_account_password, get_webhook, set_account_password, set_webhook
from .service import check_accounts, run_account_check
from .storage import Storage
from .models import AccountResult


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def cmd_init(args: argparse.Namespace) -> int:
    settings_path, rules_path = init_config(force_examples=args.force_examples)
    print(f"配置已初始化：{settings_path.resolve()}")
    print(f"分类规则已初始化：{rules_path.resolve()}")
    print("下一步：编辑 config/settings.json 添加账号，然后运行 set-secret 配置密码和 Webhook。")
    return 0


def cmd_set_secret(args: argparse.Namespace) -> int:
    if args.kind == "account":
        password = getpass.getpass(f"请输入学习通账号 {args.account} 密码（输入不回显）：")
        if not password:
            print("密码不能为空。")
            return 2
        set_account_password(args.account, password)
        print(f"已保存账号密码：{args.account}")
        return 0

    webhook = getpass.getpass(f"请输入企业微信 Webhook {args.ref}（输入不回显）：")
    if not webhook.startswith("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="):
        print("Webhook 格式不正确。")
        return 2
    set_webhook(args.ref, webhook)
    print(f"已保存企业微信 Webhook：{args.ref}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    settings = load_settings(Path(args.settings))
    problems: list[str] = []
    accounts = settings.get("accounts", [])
    print(f"版本：{__version__}")
    print(f"配置文件：{Path(args.settings).resolve()}")
    print(f"账号数量：{len(accounts)}")
    if not accounts:
        problems.append("尚未配置账号")
    if len({account.get("id") for account in accounts}) != len(accounts):
        problems.append("存在重复账号 ID")
    for account in accounts:
        account_id = str(account.get("id", ""))
        if not account_id or not account.get("username"):
            problems.append(f"账号 {account_id} 缺少 id 或 username")
        if not get_account_password(account_id):
            problems.append(f"账号 {account_id} 未配置密码")
    webhook_ref = str(settings.get("default_webhook_ref", ""))
    if not get_webhook(webhook_ref):
        problems.append(f"企业微信 Webhook {webhook_ref} 未配置")
    try:
        load_rules(Path(args.rules))
        print("分类规则：正常")
    except Exception as exc:
        problems.append(f"分类规则异常：{exc}")
    try:
        Storage()
        print("SQLite 状态库：正常")
    except Exception as exc:
        problems.append(f"SQLite 异常：{exc}")

    if args.live and accounts:
        for account in accounts:
            account_id = str(account["id"])
            password = get_account_password(account_id)
            if not password:
                continue
            try:
                client = ChaoxingClient(str(account["username"]), password)
                client.login()
                print(f"学习通登录：{account_id} 正常")
            except Exception as exc:
                problems.append(f"学习通登录 {account_id} 失败：{exc}")

    if problems:
        print("发现问题：")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("doctor 检查通过。")
    return 0


def cmd_courses(args: argparse.Namespace) -> int:
    settings = load_settings(Path(args.settings))
    account = get_account(settings, args.account)
    password = get_account_password(args.account)
    if not password:
        print("请先运行 set-secret account 配置学习通密码。")
        return 2
    client = ChaoxingClient(str(account["username"]), password)
    client.login()
    courses = client.get_courses(args.account)
    allowed = set(settings.get("ai_allowed_courses", {}).get(args.account, []))
    storage = Storage()
    for course in courses:
        storage.upsert_course(course)
    print("course_id\t状态\tAI\t课程名\t老师\t结束时间")
    for course in courses:
        status = "有效" if course.active else "已结课/归档"
        ai_status = "允许" if str(course.course_id) in allowed else "仅提醒"
        print(
            f"{course.course_id}\t{status}\t{ai_status}\t"
            f"{course.name}\t{course.teacher}\t{course.end_date}"
        )
    return 0


def _update_ai_permission(args: argparse.Namespace, allowed: bool) -> int:
    settings_path = Path(args.settings)
    settings = load_settings(settings_path)
    try:
        get_account(settings, args.account)
    except KeyError as exc:
        print(exc)
        return 2
    backup = backup_settings(settings_path)
    if backup:
        print(f"已备份配置：{backup}")
    settings = set_course_ai_permission(settings, args.account, args.course_id, allowed)
    save_settings(settings, settings_path)
    state = "允许AI生成文本作业初稿" if allowed else "仅提醒"
    print(f"课程 {args.course_id} 已设置为：{state}")
    return 0


def cmd_ai_allow(args: argparse.Namespace) -> int:
    return _update_ai_permission(args, True)


def cmd_ai_forbid(args: argparse.Namespace) -> int:
    return _update_ai_permission(args, False)


def cmd_check(args: argparse.Namespace) -> int:
    settings, results, _ = check_accounts(
        account_ids=args.account or None,
        settings_path=Path(args.settings),
    )
    rules = load_rules(Path(args.rules))
    pending_all: list[dict] = []
    for result in results:
        report = build_account_report(result, settings, rules)
        report_path = save_report(result.account_id, report)
        pending_all.extend(result.pending_ai)
        print("\n" + report)
        print(f"报告文件：{report_path.resolve()}")
        if args.send:
            account = get_account(settings, result.account_id)
            webhook_ref = str(account.get("webhook_ref") or settings.get("default_webhook_ref", ""))
            webhook = get_webhook(webhook_ref)
            if not webhook:
                print(f"企业微信发送失败：Webhook {webhook_ref} 未配置")
                continue
            try:
                notification = WeComNotifier(webhook).send_text(report)
                status = "成功" if notification.ok else "失败"
                print(f"企业微信发送：{status}（{notification.segments} 段，{notification.message}）")
            except Exception as exc:
                print(f"企业微信发送失败：{exc}")

    pending_path = write_pending_file(pending_all)
    print(f"\nAI待生成任务：{len(pending_all)} 个，文件：{pending_path.resolve()}")
    if not args.send:
        print("当前为 dry-run，未发送企业微信。")
    return 0 if all(result.ok for result in results) else 1


def cmd_build_docx(args: argparse.Namespace) -> int:
    storage = Storage()
    output = build_docx_command(
        storage=storage,
        account_id=args.account,
        assignment_id=args.assignment_id,
        draft_path=Path(args.draft),
        output_path=Path(args.output) if args.output else None,
        force=args.force,
    )
    print(f"Word 初稿已生成：{output.resolve()}")
    print("请自行审阅、修改并手动提交；系统不会提交学习通作业。")
    return 0


def cmd_notify(args: argparse.Namespace) -> int:
    settings = load_settings(Path(args.settings))
    rules = load_rules(Path(args.rules))
    storage = Storage()
    configured_ids = [str(account["id"]) for account in settings.get("accounts", [])]
    selected_ids = args.account or configured_ids
    unknown = [item for item in selected_ids if item not in configured_ids]
    if unknown:
        print("未配置的账号：" + ", ".join(unknown))
        return 2

    all_ok = True
    for account_id in selected_ids:
        account = get_account(settings, account_id)
        status = storage.latest_account_status(account_id)
        if not status:
            print(f"账号 {account_id} 尚无检查记录，请先运行 check。")
            all_ok = False
            continue
        result = AccountResult(
            account_id=account_id,
            display_name=str(account.get("display_name") or account_id),
            ok=bool(status["ok"]),
            message=str(status.get("message", "")),
            assignments=storage.latest_assignments(account_id),
        )
        report = build_account_report(result, settings, rules)
        report_path = save_report(account_id, report)
        print("\n" + report)
        print(f"报告文件：{report_path.resolve()}")
        webhook_ref = str(account.get("webhook_ref") or settings.get("default_webhook_ref", ""))
        webhook = get_webhook(webhook_ref)
        if not webhook:
            print(f"企业微信发送失败：Webhook {webhook_ref} 未配置")
            all_ok = False
            continue
        notification = WeComNotifier(webhook).send_text(report)
        state = "成功" if notification.ok else "失败"
        print(f"企业微信发送：{state}（{notification.segments} 段，{notification.message}）")
        all_ok = all_ok and notification.ok
    return 0 if all_ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chaoxing-assistant",
        description="学习通未交作业检查、AI 文本初稿归档与企业微信提醒工具",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化配置文件")
    init_parser.add_argument("--force-examples", action="store_true", help="覆盖示例配置")
    init_parser.set_defaults(func=cmd_init)

    secret_parser = subparsers.add_parser("set-secret", help="保存敏感信息到 Windows Credential Manager")
    secret_subparsers = secret_parser.add_subparsers(dest="kind", required=True)
    account_secret = secret_subparsers.add_parser("account", help="保存学习通密码")
    account_secret.add_argument("--account", required=True, help="settings.json 中的账号 ID")
    account_secret.set_defaults(func=cmd_set_secret)
    webhook_secret = secret_subparsers.add_parser("webhook", help="保存企业微信 Webhook")
    webhook_secret.add_argument("--ref", required=True, help="Webhook 引用名")
    webhook_secret.set_defaults(func=cmd_set_secret)

    doctor_parser = subparsers.add_parser("doctor", help="检查本地配置")
    doctor_parser.add_argument("--settings", default=str(SETTINGS_FILE))
    doctor_parser.add_argument("--rules", default="config/classification_rules.json")
    doctor_parser.add_argument("--live", action="store_true", help="实际尝试学习通登录")
    doctor_parser.set_defaults(func=cmd_doctor)

    courses_parser = subparsers.add_parser("courses", help="列出学习通课程")
    courses_parser.add_argument("--account", required=True)
    courses_parser.add_argument("--settings", default=str(SETTINGS_FILE))
    courses_parser.set_defaults(func=cmd_courses)

    allow_parser = subparsers.add_parser("ai-allow", help="标记课程允许生成文本作业初稿")
    allow_parser.add_argument("--account", required=True)
    allow_parser.add_argument("--course-id", required=True)
    allow_parser.add_argument("--settings", default=str(SETTINGS_FILE))
    allow_parser.set_defaults(func=cmd_ai_allow)

    forbid_parser = subparsers.add_parser("ai-forbid", help="取消课程AI生成标记")
    forbid_parser.add_argument("--account", required=True)
    forbid_parser.add_argument("--course-id", required=True)
    forbid_parser.add_argument("--settings", default=str(SETTINGS_FILE))
    forbid_parser.set_defaults(func=cmd_ai_forbid)

    check_parser = subparsers.add_parser("check", help="检查未交作业")
    check_parser.add_argument("--send", action="store_true", help="发送企业微信报告")
    check_parser.add_argument("--account", action="append", help="指定账号，可重复；默认全部账号")
    check_parser.add_argument("--settings", default=str(SETTINGS_FILE))
    check_parser.add_argument("--rules", default="config/classification_rules.json")
    check_parser.set_defaults(func=cmd_check)

    docx_parser = subparsers.add_parser("build-docx", help="把 UTF-8 草稿生成 Word 初稿")
    docx_parser.add_argument("--account", required=True)
    docx_parser.add_argument("--assignment-id", required=True)
    docx_parser.add_argument("--draft", required=True)
    docx_parser.add_argument("--output")
    docx_parser.add_argument("--force", action="store_true", help="覆盖已存在的非空 Word")
    docx_parser.set_defaults(func=cmd_build_docx)

    notify_parser = subparsers.add_parser("notify", help="基于最新检查结果发送企业微信报告")
    notify_parser.add_argument("--account", action="append", help="指定账号，可重复；默认全部账号")
    notify_parser.add_argument("--settings", default=str(SETTINGS_FILE))
    notify_parser.add_argument("--rules", default="config/classification_rules.json")
    notify_parser.set_defaults(func=cmd_notify)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\n已取消。")
        return 130
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
