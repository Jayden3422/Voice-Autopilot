import { useState, useRef, useEffect } from "react";
import { Input, Button, message as AntMessage } from "antd";
import "./index.scss";
import * as api from "../../utils/api";
import welcomeAudio from "../../assets/audio/welcome.wav";

const Home = () => {
  const [hasStarted, setHasStarted] = useState(false); // 是否“开始语音对话”
  const [messages, setMessages] = useState([]);
  // const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false); // 等待后端处理语音
  const [isWelcomePlaying, setIsWelcomePlaying] = useState(false);
  const mediaRecorderRef = useRef(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  // 自动滚动到最后一条
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 开场白
  const playWelcomeAudio = () => {
    setIsWelcomePlaying(true);
    const audio = new Audio(welcomeAudio);

    audio.onended = () => {
      setIsWelcomePlaying(false);
    };

    audio.onerror = (err) => {
      console.error("播放开场白出错：", err);
      setIsWelcomePlaying(false);
    };

    audio.play().catch((err) => {
      console.error("播放开场白失败：", err);
      setIsWelcomePlaying(false);
    });
  };

  // 点击“开始语音对话”
  const handleStartConversation = () => {
    setHasStarted(true);
    const greeting = {
      id: Date.now(),
      role: "ai",
      text: "您好，我是您的日程助手，你要记录什么日程？",
    };
    setMessages([greeting]);
    playWelcomeAudio();
  };

  // 后端音频播放
  const playBase64Audio = (base64, mimeType = "audio/wav") => {
    try {
      const byteString = atob(base64);
      const ab = new ArrayBuffer(byteString.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteString.length; i += 1) {
        ia[i] = byteString.charCodeAt(i);
      }
      const blob = new Blob([ab], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
    } catch (err) {
      console.error("播放 AI 语音失败：", err);
    }
  };

  // 音频发送后端
  const sendAudioToBackend = async (blob) => {
    const formData = new FormData();
    formData.append("audio", blob, "voice.webm");

    setIsProcessing(true);
    await api.postAPI("/voice", formData).then((res) => {
      const data = res && res.data ? res.data : res || {};
      const { user_text, ai_text, audio_base64 } = data;
      const newMessages = [];
      if (user_text) {
        newMessages.push({
          id: Date.now(),
          role: "user",
          text: user_text,
        });
      }
      if (ai_text) {
        newMessages.push({
          id: Date.now() + 1,
          role: "ai",
          text: ai_text,
        });
      }
      if (newMessages.length > 0) {
        setMessages((prev) => [...prev, ...newMessages]);
      }
      if (audio_base64) {
        playBase64Audio(audio_base64);
      }
    }).catch((err) => {
      console.error("处理语音失败：", err);
      AntMessage.error("处理语音失败，请稍后重试");
    }).finally(() => {
      setIsProcessing(false);
    });
  };

  // 开始录音
  const handleStartRecording = async () => {
    // 欢迎语
    if (isWelcomePlaying) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      AntMessage.error("当前浏览器不支持语音录制");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const chunks = [];
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: "audio/webm" });
        // 停止所有音轨
        stream.getTracks().forEach((track) => track.stop());
        // 发送给后端
        sendAudioToBackend(blob);
      };
      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setIsRecording(true);
    } catch (err) {
      console.error("获取音频权限失败：", err);
      AntMessage.error("无法访问麦克风，请检查权限设置");
    }
  };

  // 停止录音
  const handleStopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
      setIsRecording(false);
    }
  };

  // 文本输入发送
  // const handleSend = () => {
  //   const text = input.trim();
  //   if (!text) return;
  //   // 用户问题
  //   const userMessage = {
  //     id: Date.now(),
  //     role: "user",
  //     text,
  //   };
  //   setMessages((prev) => [...prev, userMessage]);
  //   setInput("");
  //   setTimeout(() => {
  //     const aiMessage = {
  //       id: Date.now() + 1,
  //       role: "ai",
  //       text: `AI: 收到：「${text}」.\n`,
  //     };
  //     setMessages((prev) => [...prev, aiMessage]);
  //   }, 400);
  // };

  // const handlePressEnter = (e) => {
  //   // 按 Enter 发送，Shift+Enter 换行
  //   if (!e.shiftKey) {
  //     e.preventDefault();
  //     handleSend();
  //   }
  // };

  // 还没开始：只显示“开始语音对话”
  if (!hasStarted) {
    return (
      <Button
        type="primary"
        size="large"
        onClick={handleStartConversation}
      >
        开始语音对话
      </Button>
    );
  }

  // 已开始：显示聊天界面 + 语音录制按钮
  return (
    <div className="home-chat">
      <div className="chat-container">
        <div className="chat-header">
          <div className="chat-title">语音驱动日程助手</div>
          <div className="chat-subtitle">
            点击下方按钮开始说话，我会帮你在 Google 日历里创建日程
          </div>
        </div>

        <div className="chat-messages">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`chat-message-row ${
                msg.role === "ai" ? "ai-row" : "user-row"
              }`}
            >
              <div
                className={`chat-bubble ${
                  msg.role === "ai" ? "ai-bubble" : "user-bubble"
                }`}
              >
                <div className="chat-bubble-role">
                  {msg.role === "ai" ? "AI" : "You"}
                </div>
                <div className="chat-bubble-text">
                  {msg.text.split("\n").map((line, idx) => (
                    <p key={idx}>{line}</p>
                  ))}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-voice-bar">
          <div className="chat-voice-hint">
            {isWelcomePlaying
              ? "正在播放提示语音，请稍候…"
              : isRecording
              ? "正在录音，请开始说出你的日程需求…"
              : "点击“开始录音”，说出例如：明天上午十点到十一点和公司 CEO 会议"}
          </div>
          <Button
            type={isRecording ? "default" : "primary"}
            danger={isRecording}
            onClick={isRecording ? handleStopRecording : handleStartRecording}
            loading={isProcessing || isWelcomePlaying}
            disabled={isProcessing || isWelcomePlaying}
          >
            {isRecording ? "停止录音" : "开始录音"}
          </Button>
        </div>

        {/* <div className="chat-input-bar">
          <Input.TextArea
            placeholder="也可以直接输入文本，按 Enter 发送（Shift+Enter 换行）"
            autoSize={{ minRows: 1, maxRows: 4 }}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={handlePressEnter}
          />
          <Button type="primary" onClick={handleSend}>
            发送
          </Button>
        </div> */}
      </div>
    </div>
  );
};

export default Home;
