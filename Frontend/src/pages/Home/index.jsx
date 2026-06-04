// Frontend/src/pages/Home/index.jsx
import { useState, useRef, useEffect } from "react";
import { Button, Input, message as AntMessage } from "antd";
import { SendOutlined } from "@ant-design/icons";
import "./index.scss";
import * as api from "../../utils/api";
import { useI18n } from "../../i18n/LanguageContext.jsx";
import { useSpeechRecognition } from "../../hooks/useSpeechRecognition.js";
import { useAudioPlayback } from "../../hooks/useAudioPlayback.js";
import { useAudioRecorder } from "../../hooks/useAudioRecorder.js";

const Home = () => {
  const { t, lang, setLangLocked } = useI18n();
  const [hasStarted, setHasStarted] = useState(false);
  const [messages, setMessages] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [liveTranscript, setLiveTranscript] = useState("");

  const messagesEndRef = useRef(null);
  const sessionIdRef = useRef(
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `sess-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );

  const { isPlaying, isGreeting, enqueueChunk, stopPlayback, playGreeting, cleanup: cleanupPlayback } =
    useAudioPlayback({ lang });

  const speech = useSpeechRecognition({
    lang,
    onResult: ({ finalText, interimText }) =>
      setLiveTranscript(`${finalText} ${interimText}`.trim()),
  });

  const appendMessagesFromResponse = (data) => {
    const { user_text, ai_text, audio_base64, session_id } = data || {};
    if (session_id) sessionIdRef.current = session_id;
    const next = [];
    if (user_text) next.push({ id: Date.now(), role: "user", text: user_text });
    if (ai_text) next.push({ id: Date.now() + 1, role: "ai", text: ai_text });
    if (next.length > 0) setMessages((prev) => [...prev, ...next]);
    if (audio_base64) enqueueChunk(audio_base64);
  };

  const recorder = useAudioRecorder({
    onBlob: async (blob) => {
      setIsProcessing(true);
      try {
        const formData = new FormData();
        formData.append("audio", blob, "voice.webm");
        formData.append("lang", lang);
        formData.append("session_id", sessionIdRef.current);
        const res = await api.postAPI("/voice", formData);
        appendMessagesFromResponse(res?.data || res || {});
      } catch (err) {
        console.error(`${t("errors.processingFailed")}:`, err);
        AntMessage.error(t("errors.processingFailed"));
      } finally {
        setIsProcessing(false);
        setLiveTranscript("");
      }
    },
  });

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, liveTranscript]);

  useEffect(() => {
    return () => {
      recorder.cleanup();
      speech.stop();
      cleanupPlayback();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStartConversation = () => {
    setHasStarted(true);
    setLangLocked(true);
    const greeting = { id: Date.now(), role: "ai", text: t("home.greeting") };
    setMessages([greeting]);
    playGreeting(t("home.greeting"));
  };

  const handleStartRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      AntMessage.error(t("errors.browserNotSupported"));
      return;
    }
    stopPlayback();
    recorder.stopRecording(false);
    speech.stop();
    setLiveTranscript("");
    try {
      await recorder.startRecording();
      speech.start();
    } catch (err) {
      console.error(`${t("errors.micDenied")}:`, err);
      AntMessage.error(t("errors.micDenied"));
      speech.stop();
    }
  };

  const handleStopRecording = () => {
    // Stop speech first to clear live transcript immediately, then stop recorder.
    // (Original deferred speech stop to recorder.onstop — same net effect.)
    speech.stop();
    setLiveTranscript("");
    recorder.stopRecording(true);
  };

  const sendTextToBackend = async () => {
    const text = textInput.trim();
    if (!text) return;
    stopPlayback();
    recorder.stopRecording(false);
    speech.stop();
    setLiveTranscript("");
    setIsProcessing(true);
    setTextInput("");
    try {
      const res = await api.postAPI("/calendar/text", {
        text, lang, session_id: sessionIdRef.current, include_audio: true,
      });
      appendMessagesFromResponse(res?.data || res || {});
    } catch (err) {
      console.error(`${t("errors.processingFailed")}:`, err);
      AntMessage.error(t("errors.processingFailed"));
    } finally {
      setIsProcessing(false);
    }
  };

  const { isRecording } = recorder;

  if (!hasStarted) {
    return (
      <Button type="primary" size="large" onClick={handleStartConversation}>
        {t("home.startConversation")}
      </Button>
    );
  }

  return (
    <div className="home-chat">
      <div className="chat-container">
        <div className="chat-header">
          <div className="chat-title">{t("home.title")}</div>
          <div className="chat-subtitle">{t("home.subtitle")}</div>
        </div>

        <div className="chat-messages-wrapper">
          <div className="chat-messages">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`chat-message-row ${msg.role === "ai" ? "ai-row" : "user-row"}`}
              >
                <div className={`chat-bubble ${msg.role === "ai" ? "ai-bubble" : "user-bubble"}`}>
                  <div className="chat-bubble-role">
                    {msg.role === "ai" ? t("roles.ai") : t("roles.user")}
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

          {(isProcessing || isGreeting || isPlaying || isRecording) && (
            <div className="chat-anim-overlay">
              {isProcessing ? (
                <div className="anim-dots">
                  <span /><span /><span /><span />
                </div>
              ) : (
                <div className={`anim-wave ${isRecording ? "recording" : "playing"}`}>
                  <span /><span /><span /><span /><span />
                </div>
              )}
            </div>
          )}
        </div>

        <div className="chat-voice-bar">
          <div className="chat-voice-hint">
            {isRecording
              ? liveTranscript || t("home.hintRecording")
              : liveTranscript || t("home.hintIdle")}
          </div>
          <Button
            type={isRecording ? "default" : "primary"}
            danger={isRecording}
            onClick={isRecording ? handleStopRecording : handleStartRecording}
            loading={isProcessing}
            disabled={isProcessing || isGreeting || isPlaying}
          >
            {isRecording ? t("home.stopRecording") : t("home.startRecording")}
          </Button>
        </div>

        <div className="chat-input-bar">
          <Input.TextArea
            rows={1}
            autoSize={{ minRows: 1, maxRows: 3 }}
            placeholder={t("home.textPlaceholder")}
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onPressEnter={(e) => {
              if (e.shiftKey) return;
              e.preventDefault();
              if (!isProcessing && !isGreeting && !isPlaying) sendTextToBackend();
            }}
            disabled={isProcessing || isGreeting || isPlaying}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={sendTextToBackend}
            loading={isProcessing}
            disabled={!textInput.trim() || isProcessing || isGreeting || isPlaying}
          >
            {t("home.sendText")}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Home;
