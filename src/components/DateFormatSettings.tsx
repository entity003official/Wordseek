import { useId, useState } from 'react'
import { useAppStore } from '../store/useAppStore'
import { dateFormats, displayDate, type DateFormat } from '../lib/dateFormat'
import { locale, t } from '../lib/i18n'
import { updatePreferences } from '../lib/api'
export function DateFormatSettings({ compact = false }: { compact?: boolean }) {
  const id = useId()
  const format = useAppStore((s) => s.dateFormat) || 'auto'
  const setFormat = useAppStore((s) => s.setDateFormat)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const labels = {auto:'跟随语言', zh:'中文日期', ymd:'年/月/日', dmy:'日/月/年', mdy:'月/日/年', iso:'年-月-日'}
  async function change(next: DateFormat) {
    const owner = useAppStore.getState().ownerId
    setBusy(true); setError('')
    try { const saved = await updatePreferences({date_format: next}); if (owner === useAppStore.getState().ownerId) setFormat(saved.date_format) }
    catch { setError('日期格式保存失败，请重试') }
    finally { setBusy(false) }
  }
  return <div className={`date-format-setting${compact ? ' is-compact' : ''}`}>
    {compact && <span className="home-date" aria-hidden="true">{displayDate(new Date(), format, locale(), true)}</span>}
    <select id={id} value={format} disabled={busy} onChange={(e) => void change(e.target.value as DateFormat)} aria-label={t('日期格式')}>
      {dateFormats.map((item) => <option key={item} value={item}>{t(labels[item])} · {displayDate(new Date(2026,8,27), item, locale())}</option>)}
    </select>
    {error && <p role="alert">{t(error)}</p>}
  </div>
}
