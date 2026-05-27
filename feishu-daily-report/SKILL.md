---
name: feishu-daily-report
description: 飞书运营日报自动生成。抓取群聊消息 → AI分析 → 生成HTML网页+飞书卡片 → 部署服务器 → 发送卡片消息。每天自动运行，也可手动触发。
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
argument-hint: "[--skip-fetch] [--no-deploy] [--send-only] [--hours N]"
license: MIT
---

# 飞书运营日报 Skill

当用户提到 **运营日报 / 日报 / daily report / 生成日报 / 发送日报 / 每日报告** 时触发此skill。

## 功能

自动化零壹创新运营日报生成流程：
1. 抓取16个飞书业务群最近24-48小时消息
2. AI分析提取关键信息（生产异常、品质问题、项目动态等）
3. 生成HTML日报网页（05.26模版风格，深色header+指标卡+数据表格）
4. 部署到内部服务器 http://192.168.1.171/daily.html
5. 生成飞书互动卡片消息（指标卡+头条+来源标注）
6. 发送卡片给指定人员（黄莹莹、王书昌）

## 环境要求

- Python 3.9+
- 工作目录：`/Users/ptk/feishu-minutes-collector/`
- 依赖：`requests`, `anthropic`
- 环境变量：`FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`
- 服务器：sshpass + scp 部署到 192.168.1.171
- DNS：open.feishu.cn 需要使用 IP 121.11.2.228 绕过

## 执行步骤

### Step 1: 确定参数

根据用户指令确定运行模式：

| 用户意图 | 命令 |
|---------|------|
| "生成日报" / "跑一下日报" | `python3 daily_report.py` |
| "重新生成"（不抓取，用现有数据） | `python3 daily_report.py --skip-fetch` |
| "只发送卡片" | `python3 daily_report.py --send-only` |
| "生成但不部署" | `python3 daily_report.py --skip-fetch --no-deploy` |
| "抓取最近N小时" | `python3 daily_report.py --hours 48` |

### Step 2: 执行

```bash
cd /Users/ptk/feishu-minutes-collector
python3 daily_report.py [参数]
```

默认参数：
- `--hours 24`：抓取最近24小时消息
- 无 `--skip-fetch`：先抓取再生成
- 无 `--no-deploy`：自动部署到服务器

### Step 3: 汇报结果

向用户报告：
- 抓取了多少个群、多少条消息
- HTML和卡片是否生成成功
- 服务器是否部署成功
- 卡片是否发送成功（分别报告每个接收人）

## 关键文件

| 文件 | 说明 |
|------|------|
| `daily_report.py` | 主脚本（抓取→分析→生成HTML→生成卡片→部署→发送） |
| `daily_report_cron.sh` | Cron定时任务脚本 |
| `daily_report.log` | 运行日志 |
| `chat_fix/` | 群聊消息存储目录 |
| `daily_card.json` | 生成的卡片JSON |
| `daily_report.html` | 生成的HTML日报 |

## 接收人配置

在 `daily_report.py` 中 `RECIPIENTS` 变量配置：
- 黄莹莹 (open_id: `ou_7fa27f1b9bdaf0a669149c87f2c9d02c`)
- 王书昌 (user_id: `d53dg676`)

如需临时只发给某人，注释掉另一个即可。

## 监控的16个业务群

新材料生产群、PMC-项目群、喷涂数据通报群、品质来料检验群、BOM问题沟通群、01*03品控组、直通良率改善群、I18单片式项目群、客服售后反馈群、QC管理、会议妙记收集群、干布计划、复材来料检验沟通群、标准群、PITAKA后端周例会小组、新材料-追料群

## 定时任务

Cron 已配置：
```
0 9 * * * /Users/ptk/.claude/skills/feishu-minutes/lib/daily_scan.sh
57 9 * * * /Users/ptk/feishu-minutes-collector/daily_report_cron.sh
```

## 卡片模版格式

严格遵循05.26模版：
- Header: "零壹创新运营日报 · MM.DD"
- 指标卡: 4个，格式="数字"+"产品名+问题"（如 🔴 28.5% / 卡包-P缺角）
- 头条: "🔴 头条 | 标题" 或 "🟠 关注 | 标题" 或 "⚠️ 预警 | 标题"
- 每条: 1-2句话精炼概括 + 来源标注

## HTML模版格式

严格遵循05.26模版（深色header+指标卡+数据表格+引用框）：
- 按业务流程排序：项目开发 → 生产动态 → 品质监控 → 物料工程 → 喷涂/良率 → 客服 → 明日关注
- 表格必须使用 `class="data-table"`
- Tags使用连字符格式：`tag-red`, `tag-orange` 等

## 常见问题

1. **DNS失败**: open.feishu.cn 在本机DNS无法解析，需用 `--resolve` 或 subprocess curl 绕过
2. **API超时**: HTML生成调用AI可能超时(180s)，会自动降级到模板生成
3. **I18群无数据**: glob pattern 已修复为 `*{name}.txt`（兼容文件名前缀）
4. **sshpass密码**: 密码含 `!` 必须用 subprocess 传递，不能用 bash 直接执行
