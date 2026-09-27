import { WeeklyJournal } from '../components/WeeklyJournal'
import { Search } from 'lucide-react'
import { FavoriteButton } from '../components/FavoriteButton'
import { t } from '../lib/i18n'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { StatusBadge } from '../components/StatusBadge'
import { LearningGuide } from '../components/LearningGuide'
import { deleteAudio } from '../lib/audioDb'
import { deleteRemoteSession } from '../lib/api'
import { formatDuration } from '../lib/format'
import { useAppStore } from '../store/useAppStore'

export function HistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const validDate = (value: string | null) => value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : ''
  const journalOpen = searchParams.get('view') === 'journal'
  const favoritesOnly = searchParams.get('view') === 'favorites'
  const selectedDate = validDate(searchParams.get('date'))
  const from = validDate(searchParams.get('from'))
  const to = validDate(searchParams.get('to'))
  const speaking = searchParams.get('metric') === 'speaking'
  const dateFiltered = Boolean(selectedDate || from || to)
  const sessions = useAppStore((state) => state.sessions)
  const removeSession = useAppStore((state) => state.removeSession)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const filtered = useMemo(() => sessions.filter((session) => {
    if (favoritesOnly && !session.isFavorite) return false
    const created = new Date(session.createdAt)
    const date = `${created.getFullYear()}-${String(created.getMonth() + 1).padStart(2, '0')}-${String(created.getDate()).padStart(2, '0')}`
    if (dateFiltered && session.id === 'demo-session') return false
    if (selectedDate && date !== selectedDate) return false
    if (from && date < from || to && date > to) return false
    const text = `${session.title} ${session.scenario}`.toLowerCase()
    return text.includes(query.trim().toLowerCase())
  }), [query, sessions, selectedDate, from, to, dateFiltered, favoritesOnly])

  async function remove(id: string) {
    const session = sessions.find((item) => item.id === id)
    if (!session || !window.confirm(t("确定删除“{0}”及其录音吗？此操作无法撤销。", [session.title]))) return
    setError('')
    try {
      if (session.remoteId) await deleteRemoteSession(session.remoteId)
      await deleteAudio(session.audioKey)
      removeSession(session.id)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '删除失败，请重试。')
    }
  }

  return (
    <div className="content-page history-page">
      <LearningGuide surface="history" />
      <header className="page-header">
        <div><h1>{t("复盘")}</h1>{!journalOpen && <p className="header-subtitle">{filtered.length}{' '}{t("段对话")}</p>}</div>

      </header>
      <nav className="history-views" aria-label={t('复盘筛选')}>
        {(['all', 'favorites', 'journal'] as const).map((view) => <button key={view} type="button" aria-pressed={view === (journalOpen ? 'journal' : favoritesOnly ? 'favorites' : 'all')} onClick={() => { const next = new URLSearchParams(searchParams); if (view === 'all') next.delete('view'); else next.set('view', view); setSearchParams(next) }}>{t(view === 'journal' ? '周记' : view === 'favorites' ? '收藏夹' : '全部')}</button>)}
      </nav>
      {journalOpen ? <WeeklyJournal /> : <>
      <label className="history-search history-search-always"><Search size={18} aria-hidden="true" /><input type="search" aria-label={t("搜索标题或场景")} value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("搜索对话")} /></label>
      {(dateFiltered || speaking) && <div className="history-filter-bar"><span>{selectedDate || t("{0} 至 {1}", [from || '最早', to || '今天'])}{speaking ? t(" · 开口时长") : ''}</span><button className="text-button" onClick={() => setSearchParams(favoritesOnly ? { view: 'favorites' } : {})}>{t("查看全部")}</button></div>}
      {speaking && <p className="history-speaking-note">{t("仅统计已确认为「你」的话轮；未确认身份时不计入。")}</p>}

      {error && <p className="speaker-error">{t(error)}</p>}
      <div className="session-list history-list">
        {filtered.map((session) => (
          <div className="session-card history-card" key={session.id}>
            <Link to={`/review/${session.id}`} className="history-card__link">
              <span className="session-card__body"><strong>{session.title}</strong><small>{formatDuration(session.durationMs)} · {session.markers.length}{t("个标记")}</small><StatusBadge status={session.processingStatus} />{speaking && <small>{t("你的开口时长：")}{session.turns.some((turn) => turn.speaker === 'you') ? formatDuration(session.turns.filter((turn) => turn.speaker === 'you').reduce((sum, turn) => sum + turn.endMs - turn.startMs, 0)) : t("暂无已确认话轮")}</small>}</span>
            </Link>
            <FavoriteButton session={session} />
            {session.id !== 'demo-session' && <button className="history-delete" onClick={() => void remove(session.id)}>{t("删除")}</button>}
          </div>
        ))}
        {!filtered.length && <div className="empty-state">{query ? t("没有匹配的对话") : dateFiltered ? t("这段时间没有录音记录") : favoritesOnly ? t("还没有收藏，点击对话旁的书签即可添加") : t("还没有复盘记录")}</div>}
      </div>
      </>}
    </div>
  )
}
