# 飞书审批AI化 Skill

自动化飞书审批流程的AI评审系统。接收飞书审批事件，调用AI模型进行合规评审，将结果推送到审批评论和IM消息。

## 使用方式

用户输入 `/feishu-approval` 时激活此技能。根据参数执行不同操作：

- `/feishu-approval setup [项目目录]` — 在指定目录初始化新项目（默认当前目录下的 `feishu-approval-ai/`）
- `/feishu-approval start [项目目录]` — 启动 Cloudflare 隧道 + Flask 服务
- `/feishu-approval status` — 检查服务运行状态
- `/feishu-approval subscribe` — 订阅审批事件
- `/feishu-approval stop` — 停止服务
- 无参数时 — 显示帮助信息

## 核心架构

```
飞书审批事件 → Webhook(POST /webhook) → 解密/验证 → 事件分发
  → 审批实例状态变更(PENDING)
    → 获取审批详情
    → 解析表单内容
    → 获取申请人信息
    → 推断审批类型
    → AI评审(LLM调用)
    → 硬编码规则引擎(覆盖AI结论)
    → 添加审批评论
    → 发送IM卡片给审批人
    → 发送Bot通知
```

## 技术栈

- Flask 2.3+ (Webhook服务)
- 飞书开放平台 API v4 (审批/IM/通讯录)
- OpenAI兼容API (AI评审, 支持中转站)
- Cloudflare Tunnel (内网穿透)
- cryptography (事件解密)

## 关键飞书API注意事项

这些是经过实际联调验证的要点，必须严格遵守：

1. **事件格式**: 审批事件走 1.0 格式 (`type: "event_callback"`, `event.type: "approval_instance"`)
2. **字段命名**: 飞书API返回 `task_list`(非`tasks`), `comment_list`(非`comments`)
3. **状态值**: 大写 `"PENDING"`, `"ONGOING"`, `"APPROVED"`, `"REJECTED"`
4. **评论API**: 飞书评论接口需要 `open_id` 作为 query parameter `user_id`（不是 request body）
5. **IM消息**: `receive_id_type` 默认用 `"user_id"`
6. **Bot通知**: 模板ID需要是应用自己的模板，公共模板会报错60001

## 执行步骤

### setup — 初始化项目

1. 创建项目目录结构：
   ```
   {project_dir}/
   ├── .env              # 环境变量（飞书凭据、AI密钥）
   ├── .env.example      # 环境变量模板
   ├── config.yaml       # 主配置（审批类型、评审标准、AI参数）
   ├── requirements.txt  # Python依赖
   ├── main.py           # 启动入口
   ├── subscription.py   # 事件订阅管理CLI
   └── src/
       ├── __init__.py
       ├── feishu_client.py   # 飞书API客户端
       ├── ai_reviewer.py     # AI评审引擎
       ├── webhook.py         # Webhook事件处理
       └── review_criteria.py # 评审标准管理
   ```

2. **交互式引导**用户填写配置（使用 AskUserQuestion 工具）：
   - 飞书 App ID 和 App Secret
   - AI API Key 和 Base URL
   - 要监控的审批类型（合同审批、报销审批等）
   - Webhook端口（默认5000）

3. 使用下方的 **文件模板** 创建所有文件

4. 运行 `pip install -r requirements.txt` 安装依赖

5. 提示用户完成飞书开放平台配置：
   - 创建企业自建应用
   - 添加权限：`approval:approval`, `contact:contact.base:readonly`, `im:message`, `im:message:send_as_bot`
   - 发布应用（必须点"发布"才生效）
   - 设置应用可用范围为"全员可用"
   - 在"事件与回调"中配置请求地址
   - 添加事件：`approval_instance`, `approval_task`

### start — 启动服务

1. 检查 `.env` 文件是否存在且配置完整
2. 检查端口是否被占用（macOS的AirPlay Receiver常占5000端口）
3. 启动 Cloudflare Tunnel：
   ```bash
   cloudflared tunnel --url http://localhost:{port} 2>&1 &
   ```
4. 等待并提取 Tunnel URL（从日志中grep `https://.*trycloudflare.com`）
5. 更新 config.yaml 中的 `forward_url` 为新的 Tunnel URL
6. 启动 Flask 服务：
   ```bash
   cd {project_dir} && python main.py --port {port}
   ```
7. 输出服务地址给用户，提醒配置到飞书事件订阅

### status — 检查状态

1. 检查 Flask 进程是否在运行
2. 检查 Cloudflare Tunnel 是否在运行
3. 检查飞书 Token 是否能正常获取
4. 汇报状态

### subscribe — 订阅事件

1. 运行 `python subscription.py list` 列出可用审批定义
2. 让用户选择要订阅的审批类型
3. 运行 `python subscription.py subscribe <approval_code>`
4. 更新 config.yaml 的 `subscribed_approvals`

### stop — 停止服务

1. 查找并终止 Flask 进程
2. 查找并终止 Cloudflare Tunnel 进程

---

## 文件模板

### .env.example

```
# 飞书应用配置
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret

# AI模型配置
AI_PROVIDER=openai
AI_API_KEY=your_api_key
AI_MODEL=claude-sonnet-4-6
AI_BASE_URL=https://api.openai.com/v1
```

### .env（setup时生成）

与 .env.example 相同结构，但填入用户提供的实际值。

### requirements.txt

```
flask>=2.3.0
requests>=2.31.0
pyyaml>=6.0
openai>=1.0.0
gunicorn>=21.0.0
python-dotenv>=1.0.0
cryptography>=41.0.0
```

### config.yaml（setup时生成）

根据用户选择的审批类型，从以下预置类型中生成对应的 `review_criteria`：

预置审批类型：
- 合同审批、报销审批、采购审批、出差审批
- 请假审批、用印审批、招聘审批、离职审批

每种类型包含：
- `name`: 审批类型名称
- `standards`: 评审标准列表（5-7条）
- `risk_keywords`: 风险关键词列表

config.yaml 完整结构：

```yaml
feishu:
  base_url: "https://open.feishu.cn/open-apis"
  subscribed_approvals:
    - "APPROVAL_CODE_HERE"

webhook:
  port: 5000
  path: "/webhook"
  encrypt_key: ""
  verification_token: ""
  forward_url: ""

ai:
  provider: "openai"
  model: "claude-sonnet-4-6"
  base_url: "https://api.openai.com/v1"
  temperature: 0.3
  max_tokens: 2000

review:
  auto_review: true
  notify_approvers: true
  add_comment: true
  send_im_card: true

review_criteria:
  default:
    name: "通用审批"
    standards:
      - "审批内容是否完整，必填项是否都已填写"
      - "申请理由是否充分、合理"
      - "是否包含敏感或违规内容"
      - "申请流程是否符合公司规定"
    risk_keywords:
      - "现金"
      - "紧急"
      - "无合同"
      - "个人账户"
  # ... 其他审批类型的标准
```

### 源代码文件

源代码文件内容较长，从参考项目 `/Users/ptk/Documents/33-流程数字化梳理2026.4.27/02-飞书审批AI化/` 中复制以下文件：

- `main.py` → 直接复制
- `subscription.py` → 直接复制
- `src/__init__.py` → 空文件
- `src/feishu_client.py` → 直接复制
- `src/ai_reviewer.py` → 直接复制
- `src/webhook.py` → 直接复制
- `src/review_criteria.py` → 直接复制

复制后无需修改，代码已通过实际联调验证。

---

## 飞书开放平台配置检查清单

setup 完成后，提醒用户按此清单操作：

1. [ ] 创建企业自建应用 → 获取 App ID + App Secret
2. [ ] 权限管理 → 添加：
   - `approval:approval` (审批)
   - `contact:contact.base:readonly` (通讯录)
   - `im:message` (消息)
   - `im:message:send_as_bot` (以机器人身份发消息)
3. [ ] 点击"发布" → 必须发布后才生效
4. [ ] 可用范围 → 设置为"全员可用"
5. [ ] 事件与回调 → 配置请求URL为 Tunnel 地址 + `/webhook`
6. [ ] 事件与回调 → 添加事件 `approval_instance` + `approval_task`
7. [ ] 运行 `/feishu-approval subscribe` 订阅具体的审批类型

---

## 双层评审机制

系统使用"规则引擎 + AI分析"双层评审：

### 第一层：硬编码规则引擎（100%确定）

在 AI 评审结果之上，用规则强制覆盖关键场景的结论：

| 规则 | 适用类型 | 触发条件 | 强制结论 |
|------|---------|---------|---------|
| G1 | 通用 | 金额 >= 100万 | 存疑 |
| C1 | 合同 | 50万+且仅电子签 | 存疑 |
| C2 | 合同 | 缺少合同正文/附件 | 存疑 |
| C3 | 合同 | 个人账户收款 | 驳回 |
| C4 | 合同 | 风险关键词>=2项 | 驳回 |
| R1 | 报销 | 无发票 | 驳回 |

### 第二层：AI分析（灵活判断）

使用 LLM 对以下维度进行评审：
- 分项评审（按评审标准逐条打分）
- 风险提示（从文本中发现潜在问题）
- 补充建议（缺失材料、需要补充的信息）
- 审批建议摘要（第一步/第二步/第三步的明确指导）

AI结论优先级：驳回 > 存疑 > 有条件通过 > 通过

---

## 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| Token获取失败(99991663) | 应用未发布 | 去开放平台点"发布" |
| 通讯录权限不足(99991672) | 权限类型错误 | 添加 `contact:contact.base:readonly` |
| 评论报"user_id required" | 传参位置错误 | open_id 作为 query param `user_id` |
| tasks字段为空 | 字段名错误 | 飞书返回 `task_list` 不是 `tasks` |
| AI超时 | 模型响应慢 | timeout设120s，换更快的模型 |
| Bot通知60001 | 模板ID无效 | 改用IM卡片消息代替 |
| IM发送"NO availability" | 可用范围限制 | 设置应用为"全员可用" |
| 端口5000被占 | macOS AirPlay | `sudo lsof -i :5000` 找到并kill |
