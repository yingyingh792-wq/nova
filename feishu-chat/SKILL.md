---
name: feishu-chat
description: "飞书群聊消息抓取工具。抓取群聊历史消息（含用户真实名称），支持多群、时间筛选、图片下载。当用户提到 群聊消息/群聊记录/聊天记录/抓取群聊/chat log/飞书群消息 时触发。"
user-invocable: true
allowed-tools: Bash, Read
argument-hint: "[--chat-id ID | --hours N | --download-images | --format txt|json]"
license: MIT
---

# 飞书群聊消息抓取

## 步骤 0：环境检查

```bash
pip3 install requests 2>&1 | tail -1
```

只需要 `requests` 库，通常已安装。如果已安装则跳过。

## 步骤 1：确定执行参数

根据用户输入构建参数：

```
用户输入 →
│
├─ "抓取所有群的消息" / 无具体参数
│   → 无额外参数（使用 .env 中配置的所有群）
│
├─ 提到了具体的群名或群ID
│   → --chat-id <ID>
│
├─ "最近X小时" / "今天" / "昨天"
│   → --hours <小时数>
│
├─ "下载图片" / "保存图片"
│   → --download-images
│
├─ "JSON格式"
│   → --format json
│
└─ 指定了输出目录
    → --output <目录路径>
```

## 步骤 2：执行

```bash
cd /Users/ptk/.claude/skills/ccg/feishu-chat/lib
python3 chat_logger_v2.py <参数>
```

### 常用命令示例

```bash
# 抓取所有配置群的消息
python3 chat_logger_v2.py

# 只抓取最近24小时
python3 chat_logger_v2.py --hours 24

# 指定群 + 下载图片
python3 chat_logger_v2.py --chat-id oc_xxx --download-images

# 输出为JSON
python3 chat_logger_v2.py --format json

# 指定输出目录
python3 chat_logger_v2.py --output /path/to/output
```

### 已配置的群聊

`.env` 中已配置 12 个群聊 ID，默认会抓取所有群。用户可以：
- 用 `--chat-id oc_xxx` 只抓取指定群
- 用 `--chat-id oc_aaa,oc_bbb` 抓取多个群

## 步骤 3：报告结果

执行完成后，向用户报告：
- 抓取了几个群
- 每个群的消息条数
- 保存文件路径
- 如果下载了图片，报告图片数量和目录

## 注意事项

- 所有配置（App ID、Secret、Chat ID）已内置在 `.env` 中
- 用户名称通过 API 实时查询并缓存，输出的是真实姓名而非 open_id
- 支持的消息类型：文本、富文本、图片、文件、系统消息
- 图片下载需要应用有 `im:resource` 权限
