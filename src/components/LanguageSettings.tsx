import { useState } from 'react'
import { useAppStore } from '../store/useAppStore'
import { languageOptions, type Language } from '../lib/languages'
import { updatePreferences } from '../lib/api'
import { t } from '../lib/i18n'

export function LanguageSettings({ compact = false, disabled = false, beforeChange }: { compact?: boolean; disabled?: boolean; beforeChange?: () => boolean }) {
  const native = useAppStore((s) => s.nativeLanguage)
  const target = useAppStore((s) => s.targetLanguage)
  const setLanguages = useAppStore((s) => s.setLanguages)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function change(n: Language, l: Language) {
    if (beforeChange && !beforeChange()) return
    setBusy(true)
    setError('')
    const owner = useAppStore.getState().ownerId
    try {
      const result = await updatePreferences({ native_language: n, target_language: l })
      if (owner === useAppStore.getState().ownerId) setLanguages(result.native_language, result.target_language)
    } catch (reason) { setError(t(reason instanceof Error ? reason.message : '语言设置保存失败，请重试。')) }
    finally { setBusy(false) }
  }
  return <section className={`language-settings${compact ? ' is-compact' : ''}`} aria-label={t('语言设置')}>
    {!compact && <label><span>{t('我的母语')}</span><select value={native} disabled={disabled || busy} onChange={(e) => void change(e.target.value as Language, target)}>{languageOptions.map((l) => <option lang={l.code} key={l.code} value={l.code}>{l.label}</option>)}</select></label>}
    <label><span>{t('我想学')}</span><select value={target} disabled={disabled || busy} onChange={(e) => void change(native, e.target.value as Language)}>{languageOptions.map((l) => <option lang={l.code} key={l.code} value={l.code}>{l.label}</option>)}</select></label>
    {busy && <small role="status">{t('保存中…')}</small>}
    {error && <p role="alert">{error}</p>}
  </section>
}
