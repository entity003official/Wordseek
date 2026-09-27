import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getWeeklyJournal, generateWeeklyJournal } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import { t } from '../lib/i18n'
import { formatShortDate } from '../lib/format'

function weekDate(offset: number) {
  const date = new Date(); date.setHours(12, 0, 0, 0)
  date.setDate(date.getDate() - (date.getDay() + 6) % 7 + offset * 7)
  return date
}
function dateKey(date: Date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
export function WeeklyJournal() {
  const [offset, setOffset] = useState(0)
  const owner = useAppStore((s) => s.ownerId)
  const start = weekDate(offset); const end = new Date(start); end.setDate(end.getDate() + 6)
  const week = dateKey(start)
  return <section className="weekly-journal">
    <div className="journal-week">
      <button className="icon-button" aria-label={t('上一周')} onClick={() => setOffset((n) => n - 1)}><ChevronLeft size={18} /></button>
      <div><span>{formatShortDate(start.toISOString())} — {formatShortDate(end.toISOString())}</span>{offset !== 0 && <button className="text-button" onClick={() => setOffset(0)}>{t('本周')}</button>}</div>
      <button className="icon-button" aria-label={t('下一周')} disabled={offset >= 0} onClick={() => setOffset((n) => n + 1)}><ChevronRight size={18} /></button>
    </div>
    <WeekEntries key={`${owner}-${week}`} week={week} />
  </section>
}
function WeekEntries({week}: {week: string}) {
  const owner = useAppStore((s) => s.ownerId)
  const sessions = useAppStore((s) => s.sessions)
  const client = useQueryClient()
  const queryKey = ['weekly-journal', owner, week]
  const journal = useQuery({queryKey, queryFn: () => getWeeklyJournal(week), retry: false})
  const start = new Date(`${week}T00:00:00`)
  const end = new Date(start); end.setDate(end.getDate() + 7)
  const available = sessions.filter((s) => s.remoteId)
  const inWeek = available.filter((s) => new Date(s.createdAt) >= start && new Date(s.createdAt) < end)
  const [choosing, setChoosing] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)
  async function generate(ids?: string[]) {
    if (pending.current) return
    pending.current = true; setBusy(true); setError('')
    try {
      await client.cancelQueries({queryKey})
      const result = await generateWeeklyJournal(week, ids)
      client.setQueryData(queryKey, result)
      setChoosing(false)
    } catch (reason) { setError(reason instanceof Error ? reason.message : '生成失败，请重试') }
    finally { pending.current = false; setBusy(false) }
  }
  function sourceLink(id: string) { return `/review/${sessions.find((s) => s.remoteId === id)?.id || `remote-${id}`}` }
  return <>
    <div className="journal-actions">
      <button className="primary-button" disabled={busy} onClick={() => void generate()}>{t(busy ? '正在整理…' : journal.data ? '重新生成本周' : '生成本周周记')}</button>
      <button className="text-button" disabled={busy} onClick={() => { setSelected(inWeek.map((s) => s.remoteId!)); setChoosing((v) => !v); setError('') }}>{t('选择复盘')}</button>
    </div>
    {choosing && <section className="journal-picker" aria-label={t('选择复盘')}>
      {available.length ? <>
        <div className="journal-picker-tools"><button className="text-button" disabled={busy} onClick={() => setSelected(inWeek.map((s) => s.remoteId!))}>{t('仅选本周')}</button><button className="text-button" disabled={busy} onClick={() => setSelected([])}>{t('清空选择')}</button></div>
        <div className="journal-picker-list">{available.map((session) => <label key={session.id}><input type="checkbox" checked={selected.includes(session.remoteId!)} disabled={busy} onChange={(e) => setSelected((old) => e.target.checked ? [...old, session.remoteId!] : old.filter((id) => id !== session.remoteId))} /><span>{session.title}<small>{formatShortDate(session.createdAt)}</small></span></label>)}</div>
        <button className="secondary-button" disabled={busy || !selected.length || selected.length > 100} onClick={() => void generate(selected)}>{t('生成周记（{0}）', [selected.length])}</button>
      </> : <p className="journal-empty">{t('还没有复盘记录')}</p>}
    </section>}
    {error && <p className="speaker-error" role="alert">{t(error)}</p>}
    {journal.isPending && !busy && <p role="status">{t('载入中')}</p>}
    {journal.isError && !busy && <p role="alert">{t('周记加载失败')} <button className="text-button" onClick={() => void journal.refetch()}>{t('重试')}</button></p>}
    {journal.data ? <>
      <p className="journal-origin">{t('来自 {0} 条复盘', [journal.data.sources.length])}{journal.data.skipped > 0 && <span> · {t('{0} 条尚无学习要点', [journal.data.skipped])}</span>}</p>
      {(['words', 'sentences'] as const).map((group) => <section className="journal-group" key={group}>
        <header><h2>{t(group === 'words' ? '单词' : '句子')}</h2></header>
        {journal.data![group].map((entry, i) => <div className="journal-entry" key={i}><div><p>{entry.text}</p>{entry.note && <small>{entry.note}</small>}</div><Link className="journal-source" to={sourceLink(entry.source_id)} aria-label={t('查看来源复盘')}>{t('来源')}</Link></div>)}
        {!journal.data![group].length && <p className="journal-empty">{t('暂无学习要点')}</p>}
      </section>)}
    </> : !journal.isPending && !journal.isError && <p className="journal-empty">{t('从复盘中整理单词和句子')}</p>}
  </>
}
