import { useState, useRef, useEffect } from "react";
import { Button, Input, message as AntMessage } from "antd";
import { SendOutlined } from "@ant-design/icons";
import "./index.scss";
import * as api from "../../utils/api";
import { useI18n } from "../../i18n/LanguageContext.jsx";
import { ENABLE_BROWSER_TTS, TTS_MODE } from "../../config/tts.js";

const getSpeechRecognitionCtor = () => {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
};

const Home = () => {
  const { t, lang, setLangLocked } = useI18n();
  const [hasStarted, setHasStarted] = useState(false);
  const [messages, setMessages] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isGreeting, setIsGreeting] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [liveTranscript, setLiveTranscript] = useState("");

  const mediaRecorderRef = useRef(null);
  const micStreamRef = useRef(null);
  const shouldSendAfterStopRef = useRef(true);

  const speechRecognitionRef = useRef(null);
  const speechRecognitionActiveRef = useRef(false);
  const speechFinalRef = useRef("");
  const isRecordingRef = useRef(false);

  const playbackQueueRef = useRef([]);
  const isChunkPlayingRef = useRef(false);
  const currentAudioRef = useRef(null);
  const currentAudioUrlRef = useRef("");

  const messagesEndRef = useRef(null);
  const sessionIdRef = useRef(
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `sess-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );

  useEffect(() => {
    isRecordingRef.current = isRecording;
  }, [isRecording]);

  const cleanupMicStream = () => {
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }
  };

  const stopLiveSpeechRecognition = () => {
    speechRecognitionActiveRef.current = false;
    const recognition = speechRecognitionRef.current;
    speechRecognitionRef.current = null;
    if (!recognition) return;

    recognition.onresult = null;
    recognition.onerror = null;
    recognition.onend = null;
    try {
      recognition.stop();
    } catch {
      // ignore
    }
  };

  const startLiveSpeechRecognition = () => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      return false;
    }

    stopLiveSpeechRecognition();

    const recognition = new Ctor();
    recognition.lang = lang === "zh" ? "zh-CN" : "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;

    speechRecognitionActiveRef.current = true;
    speechFinalRef.current = "";

    recognition.onresult = (event) => {
      let finalText = speechFinalRef.current;
      let interimText = "";

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const transcript = (event.results[i][0]?.transcript || "").trim();
        if (!transcript) continue;

        if (event.results[i].isFinal) {
          finalText = `${finalText} ${transcript}`.trim();
        } else {
          interimText = `${interimText} ${transcript}`.trim();
        }
      }

      speechFinalRef.current = finalText;
      setLiveTranscript(`${finalText} ${interimText}`.trim());
    };

    recognition.onerror = () => {
      // keep silent to avoid noisy UX on transient speech errors
    };

    recognition.onend = () => {
      if (!speechRecognitionActiveRef.current || !isRecordingRef.current) {
        return;
      }
      try {
        recognition.start();
      } catch {
        // ignore restart failure
      }
    };

    try {
      recognition.start();
      speechRecognitionRef.current = recognition;
      return true;
    } catch {
      speechRecognitionActiveRef.current = false;
      speechRecognitionRef.current = null;
      return false;
    }
  };

  const stopRecorderIfActive = (sendToBackend = true) => {
    shouldSendAfterStopRef.current = sendToBackend;
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      try {
        recorder.stop();
      } catch {
        // ignore
      }
    }
    mediaRecorderRef.current = null;
  };

  const releaseCurrentAudio = () => {
    if (currentAudioRef.current) {
      currentAudioRef.current.onended = null;
      currentAudioRef.current.onerror = null;
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    if (currentAudioUrlRef.current) {
      URL.revokeObjectURL(currentAudioUrlRef.current);
      currentAudioUrlRef.current = "";
    }
  };

  const stopPlayback = () => {
    playbackQueueRef.current = [];
    isChunkPlayingRef.current = false;
    releaseCurrentAudio();
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsPlaying(false);
  };

  const playBase64Now = (base64, mimeType = "audio/mpeg") => {
    return new Promise((resolve) => {
      try {
        const byteString = atob(base64);
        const ab = new ArrayBuffer(byteString.length);
        const ia = new Uint8Array(ab);
        for (let i = 0; i < byteString.length; i += 1) {
          ia[i] = byteString.charCodeAt(i);
        }
        const blob = new Blob([ab], { type: mimeType });
        const url = URL.createObjectURL(blob);

        releaseCurrentAudio();
        currentAudioUrlRef.current = url;

        const audio = new Audio(url);
        currentAudioRef.current = audio;

        const finalize = () => {
          releaseCurrentAudio();
          resolve();
        };

        audio.onended = finalize;
        audio.onerror = finalize;

        setIsPlaying(true);
        audio.play().catch(() => finalize());
      } catch {
        resolve();
      }
    });
  };

  const pumpAudioQueue = () => {
    if (isChunkPlayingRef.current) return;
    const next = playbackQueueRef.current.shift();
    if (!next) {
      setIsPlaying(false);
      return;
    }

    isChunkPlayingRef.current = true;
    playBase64Now(next.base64, next.mimeType)
      .catch(() => {})
      .finally(() => {
        isChunkPlayingRef.current = false;
        pumpAudioQueue();
      });
  };

  const enqueueAudioChunk = (base64, mimeType = "audio/mpeg") => {
    if (!base64) return;
    playbackQueueRef.current.push({ base64, mimeType });
    pumpAudioQueue();
  };

  const appendMessagesFromResponse = (data) => {
    const { user_text, ai_text, audio_base64, session_id } = data || {};
    if (session_id) {
      sessionIdRef.current = session_id;
    }

    const newMessages = [];
    if (user_text) {
      newMessages.push({ id: Date.now(), role: "user", text: user_text });
    }
    if (ai_text) {
      newMessages.push({ id: Date.now() + 1, role: "ai", text: ai_text });
    }
    if (newMessages.length > 0) {
      setMessages((prev) => [...prev, ...newMessages]);
    }

    if (audio_base64) {
      enqueueAudioChunk(audio_base64);
    }
  };

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, liveTranscript]);

  useEffect(() => {
    return () => {
      stopRecorderIfActive(false);
      stopLiveSpeechRecognition();
      cleanupMicStream();
      playbackQueueRef.current = [];
      isChunkPlayingRef.current = false;
      releaseCurrentAudio();
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const handleStartConversation = () => {
    setHasStarted(true);
    setLangLocked(true);
    const greeting = {
      id: Date.now(),
      role: "ai",
      text: t("home.greeting"),
    };
    setMessages([greeting]);
    playGreetingSpeech(t("home.greeting"));
  };

  const speakWithBrowserTTS = (text) => {
    if (!("speechSynthesis" in window)) return Promise.resolve(false);
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang === "zh" ? "zh-CN" : "en-US";
      utterance.onend = () => resolve(true);
      utterance.onerror = () => resolve(false);
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    });
  };

  const requestBackendTTS = async (text) => {
    const res = await api.postAPI("/tts", { text, lang });
    const data = res && res.data ? res.data : res || {};
    if (!data.audio_base64) return false;
    await playBase64Now(data.audio_base64);
    setIsPlaying(false);
    return true;
  };

  const playGreetingSpeech = async (text) => {
    setIsGreeting(true);
    stopPlayback();
    try {
      if (TTS_MODE === "browser") {
        await speakWithBrowserTTS(text);
        return;
      }
      if (TTS_MODE === "backend") {
        try {
          await requestBackendTTS(text);
        } catch (err) {
          console.error("Backend TTS failed:", err);
        }
        return;
      }
      if (TTS_MODE === "auto") {
        try {
          const ok = await requestBackendTTS(text);
          if (ok) return;
        } catch (err) {
          console.error("Backend TTS failed:", err);
        }
        if (ENABLE_BROWSER_TTS) {
          await speakWithBrowserTTS(text);
        }
      }
    } finally {
      setIsGreeting(false);
      setIsPlaying(false);
    }
  };

  const sendAudioToBackend = async (blob) => {
    const formData = new FormData();
    formData.append("audio", blob, "voice.webm");
    formData.append("lang", lang);
    formData.append("session_id", sessionIdRef.current);

    const res = await api.postAPI("/voice", formData);
    const data = res && res.data ? res.data : res || {};
    appendMessagesFromResponse(data);
  };

  const sendTextToBackend = async () => {
    const text = textInput.trim();
    if (!text) return;

    stopPlayback();
    stopRecorderIfActive(false);
    stopLiveSpeechRecognition();
    cleanupMicStream();
    setLiveTranscript("");

    setIsProcessing(true);
    setTextInput("");
    await api
      .postAPI("/calendar/text", {
        text,
        lang,
        session_id: sessionIdRef.current,
        include_audio: true,
      })
      .then((res) => {
        const data = res && res.data ? res.data : res || {};
        appendMessagesFromResponse(data);
      })
      .catch((err) => {
        console.error(`${t("errors.processingFailed")}:`, err);
        AntMessage.error(t("errors.processingFailed"));
      })
      .finally(() => {
        setIsProcessing(false);
      });
  };

  const handleStartRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      AntMessage.error(t("errors.browserNotSupported"));
      return;
    }

    stopPlayback();
    stopRecorderIfActive(false);
    stopLiveSpeechRecognition();
    cleanupMicStream();
    setLiveTranscript("");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;

      const mimeType =
        MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      const chunks = [];

      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) {
          chunks.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stopLiveSpeechRecognition();
        cleanupMicStream();
        setIsRecording(false);

        const shouldSend = shouldSendAfterStopRef.current;
        shouldSendAfterStopRef.current = true;
        if (!shouldSend) {
          return;
        }

        if (!chunks.length) {
          return;
        }

        const blob = new Blob(chunks, { type: "audio/webm" });
        setIsProcessing(true);
        try {
          await sendAudioToBackend(blob);
        } catch (err) {
          console.error(`${t("errors.processingFailed")}:`, err);
          AntMessage.error(t("errors.processingFailed"));
        } finally {
          setIsProcessing(false);
          setLiveTranscript("");
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);

      startLiveSpeechRecognition();
    } catch (err) {
      console.error(`${t("errors.micDenied")}:`, err);
      AntMessage.error(t("errors.micDenied"));
      setIsRecording(false);
      stopLiveSpeechRecognition();
      cleanupMicStream();
    }
  };

  const handleStopRecording = () => {
    stopRecorderIfActive(true);
  };

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
              if (!isProcessing && !isGreeting && !isPlaying) {
                sendTextToBackend();
              }
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
