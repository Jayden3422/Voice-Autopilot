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

打开前端地址：[voice-assistance](http://localhost:5173)

点击”开始对话“

![image-20251128155012810](C:/Users/15613/AppData/Roaming/Typora/typora-user-images/image-20251128155012810.png)

待开场白结束之后可以开始录制语音，录制结束之后点击“停止录音”

![image-20251128155114969](C:/Users/15613/AppData/Roaming/Typora/typora-user-images/image-20251128155114969.png)

之后程序自动打开浏览器写入日程，成功之后返回语音：

![image-20251128155220583](C:/Users/15613/AppData/Roaming/Typora/typora-user-images/image-20251128155220583.png)

如果是第一次登录请在自动打开的网页中登录账号，之后程序会自动检测是否登录成功。

如果有日程冲突会返回冲突语音：

![image-20251128155313223](C:/Users/15613/AppData/Roaming/Typora/typora-user-images/image-20251128155313223.png)

## 已知问题与限制

### Google 登录流程需手动完成

- 之后可以进行全流程模拟。

### Playwright 会受网络波动影响

- 网络延迟可能导致 Calendar 页面加载慢，届时可能需要调整等待时间或者根据界面加载元素确定是否登录成功。
- 已做超时处理与错误提示，但仍可能受网络环境影响。

### Whisper small 在 CPU 上速度有限

- 如果电脑性能较弱，语音识别会稍微有延迟。
- 可以通过切换到 `distil`, `tiny` 模型提升速度。

### NLP 解析不等于人工智能识别

- 有上下文限制以及识别限制，自己想出来的组合可能不全。
- 之后可以接入 ChatGPT 等模型进行语义解析。

### 日程设置只限于一天之内

- 没有跨日的日程设置功能。
- 已经预留接口拓展，之后需要修改 NLP 以及添加新写入函数。

### 历史记录

- 没有 logs ，预留 Record 界面。
