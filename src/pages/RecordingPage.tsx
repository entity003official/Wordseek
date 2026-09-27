import { useAudioSettings } from '../store/useAudioSettings'
import { locale } from '../lib/i18n'
import { t } from '../lib/i18n'
import { Check, ChevronDown, CircleStop, Flag, Info, Lock, Mic, RotateCcw, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AudioWaveform } from '../components/AudioWaveform'
import { LearningGuide } from '../components/LearningGuide'
import { useRecorder } from '../hooks/useRecorder'
import { addRemoteMarker, analysisToPatch, createRemoteSession, getRemoteAnalysis, getRemoteHealth, startRemoteAnalysis, uploadRemoteAudio } from '../lib/api'
import { connectLiveSpeech, type LiveSentence } from '../lib/liveSpeech'
import { saveAudio } from '../lib/audioDb'
import { formatDuration } from '../lib/format'
import { useAppStore } from '../store/useAppStore'
import type { Session } from '../types'

const scenarios = ['日常交流', '语言交流', '小组讨论', '课堂交流', '面试', '其他']

export function RecordingPage() {
  const nativeLanguage = useAppStore((s) => s.nativeLanguage)
  const targetLanguage = useAppStore((s) => s.targetLanguage)
  const recorder = useRecorder()
  const live = useRef<Awaited<ReturnType<typeof connectLiveSpeech>> | null>(null)
  const liveRemoteId = useRef<string | undefined>(undefined)
  const liveFinished = useRef<Promise<void>>(Promise.resolve())
  const [liveConnecting, setLiveConnecting] = useState(false)
  const [liveError, setLiveError] = useState('')
  const [liveSentences, setLiveSentences] = useState<LiveSentence[]>([])
  const [liveConsent, setLiveConsent] = useState(false)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; live.current?.close() } }, [])
  const [microphones, setMicrophones] = useState<MediaDeviceInfo[]>([])
  const microphoneId = useAudioSettings((s) => s.microphoneId)
  const setMicrophoneId = useAudioSettings((s) => s.setMicrophoneId)
  useEffect(() => {
    const media = navigator.mediaDevices
    if (!media?.enumerateDevices) return
    let cancelled = false
    const refresh = () => { void media.enumerateDevices().then((items) => {
      if (!cancelled) setMicrophones(items.filter((item) => item.kind === 'audioinput' && item.deviceId && item.deviceId !== 'default'))
    }).catch(() => undefined) }
    refresh()
    media.addEventListener('devicechange', refresh)
    return () => { cancelled = true; media.removeEventListener('devicechange', refresh) }
  }, [recorder.status])
  const navigate = useNavigate()
  const addSession = useAppStore((state) => state.addSession)
  const updateSession = useAppStore((state) => state.updateSession)
  const [scenario, setScenario] = useState(scenarios[0])
  const [cloudSpeechConsent, setCloudSpeechConsent] = useState(false)
  const [savedSessionId, setSavedSessionId] = useState<string | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [saveError, setSaveError] = useState('')
  const [savingLocal, setSavingLocal] = useState(false)
  const [analysisError, setAnalysisError] = useState('')
  const [toast, setToast] = useState('')
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
  const [pendingSession, setPendingSession] = useState<Session | null>(null)
  const [syncState, setSyncState] = useState<'idle' | 'syncing' | 'synced' | 'failed'>('idle')
  const [analyzing, setAnalyzing] = useState(false)
  const [pipelineMode, setPipelineMode] = useState<'checking' | 'cloud' | 'unavailable'>('checking')
  const [preflightOpen, setPreflightOpen] = useState(true)

  useEffect(() => {
    void getRemoteHealth()
      .then((health) => {
        if (health.speech?.qwen.available) setPipelineMode('cloud')
        else setPipelineMode('unavailable')
      })
      .catch(() => setPipelineMode('unavailable'))
  }, [])

  useEffect(() => {
    if (!audioUrl) return
    return () => URL.revokeObjectURL(audioUrl)
  }, [audioUrl])

  async function startRecording() {
    setSavedSessionId(null)
    setPendingSession(null)
    setAudioUrl(null)
    setRecordedBlob(null)
    setSyncState('idle')
    setAnalysisError('')
    setSaveError('')
    setPreflightOpen(false)
    live.current?.close()
    live.current = null
    liveRemoteId.current = undefined
    setLiveSentences([])
    setLiveError('')
    if (liveConsent) {
      setLiveConnecting(true)
      setCloudSpeechConsent(true)
      try {
        const remote = await createRemoteSession(`${t(scenario)} · ${new Intl.DateTimeFormat(locale(), { month: 'short', day: 'numeric' }).format(new Date())}`, scenario, targetLanguage)
        if (!mounted.current) return
        liveRemoteId.current = remote.id
        const connection = await connectLiveSpeech(remote.id, (sentence) => {
          if (mounted.current) setLiveSentences((previous) => [...previous.filter((item) => item.id !== sentence.id), sentence].sort((a, b) => a.start_ms - b.start_ms))
        }, (message) => { if (mounted.current) setLiveError(message) })
        if (!mounted.current) { connection.close(); return }
        live.current = connection
      } catch {
        if (mounted.current) setLiveError(t("实时转写未连接，已切换为本地录音，结束后可转写。"))
      } finally { if (mounted.current) setLiveConnecting(false) }
    }
    if (!mounted.current) return
    const started = await recorder.start(microphoneId || undefined, live.current ? (data) => live.current?.send(data) : undefined)
    if (!started) live.current?.close()
  }

  async function syncToBackend(localId: string, session: Session, blob: Blob, existingRemoteId?: string) {
    setSyncState('syncing')
    updateSession(localId, { syncStatus: 'syncing' })
    try {
      const remoteId = existingRemoteId ?? (await createRemoteSession(session.title, session.scenario, session.targetLanguage || targetLanguage)).id
      updateSession(localId, { remoteId, syncStatus: 'syncing' })
      await uploadRemoteAudio(remoteId, blob, session.durationMs)
      await Promise.all(session.markers.map((marker) => addRemoteMarker(remoteId, marker)))
      updateSession(localId, { remoteId, syncStatus: 'synced' })
      setSyncState('synced')
      if (liveConsent && liveRemoteId.current === remoteId) {
        setAnalyzing(true)
        await liveFinished.current
        try {
          const partial = await getRemoteAnalysis(remoteId)
          updateSession(localId, { ...analysisToPatch(partial), processingStatus: 'saved' })
        } catch { /* No finalized sentences yet; original recording is retained. */ }
        try {
          const job = await startRemoteAnalysis(remoteId, {
            language_hints: [...new Set([targetLanguage, nativeLanguage])], speaker_policy: { mode: 'auto', min_count: 1, max_count: 8, expected_count: null },
            cloud_audio_consent: { accepted: true, version: '2026-09-26.1' },
          })
          updateSession(localId, { processingStatus: job.processing_status })
          if (mounted.current) navigate(`/review/${localId}`)
        } catch {
          if (mounted.current) setAnalysisError(t("录音已保存，补全说话人分析未启动，可手动重试。"))
        } finally {
          if (mounted.current) setAnalyzing(false)
        }
      }
    } catch {
      updateSession(localId, { syncStatus: 'failed' })
      setSyncState('failed')
    }
  }

  async function saveCapturedRecording(session: Session, blob: Blob) {
    if (savingLocal) return
    setSavingLocal(true)
    setSaveError('')
    try {
      await saveAudio(session.audioKey!, blob)
      addSession({ ...session, syncStatus: 'local' })
      setSavedSessionId(session.id)
      setPendingSession(null)
      void syncToBackend(session.id, session, blob, session.remoteId)
    } catch {
      setPendingSession(session)
      setRecordedBlob(blob)
      setSaveError(t("录音暂存在当前页面，尚未写入本机存储。请重试保存后再离开。"))
    } finally {
      setSavingLocal(false)
    }
  }

  function closeRecordingPage() {
    if (pendingSession && !savedSessionId && !window.confirm(t("这段录音尚未保存，离开会丢失。仍要离开吗？"))) return
    navigate('/')
  }

  async function stopAndSave() {
    const result = await recorder.stop()
    liveFinished.current = live.current?.finish() ?? Promise.resolve()
    if (!result) return
    if (result.blob.size === 0) {
      setSaveError(t("没有采集到可播放的音频，请检查麦克风后重试。"))
      return
    }
    const sessionId = crypto.randomUUID()
    const audioKey = `audio-${sessionId}`
    const session: Session = {
      id: sessionId,
      targetLanguage,
      title: `${t(scenario)} · ${new Intl.DateTimeFormat(locale(), { month: 'short', day: 'numeric' }).format(new Date())}`,
      scenario,
      createdAt: new Date().toISOString(),
      durationMs: result.durationMs,
      markers: result.markers,
      processingStatus: 'saved',
      audioKey,
      remoteId: liveRemoteId.current,
      isMockAnalysis: false,
      turns: liveSentences.filter((line) => line.final).map((line) => ({ id: `live-${line.id}`, speaker: 'unknown', speakerId: 'SPEAKER_UNKNOWN', startMs: line.start_ms, endMs: line.end_ms, text: line.text })),
      events: [],
    }
    setRecordedBlob(result.blob)
    setAudioUrl(URL.createObjectURL(result.blob))
    setPendingSession(session)
    await saveCapturedRecording(session, result.blob)
  }

  function addMarker() {
    const marker = recorder.mark()
    if (marker) {
      setToast(t("重点时刻已保存 · {0}", [formatDuration(marker.timestampMs)]))
      window.setTimeout(() => setToast(''), 2200)
    }
  }

  async function analyze() {
    if (!savedSessionId) return
    const session = useAppStore.getState().sessions.find((item) => item.id === savedSessionId)
    if (!session) return
    if (!cloudSpeechConsent) {
      setAnalysisError(t("请先同意将本次录音发送给阿里云千问，再开始语音分析。"))
      return
    }
    setAnalyzing(true)
    setAnalysisError('')
    if (!session.remoteId || session.syncStatus !== 'synced') {
      setAnalysisError(t("录音尚未同步到后端。请先重试上传，成功后再开始分析。"))
      setAnalyzing(false)
      return
    }
    try {
      updateSession(savedSessionId, { processingStatus: 'transcribing' })
      await startRemoteAnalysis(session.remoteId, {
        language_hints: [...new Set([targetLanguage, nativeLanguage])],
        speaker_policy: { mode: 'auto', min_count: 1, max_count: 8, expected_count: null },
        cloud_audio_consent: { accepted: cloudSpeechConsent, version: '2026-09-26.1' },
      })
      navigate(`/review/${savedSessionId}`)
    } catch (error) {
      const message = error instanceof Error ? error.message : '分析失败，请稍后重试。'
      updateSession(savedSessionId, { processingStatus: 'failed' })
      setAnalysisError(message)
    } finally {
      setAnalyzing(false)
    }
  }

  const isRecording = recorder.status === 'recording'
  const canSaveInterrupted = recorder.status === 'error' && recorder.hasAudio
  const isFinished = recorder.status === 'stopped' && Boolean(savedSessionId || pendingSession)
  const analysisLabel = pipelineMode === 'cloud' ? '可以开始分析' : pipelineMode === 'checking' ? '正在检查服务' : '分析服务暂不可用'
  const analysisDescription = pipelineMode === 'cloud'
    ? '经你授权后，本次录音将发送给阿里云百炼千问，生成转写、时间戳并自动区分 1–8 位匿名说话人；随后仍需由你确认自己的身份。'
    : pipelineMode === 'checking'
      ? '正在检查千问语音服务，请稍候。'
      : '千问语音服务当前未配置或暂不可用，录音仍可保存，恢复后可以重新发起分析。'

  return (
    <div className={`recording-page ${preflightOpen && !isRecording && !isFinished ? 'recording-page--setup' : ''}`}>
      <header className="recording-header">
        <button className="icon-button icon-button--dark" onClick={closeRecordingPage} aria-label={t("关闭")}><X size={22} /></button>
        <strong>{t("录音")}</strong>
        <span className="recording-header__spacer" />
      </header>

      {!preflightOpen && <LearningGuide surface="recording" cloudConsent={cloudSpeechConsent} recordingPhase={isFinished ? savedSessionId ? analyzing ? 'analyzing' : syncState === 'syncing' ? 'syncing' : syncState !== 'synced' ? 'sync-failed' : pipelineMode !== 'cloud' ? 'unavailable' : analysisError ? 'analysis-failed' : 'saved' : 'unsaved' : isRecording ? 'recording' : recorder.status === 'requesting' ? 'requesting' : 'error'} />}
      <div className="recording-status">
        <span className={`live-dot ${isRecording ? 'is-live' : ''}`} />
        <strong>{isRecording ? t("正在录音") : canSaveInterrupted ? t("录音中断，可保存已采集片段") : isFinished ? savedSessionId ? t("录音已保存") : t("录音待保存") : recorder.status === 'requesting' ? t("等待麦克风权限") : t("准备就绪")}</strong>
      </div>

      <div className="recording-time">{formatDuration(recorder.elapsedMs)}</div>
      <AudioWaveform levels={recorder.levels} dark />
      {liveConnecting && <p className="live-transcript-status" role="status">{t("正在连接实时转写…")}</p>}
      {(liveConsent && (isRecording || isFinished)) && <section className="live-transcript"><h2>{t("实时转写")}</h2><div>{liveSentences.length ? liveSentences.map((line) => <p key={line.id} className={line.final ? '' : 'is-partial'}>{line.text}</p>) : <p>{t("说话后，文字会显示在这里。")}</p>}</div><small>{t("说话人身份将在录音结束后补全")}</small></section>}
      {liveError && <p className="error-banner" role="status">{t(liveError)}</p>}

      {!isFinished && !liveConnecting && <button className={`virtual-bean ${isRecording || canSaveInterrupted ? 'is-recording' : ''}`} onClick={() => isRecording || canSaveInterrupted ? void stopAndSave() : setPreflightOpen(true)} aria-label={isRecording ? t("停止并保存录音") : canSaveInterrupted ? t("保存已采集的录音片段") : t("开始录音")}>
        <span className="bean-shine" />
        {isRecording || canSaveInterrupted ? <span className="bean-stop" /> : <Mic size={40} />}
      </button>}

      {(isRecording || canSaveInterrupted) && <div className="recording-actions">
        {isRecording && <button onClick={addMarker}><Flag size={21} /><span>{t("标记")}</span></button>}
        <button className="is-danger" onClick={() => void stopAndSave()}><CircleStop size={21} /><span>{canSaveInterrupted ? t("保存片段") : t("结束")}</span></button>
      </div>}

      {isRecording && recorder.markers.length > 0 && <div className="marker-strip">{recorder.markers.map((marker) => <span key={marker.id}><Flag size={12} /> {formatDuration(marker.timestampMs)}</span>)}</div>}

      {isFinished && (
        <section className="recording-result">
          <div className="saved-line"><span>{savedSessionId ? <Check size={18} /> : <CircleStop size={18} />}</span><div><strong>{savedSessionId ? t("录音已保存") : t("录音暂存在当前页面")}</strong><small>{formatDuration(recorder.elapsedMs)} · {recorder.markers.length}{t("个重点时刻 ·")}{savedSessionId ? syncState === 'syncing' ? t("正在同步") : syncState === 'failed' ? t("等待重新同步") : syncState === 'synced' ? t("已同步") : t("保存在本机") : t("本地存储失败")}</small></div></div>
          {audioUrl && <audio controls src={audioUrl} />}
          {!savedSessionId && pendingSession && recordedBlob ? <button className="primary-button" onClick={() => void saveCapturedRecording(pendingSession, recordedBlob)} disabled={savingLocal}>{savingLocal ? t("正在保存…") : t("重试保存")}</button> : <>
          <label className="consent-check analysis-consent"><input type="checkbox" checked={cloudSpeechConsent} onChange={(event) => setCloudSpeechConsent(event.target.checked)} /><span><Check size={15} /></span><p>{t("允许分析这段录音")}</p></label>
          <button data-guide="analyze-recording" className="primary-button" onClick={() => void analyze()} disabled={!cloudSpeechConsent || syncState !== 'synced' || analyzing || pipelineMode !== 'cloud'}>{analyzing ? t("正在分析…") : t("开始分析")}</button>
          {syncState === 'failed' && savedSessionId && recordedBlob && <button className="secondary-button sync-retry" onClick={() => {
            const session = useAppStore.getState().sessions.find((item) => item.id === savedSessionId)
            if (session) void syncToBackend(savedSessionId, session, recordedBlob, session.remoteId)
          }}>{t("重试上传")}</button>}
          <button className="text-button" disabled={analyzing || syncState === 'syncing'} onClick={() => { recorder.reset(); setSavedSessionId(null); setRecordedBlob(null); setPendingSession(null); setAudioUrl(null); setSyncState('idle'); setCloudSpeechConsent(false); setPreflightOpen(true) }}><RotateCcw size={17} />{t("再录一段")}</button>
          <details className="service-details"><summary><Info size={16} />{t("分析与隐私说明")}</summary><p>{t(analysisDescription)}</p><span>{t(analysisLabel)}</span></details>
          </>}
        </section>
      )}

      {(recorder.error || saveError || analysisError) && <div className="error-banner"><Lock size={17} /><span>{t(saveError || analysisError || recorder.error || '')}</span></div>}
      {toast && <div className="toast">{t(toast)}</div>}

      {preflightOpen && !isRecording && !isFinished && <div className="recording-preflight">
        <LearningGuide surface="recording" recordingPhase="prepare" />
        <section className="recording-setup" aria-labelledby="recording-setup-title">
          <h2 id="recording-setup-title">{t("录音准备")}</h2>
          <label className="practice-microphone">{t("麦克风")}<select value={microphoneId} onChange={(event) => setMicrophoneId(event.target.value)}><option value="">{t("系统默认")}</option>{microphoneId && !microphones.some((item) => item.deviceId === microphoneId) && <option value={microphoneId}>{t("已选设备未连接")}</option>}{microphones.map((item, index) => <option key={item.deviceId} value={item.deviceId}>{item.label || `${t("麦克风")} ${index + 1}`}</option>)}</select></label>
          <label className="consent-check"><input type="checkbox" checked={liveConsent} onChange={(event) => setLiveConsent(event.target.checked)} /><span><Check size={15} /></span><p>{t("边录边转写，并在结束后自动补全分析")}</p></label>
          <p className="sheet-note">{t("开启后，音频会实时发送至千问；结束后发送完整录音区分说话人。")}</p>
          <label className="scenario-select"><span>{t("对话场景")}</span><div><select value={scenario} onChange={(event) => setScenario(event.target.value)}>{scenarios.map((item) => <option key={item} value={item}>{t(item)}</option>)}</select><ChevronDown size={19} /></div></label>
          <button className="primary-button" onClick={() => void startRecording()} disabled={liveConnecting || recorder.status === 'requesting'}>{recorder.status === 'requesting' ? t("正在获取权限…") : t("开始录音")}</button>
          <p className="sheet-note">{t("开始录音后才会启用麦克风")}</p>
        </section>
      </div>}
    </div>
  )
}
