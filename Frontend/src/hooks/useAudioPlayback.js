// Frontend/src/hooks/useAudioPlayback.js
import { useState, useRef } from "react";
import { TTS_MODE, ENABLE_BROWSER_TTS } from "../config/tts.js";
import { postAPI } from "../utils/api.js";

export function useAudioPlayback({ lang }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isGreeting, setIsGreeting] = useState(false);

  const queueRef = useRef([]);
  const isChunkPlayingRef = useRef(false);
  const currentAudioRef = useRef(null);
  const currentAudioUrlRef = useRef("");

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

  const playBase64Now = (base64, mimeType = "audio/wav") =>
    new Promise((resolve) => {
      try {
        const byteString = atob(base64);
        const ab = new ArrayBuffer(byteString.length);
        const ia = new Uint8Array(ab);
        for (let i = 0; i < byteString.length; i += 1) ia[i] = byteString.charCodeAt(i);
        const blob = new Blob([ab], { type: mimeType });
        const url = URL.createObjectURL(blob);
        releaseCurrentAudio();
        currentAudioUrlRef.current = url;
        const audio = new Audio(url);
        currentAudioRef.current = audio;
        const finalize = () => { releaseCurrentAudio(); resolve(); };
        audio.onended = finalize;
        audio.onerror = finalize;
        setIsPlaying(true);
        audio.play().catch(() => finalize());
      } catch {
        resolve();
      }
    });

  const pumpQueue = () => {
    if (isChunkPlayingRef.current) return;
    const next = queueRef.current.shift();
    if (!next) { setIsPlaying(false); return; }
    isChunkPlayingRef.current = true;
    playBase64Now(next.base64, next.mimeType)
      .catch(() => {})
      .finally(() => {
        isChunkPlayingRef.current = false;
        pumpQueue();
      });
  };

  const enqueueChunk = (base64, mimeType = "audio/wav") => {
    if (!base64) return;
    queueRef.current.push({ base64, mimeType });
    pumpQueue();
  };

  const stopPlayback = () => {
    queueRef.current = [];
    isChunkPlayingRef.current = false;
    releaseCurrentAudio();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setIsPlaying(false);
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
    const res = await postAPI("/tts", { text, lang });
    const data = res?.data || res || {};
    if (!data.audio_base64) return false;
    await playBase64Now(data.audio_base64);
    setIsPlaying(false);
    return true;
  };

  const playGreeting = async (text) => {
    setIsGreeting(true);
    stopPlayback();
    try {
      if (TTS_MODE === "browser") { await speakWithBrowserTTS(text); return; }
      if (TTS_MODE === "backend") {
        try { await requestBackendTTS(text); } catch (err) { console.error("Backend TTS failed:", err); }
        return;
      }
      if (TTS_MODE === "auto") {
        try { const ok = await requestBackendTTS(text); if (ok) return; }
        catch (err) { console.error("Backend TTS failed:", err); }
        if (ENABLE_BROWSER_TTS) await speakWithBrowserTTS(text);
      }
    } finally {
      setIsGreeting(false);
      setIsPlaying(false);
    }
  };

  const cleanup = () => {
    queueRef.current = [];
    isChunkPlayingRef.current = false;
    releaseCurrentAudio();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  };

  return { isPlaying, isGreeting, enqueueChunk, stopPlayback, playGreeting, cleanup };
}
