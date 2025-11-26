import { useState, useRef, useEffect } from "react";
import { Input, Button } from "antd";
import "./index.scss";

const Home = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: "ai",
      text: "您好，我是您的日程助手，你要记录什么日程？",
    },
  ]);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;

    // 用户问题
    const userMessage = {
      id: Date.now(),
      role: "user",
      text,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    setTimeout(() => {
      const aiMessage = {
        id: Date.now() + 1,
        role: "ai",
        text: `AI: 收到：「${text}」.\n`,
      };
      setMessages((prev) => [...prev, aiMessage]);
    }, 400);
  };

  const handlePressEnter = (e) => {
    // 按 Enter 发送，Shift+Enter 换行
    if (!e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="home-chat">
      <div className="chat-container">
        <div className="chat-header">
          <div className="chat-title">Voice Assistant Chatbot</div>
          <div className="chat-subtitle">Type your question below to chat with AI</div>
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

        <div className="chat-input-bar">
          <Input.TextArea
            placeholder="输入您的问题，按 Enter 发送（Shift+Enter 换行）"
            autoSize={{ minRows: 1, maxRows: 4 }}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={handlePressEnter}
          />
          <Button type="primary" onClick={handleSend}>
            发送
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Home;
