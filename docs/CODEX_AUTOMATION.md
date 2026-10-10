# Codex 自动化部署指南

这份指南面向把仓库 clone 到自己 Windows 电脑、并希望在 Codex App 里配置每晚自动检查的同学。每个人只配置自己的学习通账号和企业微信机器人；不要把自己的密码或 Webhook 发给他人。

## 1. 你需要准备什么

- Windows 10/11
- Python 3.12
- Git
- Codex App，并登录自己的账号
- 学习通学生账号
- 一个企业微信群机器人 Webhook
- 本机在计划时间保持开机、联网、Codex App 可运行

> 重要边界：本工具只检查作业、生成文本作业初稿并发送提醒，不会自动提交学习通作业，也不会绕过验证码或风控。使用者需要自行确认相关课程允许 AI 辅助生成，并遵守学校、老师和平台规则。

## 2. Clone 并安装环境

```powershell
git clone https://github.com/fujian233-codr/chaoxing-homework-assistant.git
Set-Location .\chaoxing-homework-assistant

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe main.py init
```

如果 `python` 默认指向旧版本，例如 Python 2.7，请始终使用 `py -3.12` 创建虚拟环境，后续命令使用 `.\.venv\Scripts\python.exe`。

## 3. 配置账号

编辑：

```text
config/settings.json
```

单账号示例：

```json
{
  "accounts": [
    {
      "id": "me",
      "display_name": "我的账号",
      "username": "学习通手机号",
      "webhook_ref": "wecom_default"
    }
  ],
  "default_webhook_ref": "wecom_default"
}
```

多账号示例：

```json
{
  "accounts": [
    {
      "id": "a1",
      "display_name": "账号一",
      "username": "手机号一",
      "webhook_ref": "wecom_default"
    },
    {
      "id": "a2",
      "display_name": "账号二",
      "username": "手机号二",
      "webhook_ref": "wecom_default"
    }
  ],
  "default_webhook_ref": "wecom_default"
}
```

`config/settings.json` 已被 `.gitignore` 忽略，不会被提交。不要把手机号、密码或 Webhook 写进 `settings.example.json`。

## 4. 保存学习通密码和企业微信 Webhook

学习通密码：

```powershell
.\.venv\Scripts\python.exe main.py set-secret account --account me
```

多账号时分别执行：

```powershell
.\.venv\Scripts\python.exe main.py set-secret account --account a1
.\.venv\Scripts\python.exe main.py set-secret account --account a2
```

企业微信 Webhook：

```powershell
.\.venv\Scripts\python.exe main.py set-secret webhook --ref wecom_default
```

输入不会回显。这些值保存在当前 Windows 用户的 Credential Manager 中，不会进入 Git。不要在公共电脑或他人可长期使用的账号下保存。

## 5. 首次自检

先做本地配置检查：

```powershell
.\.venv\Scripts\python.exe main.py doctor
```

再尝试真实登录：

```powershell
.\.venv\Scripts\python.exe main.py doctor --live
```

如果提示验证码、风控或异地登录验证，请先在浏览器手动登录学习通并完成校验。不要要求工具绕过验证码。

## 6. 获取课程 ID 并标记允许 AI 的课程

列出课程：

```powershell
.\.venv\Scripts\python.exe main.py courses --account me
```

输出中的 `course_id` 是数字 ID。标记允许生成文本作业初稿的课程：

```powershell
.\.venv\Scripts\python.exe main.py ai-allow --account me --course-id 课程ID
```

取消标记：

```powershell
.\.venv\Scripts\python.exe main.py ai-forbid --account me --course-id 课程ID
```

默认所有课程都是“仅提醒”。未标记的课程不会生成 AI 初稿。

只有报告、论文、心得、总结、讨论、作文、案例分析、读后感、实践等文本类作业会进入 AI 待生成任务。测验、考试、选择、填空、判断、互评、投票、签到不会生成。

## 7. 手动验证完整流程

### 7.1 dry-run 检查

```powershell
.\.venv\Scripts\python.exe main.py check
```

它会：

1. 登录学习通；
2. 检查未交作业；
3. 写入 SQLite 状态；
4. 生成 `reports/{account_id}.txt`；
5. 生成 `ai_pending.json`；
6. 不发送企业微信。

确认 `ai_pending.json` 中的课程、作业和要求符合预期。

### 7.2 生成 Word 初稿

可以让 Codex 根据任务生成 Markdown 草稿，然后调用：

```powershell
.\.venv\Scripts\python.exe main.py build-docx `
  --account me `
  --assignment-id 作业ID `
  --draft ai_drafts\作业ID.md
```

如果目标 Word 已存在且非空，默认不会覆盖。确实要重新生成时才添加 `--force`。

### 7.3 测试企业微信通知

```powershell
.\.venv\Scripts\python.exe main.py notify
```

这会基于最近一次检查结果发送企业微信纯文本汇总。

如果你不需要先生成 AI 初稿，也可以每次检查后直接发送：

```powershell
.\.venv\Scripts\python.exe main.py check --send
```

## 8. 在 Codex App 里创建自动化

请在 Codex App 中打开这个仓库对应的本地任务，然后让 Codex 创建一个 heartbeat 自动化：

- 目的地：当前本地线程 / local
- 频率：每天 20:00
- 时区：Asia/Shanghai
- 应用内通知：只在自动化失败、需要人工处理或配置缺失时提醒
- 日常作业汇总：通过企业微信发送，不依赖 Codex 应用内通知

可以直接复制下面这段话发给 Codex：

```text
请在当前本地仓库任务中创建一个 heartbeat 自动化：每天 20:00（Asia/Shanghai）执行学习通作业检查流程，目的地保持 local。应用内通知只在失败、需要人工处理或配置缺失时提醒；日常汇总通过项目里的企业微信通知发送。
```

然后使用下面的自动化提示词。注意把 `me` 替换成你的账号 ID；多账号时不需要逐个替换，命令会默认检查 `settings.json` 里的全部账号。

```text
在当前仓库根目录执行本地学习通作业检查流程。所有 PowerShell 命令先设置 UTF-8 输出编码，并使用 .\.venv\Scripts\python.exe。

先确认 .venv、config/settings.json、config/classification_rules.json 存在。如果缺失，停止执行并说明需要用户运行初始化和配置步骤；不要代替用户索要学习通密码或企业微信 Webhook。

运行 .\.venv\Scripts\python.exe main.py check 做 dry-run 检查。若有部分账号失败，继续处理成功账号，同时记录失败原因。若触发学习通验证码、风控、异地登录验证或密码错误，停止为该账号生成初稿，说明需要人工处理；不要尝试绕过验证码。

检查成功后读取 ai_pending.json。对每一项，根据 course_name、title、requirements 和截止时间撰写一份可编辑的完整文本作业初稿，以 UTF-8 Markdown 保存到该项 draft_path。初稿要符合作业要求，只生成文本作业，不处理测验、考试、选择、填空、判断、互评、投票或签到。不要编造不确定的课程资料；如题目信息不足，在草稿开头列出需要用户补充的信息。

对每个已生成草稿的任务运行 main.py build-docx，使用该任务的 --account、--assignment-id 和 --draft。默认不覆盖已有非空 Word，不要使用 --force，除非任务文件明确要求重建且用户已确认。

最后运行 .\.venv\Scripts\python.exe main.py notify，基于最新状态发送企业微信报告。不要在聊天中输出学习通密码、Cookie 或企业微信 Webhook，不要修改或提交学习通作业。

结束时简要汇报：检查账号数、成功账号数、未交作业总数、生成初稿数、Word 路径和通知结果；如有失败，说明下一步人工处理建议。
```

创建后，建议在当天手动触发一次，确认：

1. 学习通可以登录；
2. 企业微信能收到报告；
3. `ai_pending.json` 中的任务符合预期；
4. Word 能生成到 `作业归档`；
5. 再次运行时不会覆盖已有非空 Word。

## 9. 日常运行形态

自动化每天按顺序执行：

```text
check
  ↓
ai_pending.json
  ↓
Codex 生成 Markdown 草稿
  ↓
build-docx
  ↓
notify 发送企业微信
```

Word 输出位置：

```text
作业归档\{账号显示名}\{课程名}\{作业标题}\{作业标题}.docx
```

所有 AI 文件都是初稿。提交前必须自己审阅、修改，并手动提交。

## 10. 常见问题

### `python` 是 Python 2.7

不要直接用 `python`。创建环境时使用：

```powershell
py -3.12 -m venv .venv
```

运行项目时使用：

```powershell
.\.venv\Scripts\python.exe main.py
```

### doctor 提示账号或 Webhook 未配置

检查：

1. `config/settings.json` 是否有账号；
2. 账号 `id` 是否拼写正确；
3. 是否已运行 `set-secret account`；
4. 是否已运行 `set-secret webhook`。

### doctor --live 提示验证码或风控

先在浏览器手动登录学习通，完成验证后重试。工具不会绕过验证码。

### 课程列表为空

确认：

1. 学习通账号能正常登录；
2. 当前账号确实有课程；
3. 网络可以访问学习通；
4. 课程是否已结课或归档。

### ai_pending.json 一直是空

常见原因：

1. 课程没有执行 `ai-allow`；
2. 作业不是文本类作业；
3. 作业不是未交状态；
4. 目标 Word 已经存在且非空；
5. 作业标题和类型无法识别，报告会按待确认处理。

### build-docx 提示数据库没有作业

先运行：

```powershell
.\.venv\Scripts\python.exe main.py check
```

`build-docx` 依赖最近一次检查写入的 SQLite 记录。

### 企业微信收不到消息

检查：

1. Webhook 是否来自企业微信群机器人；
2. `webhook_ref` 是否和 `set-secret webhook --ref` 一致；
3. 机器人是否被删除或禁用；
4. 网络是否能访问企业微信；
5. 报告是否被安全软件或网络代理拦截。

### 自动化没有在 20:00 运行

确认：

1. Codex App 当时是否运行；
2. 自动化是否创建在打开该仓库的本地任务上；
3. 电脑是否睡眠或断网；
4. 时区是否为 Asia/Shanghai；
5. 自动化是否被暂停。

## 11. 更新仓库但保留自己的配置

本地配置、状态和生成文件都被忽略。更新代码时执行：

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

你的这些文件会保留：

- `config/settings.json`
- Windows Credential Manager 中的密码和 Webhook
- `data/assistant.sqlite3`
- `reports/`
- `ai_drafts/`
- `ai_pending.json`
- `作业归档/`

## 12. 安全提醒

- 不要把学习通密码发给任何人。
- 不要把企业微信 Webhook 提交到 Git。
- 不要在公共电脑保存密码。
- 不要替他人集中保管学习通账号。
- Webhook 拥有向群内发消息的权限，泄露后应立即删除机器人并重新创建。
- 如果怀疑密码泄露，立即修改学习通密码。
