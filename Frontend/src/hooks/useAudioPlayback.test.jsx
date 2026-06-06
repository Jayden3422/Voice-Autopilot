import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../utils/api.js", () => ({
  postAPI: vi.fn(),
}));

import { useAudioPlayback } from "./useAudioPlayback.js";
import { postAPI } from "../utils/api.js";

beforeEach(() => {
  postAPI.mockReset();
  window.speechSynthesis = {
    cancel: vi.fn(),
    speak: vi.fn((utterance) => utterance.onend?.()),
  };
  vi.stubGlobal("SpeechSynthesisUtterance", class {
    constructor(text) {
      this.text = text;
    }
  });
});

describe("useAudioPlayback", () => {
  it("falls back to browser speech when backend greeting TTS is unavailable", async () => {
    postAPI.mockRejectedValue(new Error("Service unavailable"));
    const { result } = renderHook(() => useAudioPlayback({ lang: "en" }));

    await act(async () => {
      await result.current.playGreeting("Welcome");
    });

    expect(window.speechSynthesis.speak).toHaveBeenCalledOnce();
  });
});
