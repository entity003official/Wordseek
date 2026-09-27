import { FavoriteButton } from '../components/FavoriteButton'
import { ReviewTutor } from '../components/ReviewTutor'
import { enrollVoiceprint, matchVoiceprint, downloadReviewWord } from '../lib/api'
import { useAuth } from '../auth/AuthContext'
import { LanguageReview } from '../components/LanguageReview'
import { t } from '../lib/i18n'
import { ArrowLeft, MoreHorizontal, BookOpen, Download, Mic2, Pencil, Play, RefreshCw, Save, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ConversationTimeline } from '../components/ConversationTimeline'
import { InsightCard } from '../components/InsightCard'
import { StatusBadge } from '../components/StatusBadge'
import { LearningGuide, useLearningGuide } from '../components/LearningGuide'
import { deleteAudio, getAudioBlob, getAudioUrl } from '../lib/audioDb'
import { addRemoteMarker, analysisToPatch, confirmRemoteSpeaker, createRemoteSession, deleteRemoteSession, generateAIReview, generatePracticeSet, getAnalysisJob, getRemoteAnalysis, getRemoteStatus, remoteAudioUrl, startRemoteAnalysis, updateRemoteSession, updateRemoteTurn, uploadRemoteAudio } from '../lib/api'
import { formatDuration, formatShortDate } from '../lib/format'
import { useAppStore } from '../store/useAppStore'
import type { Turn } from '../types'

export function ReviewPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const requestedTutor = searchParams.get('tab') === 'tutor'
  const autoReviewAttempted = useRef(new Set<string>())
  const [aiError, setAiError] = useState('')
  const nativeLanguage = useAppStore((s) => s.nativeLanguage)
  const targetLanguage = useAppStore((s) => s.targetLanguage)
  const learningGuide = useLearningGuide()
  const updateGuide = useAppStore((state) => state.updateGuide)
  const [transcriptViewed, setTranscriptViewed] = useState(true)
  const [transcriptSearch, setTranscriptSearch] = useState('')
  const [playbackMs, setPlaybackMs] = useState(0)
  const { sessionId = '' } = useParams()
  const session = useAppStore((state) => state.sessions.find((item) => item.id === sessionId))
  const navigate = useNavigate()
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const updateSession = useAppStore((state) => state.updateSession)
  const [confirmingSpeaker, setConfirmingSpeaker] = useState<string | null>(null)
  const [speakerError, setSpeakerError] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  const [syncBusy, setSyncBusy] = useState(false)
  const [editingTurnId, setEditingTurnId] = useState<string | null>(null)
  const [editingText, setEditingText] = useState('')
  const audioRef = useRef<HTMLAudioElement>(null)
  const playbackEndSeconds = useRef<number | null>(null)
  const removeSession = useAppStore((state) => state.removeSession)
  const [aiBusy, setAiBusy] = useState(false)
  const [activeTab, setActiveTab] = useState<'tutor' | 'insights' | 'transcript'>(requestedTutor ? 'tutor' : 'transcript')
  const [voiceprintNotice, setVoiceprintNotice] = useState('')
  const [voiceprintBusy, setVoiceprintBusy] = useState(false)
  const [speakerCandidate, setSpeakerCandidate] = useState('')
  const [tutorVisited, setTutorVisited] = useState(requestedTutor)
  const [speakerSheetDismissed, setSpeakerSheetDismissed] = useState(true)
  useEffect(() => {
    setActiveTab(requestedTutor ? 'tutor' : 'transcript')
    setTutorVisited(requestedTutor)
  }, [requestedTutor, sessionId])

  useEffect(() => {
    setTranscriptViewed(true)
    setTranscriptSearch('')
    setPlaybackMs(0)
    setEditingTurnId(null)
    setSpeakerSheetDismissed(true)
  }, [sessionId])

  useEffect(() => {
    let cancelled = false
    let currentUrl: string | null = null
    setAudioUrl(null)
    void getAudioUrl(session?.audioKey)
      .then((url) => {
        currentUrl = url
        if (cancelled) {
          if (url) URL.revokeObjectURL(url)
          return
        }
        setAudioUrl(url ?? (session?.remoteId ? remoteAudioUrl(session.remoteId) : null))
      })
      .catch(() => {
        if (!cancelled) setAudioUrl(session?.remoteId ? remoteAudioUrl(session.remoteId) : null)
      })
    return () => {
      cancelled = true
      if (currentUrl) URL.revokeObjectURL(currentUrl)
    }
  }, [session?.audioKey, session?.remoteId])

  useEffect(() => {
    if (!session?.remoteId || session.isMockAnalysis) return
    const activeRemoteId = session.remoteId
    const userSpeakerId = session.userSpeakerId
    let cancelled = false
    let timer: number | undefined
    let consecutiveFailures = 0

    async function pollAnalysis() {
      try {
        const status = await getRemoteStatus(activeRemoteId)
        if (cancelled) return
        consecutiveFailures = 0
        if (status.processing_status === 'failed') {
          updateSession(sessionId, { processingStatus: 'failed' })
          setSpeakerError(status.failure_reason || '语音分析失败，可重新开始分析。')
          return
        }
        if (status.processing_status === 'ready') {
          const analysis = await getRemoteAnalysis(activeRemoteId)
          if (cancelled) return
          updateSession(sessionId, { ...analysisToPatch(analysis, userSpeakerId), processingStatus: 'ready' })
          setSpeakerError('')
          return
        }
        if (status.processing_status === 'saved') {
          setSpeakerError('')
          updateSession(sessionId, { processingStatus: 'saved' })
          return
        }
        setSpeakerError('')
        updateSession(sessionId, { processingStatus: status.processing_status })
        timer = window.setTimeout(() => void pollAnalysis(), 1500)
      } catch {
        if (cancelled) return
        consecutiveFailures += 1
        if (consecutiveFailures >= 5) {
          updateSession(sessionId, { processingStatus: 'failed' })
          setSpeakerError(t("无法连接分析服务。检查网络后可以重新开始分析。"))
          return
        }
        timer = window.setTimeout(() => void pollAnalysis(), Math.min(5000, 1000 * consecutiveFailures))
      }
    }

    void pollAnalysis()
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [session?.processingStatus, session?.remoteId, session?.userSpeakerId, sessionId, updateSession])

  useEffect(() => {
    const id = session?.remoteId
    if (!id || !user?.ai_enabled || session.isMockAnalysis || session.processingStatus !== 'ready' || !session.turns.length || session.aiReview?.learning_points !== undefined || autoReviewAttempted.current.has(id)) return
    autoReviewAttempted.current.add(id)
    let cancelled = false
    setAiBusy(true)
    setAiError('')
    void (async () => {
      try {
        const latest = await getRemoteAnalysis(id)
        if (cancelled) return
        if (latest.ai_review?.learning_points === undefined) {
          const queued = await generateAIReview(id)
          await waitForJob(queued.job_id)
          if (cancelled) return
          const analysis = await getRemoteAnalysis(id)
          if (!cancelled) updateSession(session.id, analysisToPatch(analysis, session.userSpeakerId))
        } else {
          updateSession(session.id, analysisToPatch(latest, session.userSpeakerId))
        }
      } catch (error) {
        if (!cancelled) setAiError(error instanceof Error ? error.message : '复盘生成失败，请重试')
      } finally { if (!cancelled) setAiBusy(false) }
    })()
    return () => { cancelled = true; setAiBusy(false); autoReviewAttempted.current.delete(id) }
  }, [session?.remoteId, session?.processingStatus, session?.aiReview?.learning_points, user?.ai_enabled])

  if (!session) return <div className="empty-state"><h1>{t("未找到这段对话")}</h1><button className="primary-button" onClick={() => navigate('/')}>{t("返回首页")}</button></div>
  const activeSession = session

  const hasUnknownSpeaker = session.turns.some((turn) => turn.speaker === 'unknown')
  const remoteId = session.remoteId
  const localSessionId = session.id
  const knownSpeakerIds = session.speakerIds?.filter((id) => id !== 'SPEAKER_UNKNOWN') ?? []
  const confirmedSpeakerIndex = session.userSpeakerId ? knownSpeakerIds.indexOf(session.userSpeakerId) : -1

  function playTurn(turn: Turn) {
    if (!audioRef.current || !audioUrl) return
    const player = audioRef.current
    playbackEndSeconds.current = turn.endMs > turn.startMs ? turn.endMs / 1000 : null
    player.currentTime = turn.startMs / 1000
    void player.play().then(() => setSpeakerError('')).catch(() => {
      playbackEndSeconds.current = null
      setSpeakerError(t("浏览器无法播放该片段，请使用上方播放器重试。"))
    })
  }

  async function confirmSpeaker(speakerId: string) {
    if (!remoteId) return
    setSpeakerError('')
    setConfirmingSpeaker(speakerId)
    try {
      const result = await confirmRemoteSpeaker(remoteId, speakerId)
      updateSession(localSessionId, analysisToPatch(result.analysis, result.user_speaker_id))
      setSpeakerSheetDismissed(true)
    } catch (error) {
      setSpeakerError(error instanceof Error ? error.message : '无法保存说话人确认，请重试。')
    } finally {
      setConfirmingSpeaker(null)
    }
  }

  async function renameSession() {
    const title = window.prompt(t("输入新的对话标题"), activeSession.title)?.trim()
    if (!title || title === activeSession.title) return
    setActionBusy(true)
    try {
      if (remoteId) await updateRemoteSession(remoteId, { title })
      updateSession(localSessionId, { title })
      setMenuOpen(false)
    } catch (error) {
      setSpeakerError(error instanceof Error ? error.message : '重命名失败。')
    } finally {
      setActionBusy(false)
    }
  }

  async function reanalyze() {
    if (!remoteId) return
    const firstAnalysis = activeSession.processingStatus === 'saved'
    const actionLabel = t(firstAnalysis ? '开始分析' : '重新分析')
    if (!window.confirm(t("{0}会将这段录音发送给阿里云千问。是否继续？", [actionLabel]))) return
    setActionBusy(true)
    setSpeakerError('')
    setMenuOpen(false)
    try {
      updateSession(localSessionId, { processingStatus: 'transcribing' })
      const started = await startRemoteAnalysis(remoteId, {
        language_hints: [...new Set([activeSession.targetLanguage || targetLanguage, nativeLanguage])],
        speaker_policy: { mode: 'auto', min_count: 1, max_count: 8, expected_count: null },
        cloud_audio_consent: { accepted: true, version: '2026-09-26.1' },
      })
      updateSession(localSessionId, { processingStatus: started.processing_status })
    } catch (error) {
      updateSession(localSessionId, { processingStatus: 'failed' })
      setSpeakerError(error instanceof Error ? error.message : '重新分析失败。')
    } finally {
      setActionBusy(false)
    }
  }

  async function retrySync() {
    setSyncBusy(true)
    setSpeakerError('')
    updateSession(localSessionId, { syncStatus: 'syncing' })
    try {
      const blob = await getAudioBlob(activeSession.audioKey)
      if (!blob?.size) throw new Error(t("本机找不到可同步的录音文件。"))
      const nextRemoteId = activeSession.remoteId ?? (await createRemoteSession(activeSession.title, activeSession.scenario, activeSession.targetLanguage || targetLanguage)).id
      updateSession(localSessionId, { remoteId: nextRemoteId })
      if (activeSession.isFavorite) await updateRemoteSession(nextRemoteId, { is_favorite: true })
      await uploadRemoteAudio(nextRemoteId, blob, activeSession.durationMs)
      await Promise.all(activeSession.markers.map((marker) => addRemoteMarker(nextRemoteId, marker)))
      updateSession(localSessionId, { remoteId: nextRemoteId, syncStatus: 'synced' })
    } catch (error) {
      updateSession(localSessionId, { syncStatus: 'failed' })
      setSpeakerError(error instanceof Error ? error.message : '录音同步失败，请重试。')
    } finally {
      setSyncBusy(false)
    }
  }

  async function exportSession() {
    if (!remoteId) { setSpeakerError(t('请先同步录音再导出')); return }
    setActionBusy(true)
    try {
      const blob = await downloadReviewWord(remoteId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${activeSession.title.replace(/[\\/:*?"<>|]/g, '-')}.docx`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setMenuOpen(false)
    } catch { setSpeakerError(t('导出失败，请重试')) } finally { setActionBusy(false) }
  }

  async function saveVoiceprint() {
    if (!remoteId || !window.confirm(t('仅保存你已确认发言的声纹特征，用于今后识别本人声音。原始录音不会发给第三方，可在我的页面删除声纹。是否同意？'))) return
    setVoiceprintBusy(true)
    setVoiceprintNotice('')
    try { await enrollVoiceprint(remoteId); setVoiceprintNotice('声纹已保存') }
    catch (error) { setVoiceprintNotice(error instanceof Error ? error.message : '声纹保存失败') }
    finally { setVoiceprintBusy(false) }
  }

  async function findMyVoice() {
    if (!remoteId) return
    setVoiceprintBusy(true)
    setVoiceprintNotice('')
    try {
      const result = await matchVoiceprint(remoteId)
      setSpeakerCandidate(result.speaker_id || '')
      setVoiceprintNotice(result.status === 'matched' ? '已找到相近声音，请回听确认。' : result.status === 'not_enrolled' ? '尚未录入声纹，请先手动确认并保存。' : '无法可靠匹配，请手动确认。')
    } catch { setVoiceprintNotice('声纹匹配失败，请手动确认。') }
    finally { setVoiceprintBusy(false) }
  }

  function downloadRecording() {
    if (!audioUrl) return
    const extension = audioUrl.includes('.wav') ? 'wav' : 'webm'
    const anchor = document.createElement('a')
    anchor.href = audioUrl
    anchor.download = `${activeSession.title.replace(/[\\/:*?"<>|]/g, '-')}.${extension}`
    anchor.click()
    setMenuOpen(false)
  }

  async function removeCurrentSession() {
    if (!window.confirm(t("确定删除“{0}”及其录音吗？此操作无法撤销。", [activeSession.title]))) return
    setActionBusy(true)
    try {
      if (remoteId) await deleteRemoteSession(remoteId)
      await deleteAudio(activeSession.audioKey)
      removeSession(localSessionId)
      navigate('/')
    } catch (error) {
      setSpeakerError(error instanceof Error ? error.message : '删除失败。')
      setActionBusy(false)
    }
  }

  async function saveTurn(turn: Turn) {
    const text = editingText.trim()
    if (!text || !remoteId) return
    setActionBusy(true)
    try {
      const result = await updateRemoteTurn(remoteId, turn.id, { text })
      updateSession(localSessionId, analysisToPatch(result.analysis, activeSession.userSpeakerId))
      setEditingTurnId(null)
      setEditingText('')
    } catch (error) {
      setSpeakerError(error instanceof Error ? error.message : '转写修改保存失败。')
    } finally {
      setActionBusy(false)
    }
  }

  async function changeTurnSpeaker(turn: Turn, speakerId: string) {
    if (!remoteId) return
    setActionBusy(true)
    try {
      const result = await updateRemoteTurn(remoteId, turn.id, { speaker_id: speakerId })
      updateSession(localSessionId, analysisToPatch(result.analysis, activeSession.userSpeakerId))
    } catch (error) {
      setSpeakerError(error instanceof Error ? error.message : '说话人修改保存失败。')
    } finally {
      setActionBusy(false)
    }
  }

  async function runAIReview() {
    if (!remoteId) return
    setAiBusy(true)
    setAiError('')
    setSpeakerError('')
    try {
      const queued = await generateAIReview(remoteId, Boolean(activeSession.aiReview))
      await waitForJob(queued.job_id)
      const analysis = await getRemoteAnalysis(remoteId)
      updateSession(localSessionId, analysisToPatch(analysis, activeSession.userSpeakerId))
    } catch (error) {
      setAiError(error instanceof Error ? error.message : '复盘生成失败，请重试')
    } finally {
      setAiBusy(false)
    }
  }

  async function createAIExercises() {
    if (!remoteId) return
    setAiBusy(true)
    setSpeakerError('')
    try {
      const queued = await generatePracticeSet(remoteId)
      await waitForJob(queued.job_id)
      navigate('/practice?source=ai')
    } catch (error) {
      setSpeakerError(error instanceof Error ? error.message : 'AI 练习生成失败。')
    } finally {
      setAiBusy(false)
    }
  }

  async function waitForJob(jobId: string) {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      const job = await getAnalysisJob(jobId)
      if (job.status === 'complete') return
      if (job.status === 'failed') throw new Error(job.error || 'AI 任务执行失败')
      await new Promise((resolve) => window.setTimeout(resolve, 1000))
    }
    throw new Error(t("AI 任务等待超时，请稍后刷新查看。"))
  }

  return (
    <div className="content-page review-page">
      <header className="page-header">
        <button className="icon-button review-back-button" onClick={() => navigate('/')} aria-label={t("返回")} title={t("返回")}><ArrowLeft size={21} strokeWidth={1.8} aria-hidden="true" /></button>
        <div><h1>{session.title}</h1><p className="header-subtitle">{formatShortDate(session.createdAt)} · {formatDuration(session.durationMs)}</p></div>
        <FavoriteButton session={session} />
        <div className="review-menu-wrap">
          <button className="icon-button review-menu-trigger" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen} aria-label={t("操作")} title={t("操作")}><MoreHorizontal size={23} strokeWidth={1.8} aria-hidden="true" /></button>
          {menuOpen && <div className="review-menu">
            <button onClick={() => void renameSession()} disabled={actionBusy}><Pencil size={15} />{t("重命名")}</button>
            <button onClick={() => void reanalyze()} disabled={actionBusy || syncBusy || !remoteId || activeSession.processingStatus === 'transcribing' || activeSession.processingStatus === 'analyzing'}><RefreshCw size={15} /> {activeSession.processingStatus === 'saved' ? t("开始分析") : t("重新分析")}</button>
            <button onClick={() => void exportSession()} disabled={actionBusy}><Download size={15} />{t("导出 Word") }</button>
            <button onClick={downloadRecording} disabled={!audioUrl}><Mic2 size={15} />{t("下载录音")}</button>
            {session.id !== 'demo-session' && <button className="danger" onClick={() => void removeCurrentSession()} disabled={actionBusy}><Trash2 size={15} />{t("删除对话")}</button>}
          </div>}
        </div>
      </header>

      {session.userSpeakerId && <div className="voiceprint-save"><span>{t('已标记你的发言')}</span><button className="text-button" disabled={voiceprintBusy} onClick={() => void saveVoiceprint()}>{t('保存为我的声纹')}</button>{voiceprintNotice && <p role="status">{t(voiceprintNotice)}</p>}</div>}
      <LearningGuide surface="review" session={session} transcriptOpen={activeTab === 'transcript'} />
      {session.turns.length > 0 && <section className="timeline-section review-player-timeline" aria-label={t("对话节奏")}>
          <ConversationTimeline turns={session.turns} markers={session.markers} durationMs={session.durationMs} onSelect={playTurn} />
          <div className="timeline-legend"><span><i className="blue" />{t("你")}</span><span><i className="green" />{t("伙伴")}</span>{hasUnknownSpeaker && <span><i className="gray" />{t("待确认")}</span>}<span><i className="orange" />{t("标记")}</span></div>
        </section>}
      <div className="review-player">
        {audioUrl ? <audio ref={audioRef} controls src={audioUrl} className="review-audio" onTimeUpdate={(event) => {
          setPlaybackMs(event.currentTarget.currentTime * 1000)
          const endSeconds = playbackEndSeconds.current
          if (endSeconds !== null && event.currentTarget.currentTime >= endSeconds) {
            event.currentTarget.pause()
            playbackEndSeconds.current = null
          }
        }} /> : <div className="mock-audio"><button disabled aria-label={t("演示音频不可用")}><Play size={18} fill="currentColor" /></button><span>{t("原声暂不可用")}</span></div>}
        <StatusBadge status={session.processingStatus} />
        {session.syncStatus === 'syncing' && <span className="review-sync-state">{t("录音同步中")}</span>}
        {(session.syncStatus === 'failed' || session.syncStatus === 'local') && <button className="secondary-button review-sync-action" onClick={() => void retrySync()} disabled={syncBusy}>{syncBusy ? t("同步中…") : t("重试同步")}</button>}
      </div>

      <nav className="review-tabs" aria-label={t("复盘内容")} role="tablist">
        <button id="review-tab-transcript" role="tab" aria-selected={activeTab === 'transcript'} aria-controls="review-panel-transcript" className={activeTab === 'transcript' ? 'is-active' : ''} onClick={() => { setActiveTab('transcript'); setTranscriptViewed(true) }}>{t("转写")}</button>
        <button id="review-tab-insights" role="tab" aria-selected={activeTab === 'insights'} aria-controls="review-panel-insights" className={activeTab === 'insights' ? 'is-active' : ''} onClick={() => setActiveTab('insights')}>{t("语言复盘")}</button>
        <button id="review-tab-tutor" role="tab" aria-selected={activeTab === 'tutor'} aria-controls="review-panel-tutor" className={activeTab === 'tutor' ? 'is-active' : ''} onClick={() => { setTutorVisited(true); setActiveTab('tutor') }}>{t("场景陪练")}</button>
      </nav>

      {activeTab === 'insights' && <div id="review-panel-insights" className="review-tab-panel" role="tabpanel" aria-labelledby="review-tab-insights">
        {!session.isMockAnalysis && session.turns.length > 0 && <section className="ai-review-panel">
          {!session.userSpeakerId && <div className="privacy-note"><p>{t('选择哪位说话人是你，获取个人建议。')}</p>{session.diarizationStatus === 'complete' && session.speakerIds?.some((id) => id !== 'SPEAKER_UNKNOWN') ? <button className="text-button" onClick={() => setSpeakerSheetDismissed(false)}>{t('确认哪位说话人是我')}</button> : <p>{t('暂未区分说话人，仍可生成对话总结。')}</p>}</div>}
          {aiBusy && <p className="voice-status" role="status">{t('正在生成…')}</p>}
          {aiError && !aiBusy && <button className="secondary-button" onClick={() => void runAIReview()}>{t('重试')}</button>}
          {aiError && <p role="alert" className="speaker-error">{t(aiError)}</p>}
          {!user?.ai_enabled && <p>{t('开启 AI 分析后，转写将自动生成语言复盘。')}<button className="text-button" onClick={() => navigate('/profile')}>{t('前往设置')}</button></p>}
          {session.aiReview && <>
            <LanguageReview review={session.aiReview} language={session.targetLanguage || targetLanguage} turns={session.turns} onPlay={playTurn} />
            <details className="service-details"><summary>{t('对话概况')}</summary><p>{session.aiReview.summary.summary}</p><p>{t(sceneLabel(session.aiReview.scene.scene_type))} · {session.aiReview.scene.communication_goal}</p></details>
          </>}
          {session.aiReview && <button className="secondary-button ai-practice-button" onClick={() => void createAIExercises()} disabled={aiBusy}><BookOpen size={17} />{t("生成 3 道练习")}</button>}
          <details className="service-details"><summary>{t("服务与隐私详情")}</summary><p>{t("脱敏转写由 DeepSeek 生成补充分析；结论必须引用现有话轮，并需结合原声核对。")}</p></details>
        </section>}
        <section>
          <div className="section-heading"><h2>{t("值得回看的时刻")}</h2><span>{session.events.length}</span></div>
          <div className="insight-list">{session.events.map((event) => <InsightCard key={event.id} event={event} sessionId={session.id} isMock={session.isMockAnalysis} source={session.analysisSource} />)}</div>
          {!session.events.length && <div className="placeholder-card">{!session.isMockAnalysis && session.diarizationStatus === 'complete' && !session.userSpeakerId ? t("确认你的说话人身份后再生成互动提示。") : t("暂未发现需要回看的互动时刻。")}</div>}
        </section>

      </div>}

      {activeTab === 'transcript' && <div id="review-panel-transcript" className="review-tab-panel" role="tabpanel" aria-labelledby="review-tab-transcript">
        {session.turns.length > 0 ? <section className="transcript-section">

          <div className="transcript-toolbar">
            <label className="transcript-search"><span className="sr-only">{t("搜索转写")}</span><input type="search" placeholder={t("搜索对话内容")} value={transcriptSearch} onChange={(event) => setTranscriptSearch(event.target.value)} /></label>
            <span>{session.turns.filter((turn) => turn.text.toLocaleLowerCase().includes(transcriptSearch.trim().toLocaleLowerCase())).length}{t("句")}</span>
          </div>
          {!session.isMockAnalysis && session.diarizationStatus === 'complete' && knownSpeakerIds.length > 0 && <section className={`speaker-identity-card${session.userSpeakerId ? ' is-confirmed' : ''}`} aria-labelledby="speaker-identity-title">
            <div>
              <strong id="speaker-identity-title">{t(session.userSpeakerId ? '已标记自己和伙伴' : '标记自己和伙伴')}</strong>
              <p>{session.userSpeakerId && confirmedSpeakerIndex >= 0
                ? t('说话人 {0} 是你，其他说话人是伙伴。', [confirmedSpeakerIndex + 1])
                : t('回听每位说话人的片段，选择哪位是你；其他说话人会自动标记为伙伴。')}</p>
            </div>
            <button className={session.userSpeakerId ? 'secondary-button' : 'primary-button'} onClick={() => setSpeakerSheetDismissed(false)}>{t(session.userSpeakerId ? '更改标记' : '开始标记')}</button>
          </section>}
          <div className="transcript-editor-list">{session.turns.filter((turn) => turn.text.toLocaleLowerCase().includes(transcriptSearch.trim().toLocaleLowerCase())).map((turn) => <article key={turn.id} className={playbackMs >= turn.startMs && playbackMs < turn.endMs ? 'is-current-turn' : ''}>
            <div className="transcript-editor-meta">
              <strong>{turn.speaker === 'you' ? t("你") : turn.speaker === 'partner' ? t("伙伴") : t("说话人 {0}", [Math.max(0, session.speakerIds?.indexOf(turn.speakerId ?? '') ?? -1) + 1])}</strong>
              <button className="transcript-time" onClick={() => playTurn(turn)} disabled={!audioUrl} aria-label={t("回听 {0} 的这句话", [formatDuration(turn.startMs)])}><Play size={12} />{formatDuration(turn.startMs)}</button>
              {remoteId && (session.speakerIds?.length || 0) > 1 && <select value={turn.speakerId} onChange={(event) => void changeTurnSpeaker(turn, event.target.value)} disabled={actionBusy} aria-label={t("修改该话轮的说话人")}>{session.speakerIds?.map((speakerId, index) => <option key={speakerId} value={speakerId}>{t("说话人")}{index + 1}</option>)}</select>}
            </div>
            {editingTurnId === turn.id ? <div className="transcript-edit-row"><textarea lang={session.targetLanguage || targetLanguage} aria-label={t("编辑这句话")} value={editingText} onChange={(event) => setEditingText(event.target.value)} rows={3} /><div className="transcript-edit-actions"><button className="secondary-button" onClick={() => setEditingTurnId(null)} disabled={actionBusy}>{t("取消")}</button><button className="primary-button" onClick={() => void saveTurn(turn)} disabled={actionBusy || !editingText.trim()}><Save size={15} />{t("保存")}</button></div></div> : <div className="transcript-text-row"><p lang={session.targetLanguage || targetLanguage}>{turn.text}</p>{remoteId && <button className="icon-button" onClick={() => { setEditingTurnId(turn.id); setEditingText(turn.text) }} aria-label={t("修改 {0} 的转写", [formatDuration(turn.startMs)])}><Pencil size={16} /></button>}</div>}
          </article>)}</div>
          {transcriptSearch.trim() && !session.turns.some((turn) => turn.text.toLocaleLowerCase().includes(transcriptSearch.trim().toLocaleLowerCase())) && <p className="placeholder-card">{t("没有匹配的内容")}<button className="text-button" onClick={() => setTranscriptSearch('')}>{t("清除搜索")}</button></p>}
        </section> : <section className="transcript-empty">
          <h2>{session.processingStatus === 'failed' ? t("转写未完成") : ['transcribing', 'analyzing'].includes(session.processingStatus) ? t("正在转写…") : session.processingStatus === 'ready' ? t("没有识别到文字") : t("开始转写这段录音")}</h2>
          <p>{['transcribing', 'analyzing'].includes(session.processingStatus) ? t("完成后，对话文字会显示在这里。") : t("先试听录音，确认能听清人声。")}</p>
          {!session.isMockAnalysis && ['saved', 'failed'].includes(session.processingStatus) && remoteId && <button className="primary-button review-resume-analysis" onClick={() => void reanalyze()} disabled={actionBusy || syncBusy || session.syncStatus === 'syncing' || session.syncStatus === 'failed'}>{actionBusy ? t("正在提交…") : session.processingStatus === 'failed' ? t("重试转写") : t("开始转写")}</button>}
        </section>}
      </div>}

      {tutorVisited && <div id="review-panel-tutor" className="review-tab-panel review-tutor-panel" role="tabpanel" aria-labelledby="review-tab-tutor" hidden={activeTab !== 'tutor'}>
        {remoteId && session.turns.length > 0 ? <ReviewTutor key={remoteId} sessionId={remoteId} language={session.targetLanguage || targetLanguage} active={activeTab === 'tutor'} /> : <p className="placeholder-card">{t('转写完成后即可开始场景陪练。')}</p>}
      </div>}
      <details className="source-details" hidden={activeTab === 'tutor'}>
        <summary>{t("分析来源与说明")}</summary>
        <p>{session.isMockAnalysis ? t("当前内容是明确标注的演示数据，不来自你的录音。") : session.analysisNotice || '文字、时间戳和说话人信息来自本次原始录音。'}</p>
      </details>

      {speakerError && <p className="speaker-error">{t(speakerError)}</p>}
      {activeTab !== 'tutor' && session.turns.length > 0 && <button className="secondary-button review-practice-cta" onClick={() => {
        if (learningGuide.visible && learningGuide.guide.status === 'active' && transcriptViewed && session.processingStatus === 'ready' && session.turns.length > 0) updateGuide({ sessionId: session.id, reviewed: true })
        navigate(session.events[0] ? `/practice/${session.events[0].id}` : '/practice')
      }}>{t("去练习")}</button>}

      {!session.isMockAnalysis && session.diarizationStatus === 'complete' && knownSpeakerIds.length > 0 && !speakerSheetDismissed && <div className="sheet-backdrop">
        <section className="bottom-sheet speaker-check" role="dialog" aria-modal="true" aria-labelledby="speaker-check-title">
          <div className="sheet-handle" />
          <div className="sheet-heading"><div><span>{t("标记自己和伙伴")}</span><h2 id="speaker-check-title">{t("选择你的声音")}</h2></div><button className="icon-button" onClick={() => setSpeakerSheetDismissed(true)} aria-label={t("稍后确认")}><X size={20} /></button></div>
          <p>{t("先回听片段，再把你的声音标记为“我”。其余说话人会自动标记为伙伴。")}</p>
          <button className="secondary-button" disabled={voiceprintBusy} onClick={() => void findMyVoice()}>{t(voiceprintBusy ? '正在匹配…' : '用声纹匹配')}</button>
          <div className="speaker-options">{knownSpeakerIds.map((speakerId, index) => {
            const sample = session.turns.find((turn) => turn.speakerId === speakerId)
            return <article className={`speaker-option${session.userSpeakerId === speakerId ? ' is-me' : ''}`} key={speakerId}><p>{t('说话人')}{index + 1}{session.userSpeakerId === speakerId ? ` · ${t('我')}` : speakerCandidate === speakerId ? ` · ${t('声纹候选')}` : ''}</p><p>{sample?.text || t('暂无可用片段')}</p><div><button className="secondary-button" disabled={!audioUrl || !sample} onClick={() => sample && playTurn(sample)}>{t('回听')}</button><button className="primary-button" onClick={() => void confirmSpeaker(speakerId)} disabled={Boolean(confirmingSpeaker)}>{t(session.userSpeakerId === speakerId ? '已标记为我' : '标记为我')}</button></div></article>
          })}</div>
          {voiceprintNotice && <p role="status">{t(voiceprintNotice)}</p>}
          {speakerError && <p role="alert">{t(speakerError)}</p>}
        </section>
      </div>}
    </div>
  )
}

function sceneLabel(scene: NonNullable<import('../types').AIReview['scene']>['scene_type']) {
  return { casual_chat: '日常交流', classroom: '课堂交流', group_discussion: '小组讨论', interview: '面试', meeting: '会议', service_encounter: '服务场景', other: '其他场景' }[scene]
}
