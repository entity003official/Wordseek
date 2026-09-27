import { t } from '../lib/i18n'
import { ArrowLeft, ArrowRight, Play } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getAudioUrl } from '../lib/audioDb'
import { remoteAudioUrl } from '../lib/api'
import { formatDuration } from '../lib/format'
import { useAppStore } from '../store/useAppStore'

export function MomentPage() {
  const { sessionId = '', eventId = '' } = useParams()
  const navigate = useNavigate()
  const session = useAppStore((state) => state.sessions.find((item) => item.id === sessionId))
  const event = session?.events.find((item) => item.id === eventId)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  useEffect(() => {
    let objectUrl: string | null = null
    void getAudioUrl(session?.audioKey).then((url) => {
      objectUrl = url
      setAudioUrl(url ?? (session?.remoteId ? remoteAudioUrl(session.remoteId) : null))
    }).catch(() => setAudioUrl(session?.remoteId ? remoteAudioUrl(session.remoteId) : null))
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [session?.audioKey, session?.remoteId])
  if (!session || !event) return <div className="empty-state"><h1>{t("未找到这个互动时刻")}</h1><button className="primary-button" onClick={() => navigate('/')}>{t("返回首页")}</button></div>
  const activeEvent = event
  const turns = session.turns.filter((turn) => event.turnIds.includes(turn.id))
  function playEvidence() {
    if (!audioRef.current || !audioUrl) return
    audioRef.current.currentTime = activeEvent.startMs / 1000
    void audioRef.current.play()
  }

  return (
    <div className="content-page moment-page">
      <header className="page-header">
        <button className="icon-button" onClick={() => navigate(`/review/${sessionId}`)} aria-label={t("返回")}><ArrowLeft size={21} /></button>
        <div><h1>{t("表达建议")}</h1></div><span />
      </header>

      <section className="moment-player">
        <button onClick={playEvidence} disabled={!audioUrl} aria-label={t("播放原声片段")}><Play size={23} fill="currentColor" /></button>
        <div><strong>{t("听原声")}</strong><span>{formatDuration(event.startMs)}–{formatDuration(event.endMs)}</span></div>
      </section>
      {audioUrl && <audio ref={audioRef} src={audioUrl} onTimeUpdate={(change) => { if (change.currentTarget.currentTime >= event.endMs / 1000) change.currentTarget.pause() }} />}

      <section className="moment-original"><h2>{t('原句')}</h2><div className="transcript-card">{turns.map((turn) => <div key={turn.id} className={`transcript-turn transcript-turn--${turn.speaker}`}><span>{turn.speaker === 'you' ? t('你') : turn.speaker === 'partner' ? t('伙伴') : t('待确认')}</span><p lang={session.targetLanguage || 'en'}>{turn.text}</p></div>)}</div></section>
      <section className="moment-suggestion"><h2>{t('可以这样说')}</h2>{event.example && <blockquote lang={session.targetLanguage || 'en'}>{event.example}</blockquote>}{event.suggestion && <p>{event.suggestion}</p>}</section>
      <details className="moment-details"><summary>{t('分析依据')}</summary><p>{event.observation}</p>{event.context !== event.observation && <p>{event.context}</p>}{event.uncertainty && <p>{event.uncertainty}</p>}<p>{session.isMockAnalysis ? t('当前为演示分析。') : session.analysisSource === 'deepseek' ? t('本提示由 AI 基于证据话轮生成。') : t('本提示来自可解释规则。')}</p></details>
      <button className="primary-button sticky-action" onClick={() => navigate(`/practice/${event.id}`)}>{t("开始练习")}<ArrowRight size={19} /></button>
    </div>
  )
}
