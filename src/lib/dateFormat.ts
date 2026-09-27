export type DateFormat = 'auto' | 'zh' | 'ymd' | 'dmy' | 'mdy' | 'iso'
export const dateFormats: DateFormat[] = ['auto', 'zh', 'ymd', 'dmy', 'mdy', 'iso']
export function displayDate(date: Date, format: DateFormat, locale: string, weekday = false) {
  if (format === 'auto') return new Intl.DateTimeFormat(locale, { month: weekday ? 'long' : 'short', day: 'numeric', ...(weekday ? {weekday: 'long' as const} : {}) }).format(date)
  const y = date.getFullYear(), m = String(date.getMonth()+1).padStart(2,'0'), d = String(date.getDate()).padStart(2,'0')
  const text = format === 'zh' ? `${y}年${Number(m)}月${Number(d)}日` : format === 'ymd' ? `${y}/${m}/${d}` : format === 'dmy' ? `${d}/${m}/${y}` : format === 'mdy' ? `${m}/${d}/${y}` : `${y}-${m}-${d}`
  return weekday ? `${text} · ${new Intl.DateTimeFormat(locale, {weekday:'long'}).format(date)}` : text
}
