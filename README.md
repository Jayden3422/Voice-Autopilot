# voice-assistant
语音驱动的日程助手（Google Calendar 自动化）

本项目实现了一个 **语音驱动的智能日程助手 Web 应用**：

用户在前端点击“开始语音对话”按钮后，即可通过语音与系统进行交互。

- 系统自动识别语音 → 解析为日程指令 → 使用 Playwright 自动化 Google Calendar 页面 → 在用户的日历中创建对应的日程事件。

## 环境配置

### 前端：

`node`v20.19.5

```bash
cd Frontend
npm i
npm run dev
```

### 后端

`Python`3.10.11

```bash
pip install fastapi uvicorn[standard] python-multipart faster-whisper edge-tts opencc-python-reimplemented dateparser playwright
```

 `chrome-win/chrome.exe`：

```bash
python -m playwright install chromium
```

之后移动`chrome-win`到`Backend\tools`文件夹

## 总览

```bash
Frontend/
  src/
    pages/Home/         # 语音对话页面
    utils/              # axios 封装
    router/             # React Router
    styles/             # 全局 SCSS 变量
Backend/
  main.py               # FastAPI 主程序
  tools/
    speech.py           # Whisper STT + TTS
    nlp.py              # 中文自然语言解析
    calendar_agent.py   # Playwright 自动化
    file_utils.py       # 临时文件保存
    models.py           # 数据模型
    chrome_profile/     # 登录态持久化
    chrome-win/         # portable Chrome
```

### 前端（React + Vite + AntD）

- **入口**：`main.jsx`
- **路由**：`App.jsx` + `router/routes.jsx`
- **Home 页面**：`pages/Home/index.jsx`
- **HTTP 封装**：
  - `request.js`：axios 实例 + 拦截器 + 通用错误提示 + 404 跳转 `/NotFound`
  - `http.js`：封装 `get/post/put/delete`
  - `api.js`：前端其他地方直接用 `postAPI("/voice", formData)`
- **Vite 代理**：`vite.config.js`
- **全局样式变量**：`src/styles/variables.scss`

### 后端（FastAPI + Whisper + Edge TTS + Playwright）

- **入口**：`Backend/main.py`
  - FastAPI 应用 + CORS（允许 `http://localhost:5173` 前端）
- **语音模块**：`tools/speech.py`
  - Whisper `small`，`device="cpu"`, `compute_type="int8"`
  - 拼成字符串后，用 `OpenCC('t2s')` 把 **繁体转简体**
  - TTS 使用 `edge_tts`，语音：`zh-CN-XiaoxiaoNeural`
  - `__main__` 里有 STT + TTS 的本地测试代码
- **NLP 解析日程**：`tools/nlp.py`
- **Google Calendar Agent**：`tools/calendar_agent.py`
  - 通过 **Playwright + 本地 Chrome** 自动化：
    - 使用本地 `chrome-win/chrome.exe`
    - 使用 `chrome_profile` 持久化登录态
  - 对中英文时间 label 的解析做了兼容（“下午10点 - 下午11点”，“10am to 11am”，“10:00 – 11:30”）
- **数据模型**：`tools/models.py`

## 要求功能点

#### 1. 前端界面√

### 2. 语音交互流程√

- 点击按钮后开始语音对话
- 后端 Python 程序作为“语言应答 Bot”
- 首次连线时 Bot 用语音播报固定开场白
- 用户通过语音发指令，系统解析并回复

### 3. Google 日历操作√

- 使用浏览器自动化（Playwright）
- 用“Agent 方式”启动浏览器，由后端代码自动打开 Google Calendar 页面

### 4. 登录与会话保持√

- 不能用 Google Calendar API，只能界面操作
- 第一次运行：打开真实浏览器，用户手动登录 + MFA
- 登录成功后：
  - 保存登录状态
  - 下次运行复用，过期时再提示重新登录

### 5. 日程冲突检测与创建√

- 找到语音中说的日期与时间
- 判断该时间段是否空闲
  - 空闲：在 Calendar 中创建事件
  - 冲突：语音反馈“这个时间已有日程”，再等用户说新的时间，再创建

