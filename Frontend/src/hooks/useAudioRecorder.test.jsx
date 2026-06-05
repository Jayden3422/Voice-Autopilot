import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useAudioRecorder } from './useAudioRecorder.js'

// MediaRecorder must be a real class so `new MediaRecorder(...)` works.
class FakeMediaRecorder {
  constructor() {
    this.state = 'inactive'
    this.ondataavailable = null
    this.onstop = null
    this.start = vi.fn(() => { this.state = 'recording' })
    this.stop = vi.fn(() => {
      this.state = 'inactive'
      this.onstop?.()
    })
    FakeMediaRecorder._lastInstance = this
  }
}
FakeMediaRecorder.isTypeSupported = vi.fn(() => true)
FakeMediaRecorder._lastInstance = null

function makeStream() {
  return { getTracks: () => [{ stop: vi.fn() }] }
}

beforeEach(() => {
  const stream = makeStream()
  FakeMediaRecorder._lastInstance = null
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  vi.stubGlobal('navigator', {
    mediaDevices: {
      getUserMedia: vi.fn().mockResolvedValue(stream),
    },
  })
})

describe('useAudioRecorder', () => {
  it('starts with isRecording false', () => {
    const { result } = renderHook(() => useAudioRecorder({ onBlob: vi.fn() }))
    expect(result.current.isRecording).toBe(false)
  })

  it('sets isRecording to true after startRecording', async () => {
    const { result } = renderHook(() => useAudioRecorder({ onBlob: vi.fn() }))
    await act(async () => {
      await result.current.startRecording()
    })
    expect(result.current.isRecording).toBe(true)
  })

  it('sets isRecording back to false after stopRecording', async () => {
    const { result } = renderHook(() => useAudioRecorder({ onBlob: vi.fn() }))
    await act(async () => {
      await result.current.startRecording()
    })
    act(() => {
      result.current.stopRecording()
    })
    expect(result.current.isRecording).toBe(false)
  })

  it('does not fire onBlob when stopRecording is called with send=false', async () => {
    const onBlob = vi.fn()
    const { result } = renderHook(() => useAudioRecorder({ onBlob }))
    await act(async () => {
      await result.current.startRecording()
    })
    act(() => {
      result.current.stopRecording(false)
    })
    expect(onBlob).not.toHaveBeenCalled()
  })

  it('cleanup stops the stream without firing onBlob', async () => {
    const onBlob = vi.fn()
    const { result } = renderHook(() => useAudioRecorder({ onBlob }))
    await act(async () => {
      await result.current.startRecording()
    })
    act(() => {
      result.current.cleanup()
    })
    expect(onBlob).not.toHaveBeenCalled()
    expect(result.current.isRecording).toBe(false)
  })
})
