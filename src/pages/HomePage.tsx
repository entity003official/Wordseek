import { DateFormatSettings } from '../components/DateFormatSettings'
import { locale } from '../lib/i18n'
import { t } from '../lib/i18n'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronRight, Mic, MessageCircle, UserRound, AudioLines } from 'lucide-react'
import { LearningCalendar } from '../components/LearningCalendar'
import { StatusBadge } from '../components/StatusBadge'
import { LearningGuide } from '../components/LearningGuide'
import { formatDuration, formatShortDate } from '../lib/format'
import { useAppStore } from '../store/useAppStore'

export function HomePage() {
  const sessions = useAppStore((state) => state.sessions)
  const attempts = useAppStore((state) => state.attempts)
  const navigate = useNavigate()
  const now = new Date()
  const weekStart = new Date(now)
  weekStart.setHours(0, 0, 0, 0)
  weekStart.setDate(now.getDate() - ((now.getDay() + 6) % 7))
  const weekEnd = new Date(weekStart)
  weekEnd.setDate(weekStart.getDate() + 7)
  const weekSessions = sessions.filter((session) => session.id !== 'demo-session' && new Date(session.createdAt) >= weekStart && new Date(session.createdAt) < weekEnd)
  const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  const weekHistory = `/history?from=${dateKey(weekStart)}&to=${dateKey(new Date(weekEnd.getTime() - 1))}`
  const totalSpeakingMs = weekSessions.reduce((sum, session) => {
    const turns = session.turns.filter((turn) => turn.speaker === 'you')
    return sum + turns.reduce((turnSum, turn) => turnSum + turn.endMs - turn.startMs, 0)
  }, 0)
  const weekAttempts = attempts.filter((attempt) => new Date(attempt.createdAt) >= weekStart && new Date(attempt.createdAt) < weekEnd)
  const dayFormat = new Intl.DateTimeFormat(locale(), { month: 'numeric', day: 'numeric' })
  const activeDays = new Set(sessions.filter((session) => session.id !== 'demo-session').map((session) => new Date(session.createdAt).toDateString()))
  let streak = 0
  const cursor = new Date(now)
  cursor.setHours(0, 0, 0, 0)
  if (!activeDays.has(cursor.toDateString())) cursor.setDate(cursor.getDate() - 1)
  while (activeDays.has(cursor.toDateString())) {
    streak += 1
    cursor.setDate(cursor.getDate() - 1)
  }
  const recent = sessions.slice(0, 2)
  const assistantSession = sessions.filter((session) => session.id !== 'demo-session' && session.remoteId && session.turns.length > 0).sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0]

  return (
    <div className="home-page content-page">
      <header className="topbar home-topbar">
        <div><h1 className="home-wordmark">Beyond Words</h1><DateFormatSettings compact /></div>
        <Link className="home-account" to="/profile" aria-label={t("个人设置")}><UserRound size={20} aria-hidden="true" /></Link>
      </header>

      <LearningGuide surface="home" />
      <button className="home-record-entry" onClick={() => navigate('/recording')}>
        <span className="home-record-icon"><Mic size={23} strokeWidth={1.6} aria-hidden="true" /></span>
        <span className="home-record-label">{t("开始录音")}</span>
        <ChevronRight className="home-record-arrow" size={19} strokeWidth={1.6} aria-hidden="true" />
      </button>

      <section className="week-progress home-week" aria-label={t("本周进度")}>
        <div className="home-section-heading">
          <h2>{t("本周学习")}</h2>
          <Link to={weekHistory} aria-label={t("查看本周对话")}>{dayFormat.format(weekStart)} — {dayFormat.format(new Date(weekEnd.getTime() - 1))}<ChevronRight size={14} aria-hidden="true" /></Link>
        </div>
        <div className="home-week-stats">
          <Link to={weekHistory} aria-label={t("查看本周 {0} 次对话", [weekSessions.length])}><strong>{weekSessions.length}</strong><span>{t("次对话")}<ChevronRight size={12} /></span></Link>
          <Link to={`${weekHistory}&metric=speaking`} aria-label={t("查看本周开口时长明细")}><strong>{formatDuration(totalSpeakingMs)}</strong><span>{t("开口时长")}<ChevronRight size={12} /></span></Link>
          <Link to="/practice" aria-label={t("进入表达练习")}><strong>{weekAttempts.length}</strong><span>{t("次练习")}<ChevronRight size={12} /></span></Link>
        </div>
        <LearningCalendar />
        {streak > 0 && <Link to="/history" className="home-streak">{t("已连续记录")}<strong>{streak}</strong>{t("天")}<ChevronRight size={12} aria-hidden="true" /></Link>}
        <Link className="home-review-assistant" to={assistantSession ? `/review/${assistantSession.id}?tab=tutor` : '/recording'}>
          <span className="home-assistant-icon"><MessageCircle size={21} strokeWidth={1.7} aria-hidden="true" /></span>
          <span className="home-assistant-copy"><span>{t('复盘助手')}</span><small>{t(assistantSession ? '练口语 · 问表达' : '录音后开启')}</small></span>
          <ChevronRight size={17} aria-hidden="true" />
        </Link>
      </section>

      <section className="recent-section home-recent" aria-labelledby="home-recent-title">
        <div className="home-section-heading"><h2 id="home-recent-title">{t("最近复盘")}</h2>{recent.length > 0 && <Link to="/history">{t("查看全部")}<ChevronRight size={14} aria-hidden="true" /></Link>}</div>
        <div className="home-recent-list">{recent.length > 0 ? recent.map((session) => (
          <Link key={session.id} to={`/review/${session.id}`} className="home-recent-row">
            <span className="home-session-icon"><AudioLines size={20} aria-hidden="true" /></span>
            <span className="home-recent-row__body">
              <strong>{session.title}</strong>
              <span>{formatShortDate(session.createdAt)} · {formatDuration(session.durationMs)}</span>
              <StatusBadge status={session.processingStatus} />
            </span>
            <ChevronRight size={16} aria-hidden="true" />
          </Link>
        )) : (
          <div className="home-empty"><AudioLines size={22} aria-hidden="true" /><p>{t("录下第一段对话后，在这里复盘")}</p></div>
        )}</div>
      </section>
      <section className="home-practice-section" aria-labelledby="home-practice-title">
        <div className="home-section-heading"><h2 id="home-practice-title">{t("表达练习")}</h2></div>
        <Link className="home-practice-link" to="/practice"><MessageCircle size={20} aria-hidden="true" /><span>{t("开始练习")}</span><ChevronRight size={16} aria-hidden="true" /></Link>
      </section>
    </div>
  )
}
