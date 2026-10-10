# 学习通作业检查、AI 初稿归档与企业微信提醒助手

这是一个 Windows 本地 Python 3.12 工具，用于检查多个学习通账号的未交作业，按截止时间生成企业微信纯文本提醒，并为显式标记的课程生成文本作业 Word 初稿。系统**不会提交学习通作业**。

## 功能

- 支持 2-5 个学生账号串行检查。
- 解析未交、待互评、待批阅、已完成等状态。
- 按剩余时间排序，标记 24 小时内截止作业。
- 使用企业微信群机器人 Webhook 发送纯文本报告。
- 学习通密码和企业微信 Webhook 保存在 Windows Credential Manager。
- 默认所有课程“仅提醒”；执行 `ai-allow` 后才允许生成文本作业初稿。
- 只为报告、论文、心得、总结、讨论、作文、案例分析、读后感、实践等文本类作业生成任务。
- 不处理测验、考试、选择、填空、判断、互评、投票、签到。
- Word 输出到：
  `作业归档\{账号显示名}\{课程名}\{作业标题}\{作业标题}.docx`

## 安装

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 初始化与配置

```powershell
.\.venv\Scripts\python.exe main.py init
```

编辑 `config/settings.json`：

```json
{
  "accounts": [
    {
      "id": "me",
      "display_name": "我的账号",
      "username": "手机号",
      "webhook_ref": "wecom_default"
    }
  ],
  "default_webhook_ref": "wecom_default"
}
```

保存敏感信息：

```powershell
.\.venv\Scripts\python.exe main.py set-secret account --account me
.\.venv\Scripts\python.exe main.py set-secret webhook --ref wecom_default
```

检查本地配置：

```powershell
.\.venv\Scripts\python.exe main.py doctor
```

如需实际验证学习通登录：

```powershell
.\.venv\Scripts\python.exe main.py doctor --live
```

## 课程与 AI 标记

```powershell
.\.venv\Scripts\python.exe main.py courses --account me
.\.venv\Scripts\python.exe main.py ai-allow --account me --course-id 123456
.\.venv\Scripts\python.exe main.py ai-forbid --account me --course-id 123456
```

标记只影响该账号该门课程。新课程默认仅提醒。

## 检查与通知

默认 dry-run，不发送企业微信：

```powershell
.\.venv\Scripts\python.exe main.py check
```

直接检查并发送企业微信：

```powershell
.\.venv\Scripts\python.exe main.py check --send
```

检查结果写入 `reports/{account_id}.txt`，AI 待生成任务写入 `ai_pending.json`。

推荐自动化流程为“先检查、再生成初稿、最后发送”，避免重复访问学习通：

```powershell
.\.venv\Scripts\python.exe main.py check
# 按 ai_pending.json 生成草稿并运行 build-docx
.\.venv\Scripts\python.exe main.py notify
```

## 生成 Word 初稿

`check` 生成 `ai_pending.json` 后，为其中的任务准备 UTF-8 Markdown 草稿，再执行：

```powershell
.\.venv\Scripts\python.exe main.py build-docx `
  --account me `
  --assignment-id 123456 `
  --draft ai_drafts\123456.md
```

如需覆盖已有非空 Word，添加 `--force`。生成后请自行审阅、修改并手动提交。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 风险与边界

- 学习通可能触发验证码或风控；本工具不会绕过验证码。
- 接口或页面结构变更后需要更新解析器。
- 单账号默认最多追踪 12 门有效课程，可通过 `max_courses_per_account` 调整，但不建议调高。
- AI 文件是初稿，提交前必须人工审阅。
- 本项目未复制 GPL 项目代码；如未来引入 GPL 代码，需要遵循相应许可证。
