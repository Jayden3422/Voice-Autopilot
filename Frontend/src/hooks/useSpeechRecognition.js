// Frontend/src/hooks/useSpeechRecognition.js
import { useState, useRef } from "react";

const getCtor = () => {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
};

export function useSpeechRecognition({ lang, onResult, onError }) {
  const [isActive, setIsActive] = useState(false);
  const recognitionRef = useRef(null);
  const activeRef = useRef(false);
  const finalTextRef = useRef("");
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const stop = () => {
    activeRef.current = false;
    setIsActive(false);
    const r = recognitionRef.current;
    recognitionRef.current = null;
    finalTextRef.current = "";
    if (!r) return;
    r.onresult = null;
    r.onerror = null;
    r.onend = null;
    try { r.stop(); } catch { /* ignore */ }
  };

  const start = () => {
    const Ctor = getCtor();
    if (!Ctor) return false;

    stop();

    const r = new Ctor();
    r.lang = lang === "zh" ? "zh-CN" : "en-US";
    r.continuous = true;
    r.interimResults = true;

    activeRef.current = true;
    finalTextRef.current = "";

    r.onresult = (event) => {
      let finalText = finalTextRef.current;
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
      finalTextRef.current = finalText;
      onResultRef.current({ finalText, interimText });
    };

    r.onerror = (event) => {
      if (event.error === "not-allowed" && onErrorRef.current) {
        onErrorRef.current(event);
      }
    };

    r.onend = () => {
      // activeRef check is sufficient: stop() nulls r.onend synchronously before calling r.stop(),
      // so by the time onend fires after an intentional stop, this handler is already null.
      if (!activeRef.current) return;
      try { r.start(); } catch { /* ignore restart failure */ }
    };

    try {
      r.start();
      recognitionRef.current = r;
      setIsActive(true);
      return true;
    } catch {
      activeRef.current = false;
      recognitionRef.current = null;
      return false;
    }
  };

  return { isActive, start, stop };
}
