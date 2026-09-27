import { SoundcoreDevice } from '../components/SoundcoreDevice'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Upload } from 'lucide-react'
import { saveAudio, deleteAudio } from '../lib/audioDb'
import { useAppStore } from '../store/useAppStore'
import { t } from '../lib/i18n'

export function RecorderDevicePage() {
  const navigate = useNavigate()
  const input = useRef<HTMLInputElement>(null)
  const pending = useRef(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function importDeviceAudio(blob: Blob, durationMs: number, title: string) {
    const owner = useAppStore.getState().ownerId
    const id = crypto.randomUUID(); const audioKey = `audio-${id}`
    await saveAudio(audioKey, blob)
    if (owner !== useAppStore.getState().ownerId) { await deleteAudio(audioKey); return }
    useAppStore.getState().addSession({id, title, scenario: '其他', targetLanguage: useAppStore.getState().targetLanguage, createdAt: new Date().toISOString(), durationMs, markers: [], processingStatus: 'saved', syncStatus: 'local', audioKey, isMockAnalysis: false, turns: [], events: []})
    navigate(`/review/${id}`)
  }
  async function importAudio(file?: File) {
    if (!file || pending.current) return
    if (!/\.(mp3|wav|m4a|mp4|webm|ogg|opus)$/i.test(file.name) || !file.size || file.size > 100 * 1024 * 1024) { setError('请选择 100 MB 以内的有效录音文件'); return }
    const owner = useAppStore.getState().ownerId
    pending.current = true; setBusy(true); setError('')
    const url = URL.createObjectURL(file)
    const audio = new Audio()
    let audioKey = ''
    try {
      const duration = await new Promise<number>((resolve, reject) => {
        const timeout = window.setTimeout(() => { cleanup(); reject(new Error('无法读取录音时长，请导出为 MP3 或 WAV 后重试')) }, 15000)
        function cleanup() { window.clearTimeout(timeout); audio.onloadedmetadata = null; audio.onerror = null }
        audio.onloadedmetadata = () => { cleanup(); Number.isFinite(audio.duration) && audio.duration > 0 ? resolve(Math.round(audio.duration * 1000)) : reject(new Error('无法读取录音时长，请导出为 MP3 或 WAV 后重试')) }
        audio.onerror = () => { cleanup(); reject(new Error('无法读取录音，请换一个文件')) }
        audio.preload = 'metadata'; audio.src = url
      })
      if (duration > 4 * 60 * 60 * 1000) throw new Error('单条录音不能超过 4 小时')
      if (owner !== useAppStore.getState().ownerId) return
      const id = crypto.randomUUID(); audioKey = `audio-${id}`
      await saveAudio(audioKey, file)
      if (owner !== useAppStore.getState().ownerId) { await deleteAudio(audioKey); return }
      useAppStore.getState().addSession({id, title: file.name.replace(/\.[^.]+$/, '').slice(0, 200), scenario: '其他', targetLanguage: useAppStore.getState().targetLanguage, createdAt: new Date().toISOString(), durationMs: duration, markers: [], processingStatus: 'saved', syncStatus: 'local', audioKey, isMockAnalysis: false, turns: [], events: []})
      navigate(`/review/${id}`)
    } catch (reason) { setError(reason instanceof Error ? reason.message : '导入失败，请重试') }
    finally { audio.removeAttribute('src'); audio.load(); URL.revokeObjectURL(url); pending.current = false; setBusy(false) }
  }
  return <div className="content-page recorder-device-page">
    <header className="page-header"><button className="icon-button" onClick={() => navigate('/profile')} aria-label={t('返回')}><ArrowLeft size={20} /></button><div><h1>{t('录音豆')}</h1></div></header>
    <SoundcoreDevice onImport={importDeviceAudio} />
    <section className="device-card"><header><span>{t('导入录音文件')}</span></header><p>{t('导入设备导出的录音，继续转写与复盘。')}</p>
      <input className="sr-only" ref={input} type="file" accept=".mp3,.wav,.m4a,.mp4,.webm,.ogg,.opus" aria-label={t('导入录音')} disabled={busy} onChange={(e) => { void importAudio(e.target.files?.[0]); e.target.value = '' }} />
      <button className="primary-button" disabled={busy} onClick={() => input.current?.click()}><Upload size={18} />{t(busy ? '正在导入…' : '导入录音')}</button>
      <small>{t('先保存到本机，分析时再上传。')}</small>
    </section>
    {error && <p className="speaker-error" role="alert">{t(error)}</p>}
  </div>
}
