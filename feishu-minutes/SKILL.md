---
name: feishu-minutes
description: "飞书会议妙记抓取工具。抓取会议转写文字（含说话人和时间戳），支持单个URL、批量处理、群消息扫描。当用户提到 妙记/会议记录/会议转写/transcript/minutes/飞书会议/抓取妙记 时触发。"
user-invocable: true
allowed-tools: Bash, Read
argument-hint: "[URL | --scan | --file urls.txt]"
license: MIT
---

# 飞书会议妙记抓取

## 步骤 0：环境检查

```bash
SKILL_LIB="/Users/ptk/.claude/skills/feishu-minutes/lib"
pip3 install -r "$SKILL_LIB/requirements.txt" 2>&1 | tail -1
python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null || python3 -m playwright install chromium
```

依赖只需安装一次。后续运行跳过此步骤。

## 步骤 1：确定执行模式

根据用户输入判断：

```
用户输入 →
│
├─ 提供了妙记 URL（含 minutes.feishu.cn 或 minutes.larksuite.com）
│   → 模式 A：抓取单个妙记
│
├─ 提供了多个 URL 或文件路径
│   → 模式 B：批量抓取
│
├─ 提到 "扫描" / "补漏" / "最近X小时" / "scan"
│   → 模式 C：扫描群消息
│
└─ 不确定
    → 询问用户提供 URL 或说明需求
```

## 步骤 2：执行

### 模式 A：抓取单个妙记

```bash
cd /Users/ptk/.claude/skills/feishu-minutes/lib
python3 main.py "<URL>"
```

- 如果报错 "需要登录飞书"，提示用户用 `--no-headless` 模式重新运行（会打开浏览器手动登录）
- 可用 `--output <dir>` 指定输出目录
- 可用 `--debug` 保存页面快照用于调试

### 模式 B：批量抓取

```bash
cd /Users/ptk/.claude/skills/feishu-minutes/lib
python3 main.py --file <文件路径>
```

- 文件每行一个妙记 URL，`#` 开头的行为注释

### 模式 C：扫描群消息

```bash
cd /Users/ptk/.claude/skills/feishu-minutes/lib
python3 main.py --scan --scan-hours <小时数>
```

- 默认扫描最近 24 小时
- 已处理过的链接会自动跳去重
- 可加 `--scan-notify` 发送汇总到群聊

### 首次运行（登录）

```bash
cd /Users/ptk/.claude/skills/feishu-minutes/lib
python3 main.py "<URL>" --no-headless
```

登录一次后 cookie 自动保存，后续无需再登录。

## 步骤 3：报告结果

执行完成后，向用户报告：
- 成功/失败数量
- 保存路径（默认在 `lib/meeting_transcripts/` 目录）
- 如有失败，说明原因和建议

## 注意事项

- 所有配置（App ID、Secret、Chat ID）已内置在 `.env` 中，无需额外配置
- Cookie 保存在 `lib/cookies/lark_cookies.json`，登录一次后自动复用
- 转写文字包含说话人名称 + 时间戳 + 发言内容
