import { useEffect, useRef, useState } from 'react'
import { useAudioSettings } from '../store/useAudioSettings'
import { t } from '../lib/i18n'

export function MicrophoneSettings() {
  const selected = useAudioSettings((s) => s.microphoneId)
  const setSelected = useAudioSettings((s) => s.setMicrophoneId)
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [state, setState] = useState<'idle' | 'requesting' | 'testing'>('idle')
  const [level, setLevel] = useState(0)
  const [heard, setHeard] = useState(false)
  const [error, setError] = useState('')
  const [actual, setActual] = useState('')
  const stream = useRef<MediaStream | null>(null)
  const context = useRef<AudioContext | null>(null)
  const frame = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const generation = useRef(0)
  function release() {
    generation.current++
    cancelAnimationFrame(frame.current)
    if (timer.current) clearTimeout(timer.current)
    stream.current?.getTracks().forEach((track) => track.stop())
    stream.current = null
    if (context.current) void context.current.close().catch(() => undefined)
    context.current = null
  }
  function stop() { release(); setState('idle'); setLevel(0) }
  useEffect(() => {
    const media = navigator.mediaDevices
    let alive = true
    const refresh = () => { void media?.enumerateDevices().then((items) => { if (alive) setDevices(items.filter((item) => item.kind === 'audioinput' && item.deviceId && item.deviceId !== 'communications')) }).catch(() => { if (alive) setError('无法读取麦克风列表，请检查浏览器权限。') }) }
    const hide = () => { if (document.hidden) stop() }
    refresh(); media?.addEventListener('devicechange', refresh); document.addEventListener('visibilitychange', hide)
    return () => { alive = false; release(); media?.removeEventListener('devicechange', refresh); document.removeEventListener('visibilitychange', hide) }
  }, [])
  async function start() {
    release()
    const token = generation.current
    setState('requesting'); setError(''); setHeard(false); setActual('')
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error()
      const acquired = await navigator.mediaDevices.getUserMedia({audio: selected ? {deviceId: {exact: selected}} : true})
      if (token !== generation.current) { acquired.getTracks().forEach((track) => track.stop()); return }
      stream.current = acquired
      const track = acquired.getAudioTracks()[0]
      setActual(track.label)
      track.onended = () => { if (token === generation.current) { stop(); setError('所选麦克风已断开，请重新选择。') } }
      const items = await navigator.mediaDevices.enumerateDevices()
      if (token !== generation.current) return
      setDevices(items.filter((item) => item.kind === 'audioinput' && item.deviceId && item.deviceId !== 'communications'))
      const audio = new AudioContext()
      context.current = audio
      await audio.resume()
      if (token !== generation.current) return
      const analyser = audio.createAnalyser()
      analyser.fftSize = 1024
      audio.createMediaStreamSource(acquired).connect(analyser)
      const samples = new Float32Array(analyser.fftSize)
      let last = 0
      const draw = (now: number) => {
        if (token !== generation.current) return
        if (now - last > 80) {
          analyser.getFloatTimeDomainData(samples)
          const rms = Math.sqrt(samples.reduce((sum, v) => sum + v*v, 0) / samples.length)
          setLevel(Math.min(1, rms * 8))
          if (rms > 0.006) setHeard(true)
          last = now
        }
        frame.current = requestAnimationFrame(draw)
      }
      frame.current = requestAnimationFrame(draw)
      setState('testing')
      timer.current = setTimeout(() => { if (token === generation.current) stop() }, 30000)
    } catch (e) {
      if (token !== generation.current) return
      stop()
      setError(e instanceof DOMException && e.name === 'NotAllowedError' ? '请允许浏览器访问麦克风。' : '麦克风不可用，请检查连接或选择其他设备。')
    }
  }
  return <section className="profile-editor microphone-settings">
    <h2>{t('麦克风设定')}</h2>
    <label htmlFor="preferred-microphone">{t('录音设备')}</label>
    <select id="preferred-microphone" value={selected} onChange={(e) => { stop(); setSelected(e.target.value); setError(''); setActual(''); setHeard(false) }}>
      <option value="">{t('系统默认')}</option>
      {selected && !devices.some((d) => d.deviceId === selected) && <option value={selected}>{t('已选设备未连接')}</option>}
      {devices.filter((d) => d.deviceId !== 'default').map((d,i) => <option value={d.deviceId} key={d.deviceId}>{d.label || `${t('麦克风')} ${i+1}`}</option>)}
    </select>
    <p>{t('用于本设备上的录音、练习和场景陪练。')}</p>
    <button className="secondary-button" onClick={() => state === 'idle' ? void start() : stop()}>{t(state === 'idle' ? '检测麦克风' : state === 'requesting' ? '取消' : '停止检测')}</button>
    {state === 'requesting' && <p role="status">{t('等待麦克风权限…')}</p>}
    {actual && <small>{actual}</small>}
    {state === 'testing' && <><meter min={0} max={1} value={level} aria-label={t('麦克风音量')} /><p role="status">{t(heard ? '已检测到声音' : '请说句话；若音量条不动，请切换设备。')}</p></>}
    {state === 'idle' && actual && !error && <p role="status">{t(heard ? '检测结束，已收到声音。' : '未检测到明显声音，请换一个麦克风。')}</p>}
    <small>{t('仅检测音量，不保存或上传声音；30 秒后自动停止。')}</small>
    {error && <p role="alert">{t(error)}</p>}
  </section>
}
