import { useAudioSettings } from '../store/useAudioSettings'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Marker } from '../types'

export type RecorderState = 'idle' | 'requesting' | 'recording' | 'stopped' | 'error'

export interface RecordingResult {
  blob: Blob
  durationMs: number
  markers: Marker[]
}

export function useRecorder() {
  const [status, setStatus] = useState<RecorderState>('idle')
  const [error, setError] = useState('')
  const [elapsedMs, setElapsedMs] = useState(0)
  const [hasAudio, setHasAudio] = useState(false)
  const [inputLevel, setInputLevel] = useState<number | null>(null)
  const [markers, setMarkers] = useState<Marker[]>([])
  const [levels, setLevels] = useState<number[]>(Array(32).fill(0.04))
  const mediaRecorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const startTime = useRef(0)
  const chunks = useRef<Blob[]>([])
  const animationFrame = useRef<number | null>(null)
  const timer = useRef<number | null>(null)
  const markerRef = useRef<Marker[]>([])
  const audioContext = useRef<AudioContext | null>(null)
  const pcmNode = useRef<AudioWorkletNode | null>(null)

  const stopVisuals = useCallback(() => {
    if (animationFrame.current) cancelAnimationFrame(animationFrame.current)
    if (timer.current) window.clearInterval(timer.current)
    animationFrame.current = null
    timer.current = null
  }, [])

  const start = useCallback(async (deviceId?: string, onPcm?: (data: ArrayBuffer) => void) => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setStatus('error')
      setError('当前浏览器不支持麦克风录音，请尝试最新版 Chrome、Edge 或 Safari。')
      return false
    }

    setStatus('requesting')
    setError('')
    setInputLevel(null)
    try {
      const selectedDevice = deviceId ?? useAudioSettings.getState().microphoneId
      const activeStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1, ...(selectedDevice ? { deviceId: { exact: selectedDevice } } : {}) },
      })
      stream.current = activeStream
      chunks.current = []
      setHasAudio(false)
      markerRef.current = []
      setMarkers([])
      setElapsedMs(0)

      const preferredType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : undefined
      const recorder = new MediaRecorder(activeStream, preferredType ? { mimeType: preferredType } : undefined)
      mediaRecorder.current = recorder
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.current.push(event.data)
          setHasAudio(true)
        }
      }
      recorder.onerror = () => {
        setError('录音意外中断。可以保存已采集的片段。')
        setStatus('error')
        stopVisuals()
        if (recorder.state !== 'inactive') {
          try { recorder.stop() } catch { /* release the microphone even if finalization already started */ }
        }
        activeStream.getTracks().forEach((track) => track.stop())
        stream.current = null
        void audioContext.current?.close().catch(() => undefined)
        audioContext.current = null
      }
      recorder.start(1000)
      startTime.current = performance.now()
      setStatus('recording')

      try {
        const context = new AudioContext()
        audioContext.current = context
        if (context.state === 'suspended') await context.resume()
        const source = context.createMediaStreamSource(activeStream)
        if (onPcm) {
          await context.audioWorklet.addModule('/pcm-capture.js')
          const capture = new AudioWorkletNode(context, 'pcm-capture')
          pcmNode.current = capture
          capture.port.onmessage = (event) => { if (event.data instanceof ArrayBuffer) onPcm(event.data) }
          const silent = context.createGain()
          silent.gain.value = 0
          source.connect(capture).connect(silent).connect(context.destination)
        }
        const analyser = context.createAnalyser()
        analyser.fftSize = 128
        analyser.smoothingTimeConstant = 0.75
        source.connect(analyser)
        const data = new Uint8Array(analyser.frequencyBinCount)
        const samples = new Float32Array(analyser.fftSize)
        let lastPaint = 0
        const draw = (now: number) => {
          analyser.getByteFrequencyData(data)
          if (now - lastPaint > 55) {
            analyser.getFloatTimeDomainData(samples)
            const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length)
            setInputLevel(rms)
            const next = Array.from(data.slice(0, 32), (value) => Math.max(0.035, value / 255))
            setLevels(next)
            lastPaint = now
          }
          animationFrame.current = requestAnimationFrame(draw)
        }
        animationFrame.current = requestAnimationFrame(draw)
      } catch {
        if (onPcm) setError('实时音频采集不可用，录音仍会保存，结束后可转写。')
        // Recording still works if the browser can't provide a waveform analyser.
        setLevels(Array(32).fill(0.04))
      }
      timer.current = window.setInterval(() => setElapsedMs(performance.now() - startTime.current), 100)
      return true
    } catch (reason) {
      stopVisuals()
      if (mediaRecorder.current?.state === 'recording') {
        mediaRecorder.current.ondataavailable = null
        mediaRecorder.current.onerror = null
        try { mediaRecorder.current.stop() } catch { /* stream cleanup below is still required */ }
      }
      stream.current?.getTracks().forEach((track) => track.stop())
      stream.current = null
      await audioContext.current?.close().catch(() => undefined)
      audioContext.current = null
      mediaRecorder.current = null
      chunks.current = []
      setHasAudio(false)
      const denied = reason instanceof DOMException && (reason.name === 'NotAllowedError' || reason.name === 'PermissionDeniedError')
      setError(denied
        ? '未获得麦克风权限。请在浏览器中允许访问麦克风后重试。'
        : reason instanceof DOMException && ['NotFoundError', 'OverconstrainedError'].includes(reason.name)
          ? '所选麦克风不可用，请到个人中心重新选择设备。'
          : '无法启动麦克风。请确认设备已连接，且未被其他应用占用。')
      setStatus('error')
      return false
    }
  }, [stopVisuals])

  const mark = useCallback(() => {
    if (status !== 'recording') return null
    const marker = { id: crypto.randomUUID(), timestampMs: Math.round(performance.now() - startTime.current) }
    markerRef.current = [...markerRef.current, marker]
    setMarkers(markerRef.current)
    return marker
  }, [status])

  const stop = useCallback(async (): Promise<RecordingResult | null> => {
    const recorder = mediaRecorder.current
    if (!recorder) return null
    const durationMs = Math.round(performance.now() - startTime.current)
    let blob: Blob
    if (recorder.state === 'inactive') {
      blob = new Blob(chunks.current, { type: recorder.mimeType || 'audio/webm' })
    } else {
      blob = await new Promise<Blob>((resolve) => {
        recorder.addEventListener('stop', () => resolve(new Blob(chunks.current, { type: recorder.mimeType || 'audio/webm' })), { once: true })
        recorder.stop()
      })
    }
    stopVisuals()
    if (pcmNode.current) {
      const capture = pcmNode.current
      await new Promise<void>((resolve) => {
        const onMessage = (event: MessageEvent) => {
          if (event.data === 'flushed') { clearTimeout(timeout); capture.port.removeEventListener('message', onMessage); resolve() }
        }
        const timeout = window.setTimeout(() => { capture.port.removeEventListener('message', onMessage); resolve() }, 500)
        capture.port.addEventListener('message', onMessage)
        capture.port.postMessage('flush')
      })
      capture.disconnect()
      pcmNode.current = null
    }
    stream.current?.getTracks().forEach((track) => track.stop())
    stream.current = null
    await audioContext.current?.close()
    audioContext.current = null
    setElapsedMs(durationMs)
    setLevels(Array(32).fill(0.04))
    setStatus('stopped')
    mediaRecorder.current = null
    return { blob, durationMs, markers: markerRef.current }
  }, [stopVisuals])

  const reset = useCallback(() => {
    setStatus('idle')
    setError('')
    setElapsedMs(0)
    setHasAudio(false)
    setMarkers([])
    markerRef.current = []
  }, [])

  useEffect(() => () => {
    stopVisuals()
    if (mediaRecorder.current?.state === 'recording') mediaRecorder.current.stop()
    stream.current?.getTracks().forEach((track) => track.stop())
    void audioContext.current?.close()
  }, [stopVisuals])

  return { status, error, elapsedMs, hasAudio, markers, levels, inputLevel, start, stop, mark, reset }
}
