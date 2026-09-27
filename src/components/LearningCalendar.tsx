import { t } from '../lib/i18n'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAppStore } from '../store/useAppStore'

const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`

export function LearningCalendar() {
  const sessions = useAppStore((state) => state.sessions)
  const attempts = useAppStore((state) => state.attempts)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const todayKey = dateKey(today)
  const [selected, setSelected] = useState(todayKey)
  const [yearView, setYearView] = useState(false)
  const scroll = useRef<HTMLDivElement>(null)
  const weeks = yearView ? 53 : 13
  const start = new Date(today)
  start.setDate(start.getDate() - (start.getDay() + 6) % 7 - (weeks - 1) * 7)
  const counts = new Map<string, { conversations: number; practices: number }>()
  for (const session of sessions) {
    if (session.id === 'demo-session' || session.isMockAnalysis) continue
    const key = dateKey(new Date(session.createdAt))
    const value = counts.get(key) ?? { conversations: 0, practices: 0 }
    counts.set(key, { ...value, conversations: value.conversations + 1 })
  }
  for (const attempt of attempts) {
    const key = dateKey(new Date(attempt.createdAt))
    const value = counts.get(key) ?? { conversations: 0, practices: 0 }
    counts.set(key, { ...value, practices: value.practices + 1 })
  }
  const days = Array.from({ length: weeks * 7 }, (_, index) => {
    const date = new Date(start)
    date.setDate(start.getDate() + index)
    const key = dateKey(date)
    const count = counts.get(key)
    return { date, key, total: (count?.conversations ?? 0) + (count?.practices ?? 0), future: date > today }
  })
  const current = counts.get(selected) ?? { conversations: 0, practices: 0 }
  useEffect(() => { if (scroll.current) scroll.current.scrollLeft = scroll.current.scrollWidth }, [yearView])
  return <section className="learning-calendar" aria-label={t("学习热力日历")}>
    <div className="learning-calendar-heading"><strong>{t("学习日历")}</strong><button type="button" onClick={() => { setYearView((value) => !value); setSelected(todayKey) }} aria-label={yearView ? t("切换到近13周") : t("切换到近一年")}>{yearView ? t("近一年") : t("近13周")} <span aria-hidden="true">⌄</span></button></div>
    <div className="learning-calendar-scroll" ref={scroll}>
      <div className="learning-calendar-grid" style={{ gridTemplateColumns: `20px repeat(${weeks}, 20px)` }}>
        {Array.from({ length: weeks }, (_, index) => {
          const date = days[index * 7].date
          const previous = index ? days[(index - 1) * 7].date : null
          return <span key={index} className="learning-calendar-month" style={{ gridColumn: index + 2, gridRow: 1 }}>{!previous || previous.getMonth() !== date.getMonth() ? t("{0}月", [date.getMonth() + 1]) : ''}</span>
        })}
        {['一', '', '三', '', '五', '', '日'].map((label, index) => <span className="learning-calendar-weekday" key={index} style={{ gridColumn: 1, gridRow: index + 2 }}>{t(label)}</span>)}
        {days.map((day, index) => day.future ? <span key={day.key} style={{ gridColumn: Math.floor(index / 7) + 2, gridRow: index % 7 + 2 }} /> : <button
          type="button" key={day.key} className={`learning-calendar-day${selected === day.key ? ' is-selected' : ''}`}
          style={{ gridColumn: Math.floor(index / 7) + 2, gridRow: index % 7 + 2 }}
          aria-label={t("{0}，{1} 次学习", [day.key, day.total])} aria-pressed={selected === day.key} aria-current={day.key === todayKey ? 'date' : undefined}
          title={t("{0} · {1} 次学习", [day.key, day.total])} onClick={() => setSelected(day.key)}
          onKeyDown={(event) => {
            const delta = { ArrowUp: -1, ArrowDown: 1, ArrowLeft: -7, ArrowRight: 7 }[event.key]
            if (delta === undefined) return
            event.preventDefault()
            const destination = days[index + delta]
            if (destination && !destination.future) {
              setSelected(destination.key)
              event.currentTarget.parentElement?.querySelector<HTMLButtonElement>(`[data-date="${destination.key}"]`)?.focus()
            }
          }} data-date={day.key} tabIndex={selected === day.key ? 0 : -1}>
          <span data-level={Math.min(4, day.total)} />
        </button>)}
      </div>
    </div>
    <div className="learning-calendar-legend" aria-label={t("颜色越深表示当天学习次数越多")}><span>{t("少")}</span>{[0, 1, 2, 3, 4].map((level) => <i key={level} data-level={level} />)}<span>{t("多")}</span></div>
    <div className="learning-calendar-detail" aria-live="polite"><span>{selected.slice(5).replace('-', '/')} · {current.conversations}{' '}{t("次对话 ·")} {current.practices}{' '}{t("次练习")}</span><Link to={`/history?date=${selected}`}>{t("查看对话")}</Link></div>
  </section>
}
