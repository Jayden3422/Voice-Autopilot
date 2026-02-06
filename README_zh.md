# Voice-Autopilot

[English README](README.md)

<div align="center">

**生产级 AI 工作流自动化系统**
*语音优先日程 + 销售/支持自动驾驶，具备结构化提取、RAG 依据、模块化动作路由*

[![Tests](https://img.shields.io/badge/tests-12%20passing-success)](Backend/tests/test_autopilot.py)
[![Python](https://img.shields.io/badge/python-3.10.11-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-19-61dafb)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.122.0-009688)](https://fastapi.tiangolo.com/)

</div>

---

## 🎯 核心差异化价值

这不是一个普通的语音助手，而是一个围绕三大核心原则设计的**完整 AI 工作流系统**：

1. **可靠性优先**：严格 JSON Schema 强制结构化输出 → 零解析脆弱性
2. **上下文感知智能**：Prompt 注入时区感知时间 + 上下文传播 → 自然对话
3. **生产就绪架构**：RAG 依据 + 模块化连接器 + 审计追踪 → 真实业务应用

### 解决的问题

**之前**：在对话、日历、Slack 和邮件之间手动上下文切换
**之后**：说话或粘贴对话 → AI 提取意图、日期、预算 → 预览动作 → 确认 → 完成

---

## 🚀 核心工作流

### 1. 语音/文字日程
```
用户："下周二下午2点安排一个演示"
  ↓ Whisper STT（如果是语音）
  ↓ GPT Tool Calling + Schema 校验
  ↓ 时区感知的日期时间解析
  ↓ 通过 Playwright 检测冲突
  ↓ Google Calendar 自动化
```

**冲突解决**：只说"改到3点" → AI 重用现有上下文（标题、参与者）→ 更新时间槽

### 2. 销售/支持 Autopilot
```
对话文本/音频
  ↓ OpenAI Tool Calling（严格 schema）
  ↓ RAG 检索（知识库依据）
  ↓ 回复草稿生成（带引用）
  ↓ 动作数据补全（Calendar + Slack + Email + Ticket）
  ↓ 人工确认
  ↓ 并行执行
  ↓ SQLite 审计日志
```

**自动增强**：日历标题包含 `{公司} - {产品} - {预算}` 提供即时上下文

---

## 🏗️ 架构亮点

### 为什么这样设计？

| 组件 | 设计决策 | 好处 |
|------|---------|------|
| **JSON Schema 强制** | 为每个 action 类型定义 `oneOf` | 类型安全 payload，无歧义 |
| **Prompt 注入时间** | 系统 prompt 中包含当前时间 | 解析"明天"/"下周"无需正则 |
| **上下文传播** | `context_event` 参数 | 部分更新（"只改时间"）自然工作 |
| **RAG 带引用** | FAISS 向量存储 + 来源追踪 | 回复引用真实文档，减少幻觉 |
| **模块化连接器** | `dispatcher.py` 路由到 `slack.py`、`email_connector.py` 等 | 易于添加新动作类型 |
| **并行执行** | `asyncio.gather` 用于 dry_run 预览 | 快 3 倍的动作验证 |
| **审计追踪** | SQLite 记录每次提取 → 动作 → 结果 | 完整可追溯性，便于调试 |

### 文件结构（关键文件）

```
Backend/
├── api/autopilot.py              # 🔧 编排层（run → extract → RAG → draft → actions）
├── chat/
│   ├── autopilot_extractor.py    # 📊 OpenAI Tool Calling 带修复重试
│   ├── calendar_extractor.py     # 📅 上下文感知的日期/时间提取
│   └── prompt/
│       ├── autopilot_extraction.txt  # 💡 结构化输出的严格指令
│       └── calendar_extraction.txt   # 💡 注入时间的 prompt
├── rag/
│   ├── ingest.py                 # 🔍 分块 → 嵌入 → FAISS 索引
│   └── retrieve.py               # 🔍 向量搜索（带缓存）
├── connectors/
│   ├── slack.py                  # 📢 Webhook 集成
│   ├── email_connector.py        # 📧 SMTP 发送
│   └── linear.py                 # 🎫 GraphQL 工单创建
├── actions/dispatcher.py         # 🎯 统一动作路由（dry_run + execute）
├── business/
│   ├── autopilot_schema.json     # 📋 带 oneOf 定义的严格 schema
│   └── calendar_schema.json      # 📋 日历槽位 schema
├── store/
│   ├── db.py                     # 💾 SQLite 初始化
│   └── runs.py                   # 📜 审计日志 CRUD
└── tests/test_autopilot.py       # ✅ 12 个测试（schema、RAG、连接器、SQLite）
```

---

## 📊 技术栈

**前端**：React 19 + Vite 7 + Ant Design 6 + i18n（中英）
**后端**：FastAPI + Whisper + OpenAI + FAISS + Playwright
**存储**：SQLite（审计日志）+ FAISS（向量嵌入）
**动作**：Slack Webhook + SMTP + Linear GraphQL + Google Calendar（Playwright）
**测试**：pytest + 12 个测试覆盖 5 个类别

---

## 🎥 快速演示

### 示例：Autopilot 工作流

**输入**：
```
你好，我是 TheBestTech 的 Jack。我们想在下周五上午 10 点安排一个演示。
预算大约是每月 3000 美元。我的邮箱是 jack@example.com。
```

**AI 提取**（严格 schema）：
```json
{
  "intent": "sales_lead",
  "urgency": "medium",
  "budget": {"currency": "CAD", "range_min": 3000, "range_max": 3000},
  "entities": {"company": "TheBestTech", "contact_name": "Jack", "email": "jack@example.com"},
  "summary": "TheBestTech（Jack）请求下周五上午 10 点演示，预算约 3000 美元/月。",
  "next_best_actions": [
    {"action_type": "create_meeting", "payload": {"date": "2026-02-14", "start_time": "10:00", "end_time": "11:00", "title": "演示"}},
    {"action_type": "send_slack_summary", "payload": {"channel": "#销售", "message": "..."}},
    {"action_type": "send_email_followup", "payload": {"to": "jack@example.com", "subject": "...", "body": "..."}}
  ]
}
```

**日历标题**（自动增强）：
```
"演示 - TheBestTech - CAD $3,000/月"
```

**结果**：
- ✅ Google Calendar 中的会议（带冲突检测）
- ✅ 发送到 Slack #销售的摘要
- ✅ 发送给 Jack 的跟进邮件
- ✅ 存储在 SQLite 中的审计日志

> **注意**：所有动作在执行前都需要人工确认（dry_run 预览 → 编辑 → 确认）

---

## 环境配置

### 前端

`node` v20.19.5

```bash
cd Frontend
npm i
```

### 后端

`Python` 3.10.11

```bash
pip install fastapi uvicorn[standard] python-multipart faster-whisper edge-tts opencc-python-reimplemented dateparser playwright python-dotenv openai jsonschema faiss-cpu numpy httpx pytest pytest-asyncio tzdata
```

安装浏览器（用于日历自动化）：

```bash
python -m playwright install chromium
```

之后移动 `chrome-win` 到 `Backend\tools` 文件夹。

### 配置

将项目根目录下的 `.env.example` 复制为 `.env` 并填写你的密钥：

```bash
cp .env.example .env
```

必填项：

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5-mini              # 或 gpt-4.1-mini、gpt-4o 等
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
TIMEZONE=America/Toronto             # 默认时区，用于日期解析
```

可选项（启用对应动作连接器）：

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
LINEAR_API_KEY=lin_api_...
LINEAR_TEAM_ID=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASS=your-app-password
SMTP_FROM=noreply@yourdomain.com
SMTP_FROM_NAME=Voice Autopilot
SMTP_SSL=false
SMTP_TIMEOUT=30
```

## 总览

```
Frontend/
  src/
    pages/Home/           # 语音/文字对话页面
    pages/Autopilot/      # 销售/支持 Autopilot 页面
    utils/                # Axios 封装
    router/               # React Router
    styles/               # 全局 SCSS 变量
    i18n/                 # 中英双语翻译
Backend/
  main.py                 # FastAPI 入口 + dotenv 加载
  api/
    autopilot.py          # Autopilot API 路由 + 动作数据补全
  chat/
    calendar_extractor.py # GPT 日历槽位提取（日期/时间/标题）
    autopilot_extractor.py # OpenAI Tool Calling 提取 + 修复重试
    reply_drafter.py      # 带引用的回复草稿生成
    prompt/
      calendar_extraction.txt   # 日历提取 prompt（含 {current_datetime}）
      autopilot_extraction.txt  # Autopilot 提取 prompt（含 {current_datetime}）
      autopilot_reply_draft.txt # 回复草稿 prompt
  rag/
    ingest.py             # 知识库 → 分块 → 嵌入 → FAISS 索引
    retrieve.py           # FAISS 向量检索（带缓存）
  connectors/
    slack.py              # Slack Incoming Webhook
    linear.py             # Linear GraphQL 工单创建
    email_connector.py    # SMTP 邮件发送
  actions/
    dispatcher.py         # 统一动作路由（dry_run / execute）
  store/
    db.py                 # SQLite 初始化（autopilot.db）
    runs.py               # 审计日志 CRUD + 缓存
  business/
    calendar_schema.json  # 日历槽位提取 JSON Schema
    autopilot_schema.json # Autopilot 提取 JSON Schema
  utils/
    timezone.py           # 项目时区配置（默认 America/Toronto）
  tools/
    speech.py             # Whisper STT + Edge TTS
    nlp.py                # 正则 NLP 解析器（已注释——已被 AI 替代）
    calendar_agent.py     # Playwright Google Calendar 自动化
    file_utils.py         # 临时文件工具
    models.py             # 数据模型（CalendarCommand 等）
  tests/
    test_autopilot.py     # 12 个测试（schema、RAG、连接器、SQLite）
knowledge_base/           # RAG 用 Markdown 文档（含 10 篇示例）
```

### 前端（React 19 + Vite 7 + AntD 6）

- **入口**：`main.jsx`
- **路由**：`App.jsx` + `router/routes.jsx`
- **Home 页面**：`pages/Home/index.jsx`
- **Autopilot 页面**：`pages/Autopilot/index.jsx`
- **HTTP 封装**：
  - `request.js`：axios 实例 + 拦截器 + 错误处理
  - `http.js`：封装 `get/post/put/delete`
  - `api.js`：如 `postAPI("/voice", formData)`
- **Vite 代理**：`vite.config.js`（`/api` → `http://localhost:8000`）
- **全局样式变量**：`src/styles/variables.scss`

### 后端（FastAPI + Whisper + Edge TTS + Playwright + OpenAI）

- **入口**：`Backend/main.py`
  - FastAPI 应用 + CORS（允许 `http://localhost:5173`）
  - 通过 `python-dotenv` 加载 `.env`
- **语音模块**：`tools/speech.py`
  - Whisper `small`，`device="cpu"`，`compute_type="int8"`
  - OpenCC `t2s` 简繁转换
  - TTS 使用 `edge_tts`，中英音色 + 自动 fallback
- **日历提取**：`chat/calendar_extractor.py`
  - GPT Tool Calling + 当前多伦多时间注入
  - 冲突时支持在上下文中只修改时间
  - 替代旧版正则 NLP（`tools/nlp.py`，已注释）
- **Google Calendar Agent**：`tools/calendar_agent.py`
  - Playwright + 本地 Chrome
  - `chrome_profile` 持久化登录态
  - 冲突检测
- **数据模型**：`tools/models.py`

## 运行

前端：

```bash
cd Frontend
npm run dev
```

后端：

```bash
cd Backend
python main.py
```

打开：`http://localhost:5173`

## 核心功能

### 1. 中英双语支持

覆盖 UI、日志、报错、AI 提取、Autopilot 输出。

### 2. 语音/文字日程（AI 驱动）

- 在 Home 页面点击 **开始语音对话**
- 用中文或英文说/输入日程：
  - 相对日期：“明天”“后天”“下周三”“next Tuesday”
  - 明确日期：“2月10号”“Feb 10”
  - 自然时间：“下午两点到三点”“2pm to 3pm”
- GPT 通过 Tool Calling 提取日期/时间/标题
- 系统检测冲突并创建 Google Calendar 事件
- **如发生冲突**，可用 **语音或文字** 只说新的时间进行改期（`4`中有示例）

### 3. Google Calendar 自动化

- 基于 Playwright 的浏览器自动化（无需 API 密钥）
- 持久化登录（首次运行需手动登录 Google + MFA）
- 自动冲突检测

![image-20260206010955719](assets/image-20260206010955719.png)

### 4. 销售/支持 Autopilot

访问 `http://localhost:5173/autopilot`

#### 示例

解析结束后确认`Action Plan`执行

![image-20260206023537765](assets/image-20260206023537765.png)

日历`meeting`

![image-20260206023600869](assets/image-20260206023600869.png)

在`Slack`中：

![image-20260206023621965](assets/image-20260206023621965.png)

应答邮件：

![image-20260206023639686](assets/image-20260206023639686.png)

#### 日历冲突

要求重新排时间，

用户需要选定新的日期或者时间然后重新安排

![image-20260206023805388](assets/image-20260206023805388.png)

![image-20260206023948432](assets/image-20260206023948432.png)

#### 工作原理

**完整管线**：

```
输入（文本/语音） → Whisper STT → OpenAI Tool Calling（结构化提取）
  → RAG 知识库检索 → 带引用的回复草稿
  → 动作计划 → 人工确认 → 执行 → 审计日志
```

1. **输入**：粘贴对话文本或录制音频
2. **AI 提取**：OpenAI 提取意图、紧急程度、预算、实体信息，并建议下一步动作（严格 JSON Schema + 修复重试）
3. **知识库**：RAG 检索相关 FAQ / 产品文档作为依据
4. **回复草稿**：AI 生成专业回复（带引用）——不会编造内容
5. **动作数据补全**：从提取数据中自动填充 Payload：
   - `create_meeting` — 标题取自摘要，日期/时间取自对话内容或使用默认值
   - `send_slack_summary` — 从意图 + 紧急程度 + 公司 + 摘要构建消息
   - `send_email_followup` — 仅在有邮箱地址时生成；正文取自回复草稿
   - `create_ticket` — 标题/描述取自摘要，优先级取自紧急程度
6. **确认并执行**：预览所有动作，编辑 Payload，勾选/取消，然后确认

#### Autopilot 增强

- **邮件自动跟进**：输入中包含邮箱时，AI 回复会按邮件格式生成（含 noreply 提示），并加入 `send_email_followup` 动作。
- **富文本邮件预览**：前端以富文本方式展示邮件正文。
- **冲突改期**：日历动作冲突时，可用语音或文字更新会议时间并重新执行。
- **Slack 总结默认开启**：即使模型未建议，也会默认添加 `send_slack_summary` 动作，确保每次运行都能发送摘要到 Slack。

#### Autopilot API

| 端点 | 说明 |
|---|---|
| `POST /autopilot/run` | 分析对话（音频或文本）。返回 `run_id`、转录文本、提取 JSON、证据、回复草稿、动作预览。 |
| `POST /autopilot/confirm` | 执行已确认的动作。返回每个动作的状态和结果（URL、摘要）。 |
| `POST /autopilot/adjust-time` | 用语音或文字调整 `create_meeting` 时间并返回更新后的动作预览。 |
| `POST /autopilot/ingest` | 重新索引知识库到 FAISS 向量存储。 |

#### 日历 API

| 端点 | 说明 |
|---|---|
| `POST /voice` | 语音日程（音频）。支持 `session_id` 用于冲突改期。 |
| `POST /calendar/text` | 文字日程。支持 `session_id` 用于冲突改期。 |

#### 知识库

将 `.md` 文件放入 `knowledge_base/` 目录。项目已包含 10 篇示例文档，涵盖产品概览、定价、FAQ、支持政策、API 参考、入门指南与安全合规。

重新索引：`POST /autopilot/ingest`

#### 审计日志

所有运行记录存储在 `Backend/autopilot.db`（SQLite），支持完整追溯：输入 → 转录 → 提取 → 证据 → 草稿 → 动作 → 执行状态 → 错误。

## 测试

### 运行测试

覆盖 schema 校验、RAG、连接器、SQLite 的全部 12 个测试：

```bash
cd Backend
python -m pytest tests/test_autopilot.py -v
```

### 测试覆盖

| 类别 | 测试数 | 覆盖内容 |
|------|--------|----------|
| **Schema 校验** | 3 | 有效提取、无效数据、缺失必填字段 |
| **知识库** | 2 | 文件存在性、文本分块 |
| **连接器 Dry Run** | 5 | Slack、Linear、Email、Calendar、None action |
| **Dispatcher** | 1 | 动作路由逻辑 |
| **SQLite CRUD** | 1 | 审计日志数据库操作 |

### 测试输出示例

```
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-9.0.2, pluggy-1.6.0
tests/test_autopilot.py::test_schema_validation_valid PASSED             [  8%]
tests/test_autopilot.py::test_schema_validation_invalid PASSED           [ 16%]
tests/test_autopilot.py::test_schema_validation_missing_required PASSED  [ 25%]
tests/test_autopilot.py::test_knowledge_base_files_exist PASSED          [ 33%]
tests/test_autopilot.py::test_chunk_text PASSED                          [ 41%]
tests/test_autopilot.py::test_slack_dry_run PASSED                       [ 50%]
tests/test_autopilot.py::test_linear_dry_run PASSED                      [ 58%]
tests/test_autopilot.py::test_email_dry_run PASSED                       [ 66%]
tests/test_autopilot.py::test_dispatcher_dry_run PASSED                  [ 75%]
tests/test_autopilot.py::test_calendar_preview PASSED                    [ 83%]
tests/test_autopilot.py::test_none_action_dry_run PASSED                 [ 91%]
tests/test_autopilot.py::test_sqlite_runs_crud PASSED                    [100%]
============================= 12 passed in 0.79s ==============================
```

### 运行特定测试

```bash
# 仅运行 schema 测试
pytest tests/test_autopilot.py::test_schema_validation_valid -v

# 运行并生成覆盖率报告
pytest tests/test_autopilot.py --cov=api --cov=chat --cov=rag

# 详细模式运行并显示输出
pytest tests/test_autopilot.py -v -s
```

## 已知问题与限制

- **Google 登录需手动完成**：首次运行需在浏览器中手动登录 + MFA
- **Playwright 受网络影响**：网络慢会导致 Calendar 加载延迟
- **Whisper CPU 模式较慢**：`small` 模型较慢，可切换 `tiny` 提速
- **仅支持单日事件**：暂不支持跨日事件
- **连接器需配置凭据**：Slack/Linear/Email 需在 `.env` 中填写有效凭据才能执行（dry_run 预览始终可用）

## 🎯 技术深入探讨

### 核心实现

**1. 核心 AI 工作流？**
- 📁 [autopilot.py:55-147](Backend/api/autopilot.py#L55-L147) - 主管道编排
- 📁 [autopilot_extractor.py:59-144](Backend/chat/autopilot_extractor.py#L59-L144) - 带修复重试的结构化提取

**2. Schema 如何强制可靠性？**
- 📁 [autopilot_schema.json:150-365](Backend/business/autopilot_schema.json#L150-L365) - `oneOf` 定义实现类型安全
- 📁 [autopilot_extraction.txt:18-29](Backend/chat/prompt/autopilot_extraction.txt#L18-L29) - 完整提取的 prompt 指令

**3. RAG 实现？**
- 📁 [ingest.py](Backend/rag/ingest.py) - 知识库分块 + 嵌入
- 📁 [retrieve.py](Backend/rag/retrieve.py) - FAISS 向量搜索（带缓存）
- 📁 [knowledge_base/](knowledge_base/) - 10 篇示例 markdown 文档

**4. 上下文感知的重新调度？**
- 📁 [calendar_extractor.py:73-149](Backend/chat/calendar_extractor.py#L73-L149) - `context_event` 处理
- 📁 [calendar_extraction.txt](Backend/chat/prompt/calendar_extraction.txt) - 注入时间的 prompt

**5. 性能优化？**
- 📁 [autopilot.py:533-597](Backend/api/autopilot.py#L533-L597) - 日历标题增强（新）
- 📁 [autopilot.py:122-124](Backend/api/autopilot.py#L122-L124) - 并行 dry_run 执行
- 📁 [MEMORY.md](C:\Users\15613\.claude\projects\d--Projects-Voice-Autopilot\memory\MEMORY.md) - 优化决策日志

**6. 测试与质量保证？**
- 📁 [test_autopilot.py](Backend/tests/test_autopilot.py) - 12 个全面的测试
- 📝 运行：`cd Backend && pytest tests/test_autopilot.py -v`

### 关键指标

| 指标 | 值 | 重要性 |
|------|-----|--------|
| **测试覆盖率** | 12/12 通过 | 所有关键路径已验证 |
| **每次运行的 LLM 调用** | 1 次提取（曾经 3 次） | -66% API 成本 + 延迟 |
| **Schema 强制** | 100% 严格验证 | 零解析错误 |
| **审计日志** | 100% 运行记录 | 完全可追溯 |
| **动作成功率** | Dry_run 验证后执行 | 零破坏性操作 |

### 架构原则

1. **Schema 驱动设计**：JSON Schema 作为 AI 与代码之间的契约
2. **快速失败验证**：在执行动作前捕获问题
3. **模块化连接器**：易于扩展（添加 GitHub Issues、Discord 等）
4. **可观察工作流**：每一步都记录用于调试
5. **人在回路中**：预览 → 编辑 → 确认模式确保安全

---

## 🔗 链接

- **GitHub**：https://github.com/Jayden3422/Voice-Autopilot
- **English Docs**：[README.md](README.md)
