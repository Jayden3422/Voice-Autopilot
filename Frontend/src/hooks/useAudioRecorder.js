// Frontend/src/hooks/useAudioRecorder.js
import { useState, useRef } from "react";

export function useAudioRecorder({ onBlob }) {
  const [isRecording, setIsRecording] = useState(false);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const shouldSendRef = useRef(true);

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  };

  const stopRecording = (send = true) => {
    shouldSendRef.current = send;
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      try { recorder.stop(); } catch { /* ignore */ }
    }
    recorderRef.current = null;
  };

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;

    const mimeType =
      MediaRecorder.isTypeSupported?.("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

    const recorder = new MediaRecorder(stream, { mimeType });
    const chunks = [];

    recorder.ondataavailable = (e) => {
      if (e.data?.size > 0) chunks.push(e.data);
    };

    recorder.onstop = async () => {
      stopStream();
      setIsRecording(false);
      const send = shouldSendRef.current;
      shouldSendRef.current = true;
      if (!send || !chunks.length) return;
      const blob = new Blob(chunks, { type: "audio/webm" });
      await onBlob(blob);
    };

    recorder.start();
    recorderRef.current = recorder;
    setIsRecording(true);
  };

  const cleanup = () => {
    shouldSendRef.current = false;
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      try { recorder.stop(); } catch { /* ignore */ }
    }
    recorderRef.current = null;
    stopStream();
  };

  return { isRecording, startRecording, stopRecording, cleanup };
}
