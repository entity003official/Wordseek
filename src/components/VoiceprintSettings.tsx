import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getVoiceprint, deleteVoiceprint } from '../lib/api'
import { t } from '../lib/i18n'
export function VoiceprintSettings() {
  const [enrolled, setEnrolled] = useState<boolean | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const navigate = useNavigate()
  useEffect(() => { let alive = true; setError(''); setEnrolled(null); void getVoiceprint().then((v) => { if (alive) setEnrolled(v.enrolled) }).catch((reason) => { if (alive) setError(reason instanceof Error ? reason.message : '声纹状态读取失败') }); return () => { alive = false } }, [reload])
  async function remove() {
    setBusy(true)
    try { await deleteVoiceprint(); setEnrolled(false); setError('') } catch { setError('删除失败，请重试') } finally { setBusy(false) }
  }
  return <section className="profile-editor"><h2>{t('我的声纹')}</h2><p>{t(enrolled ? '已保存，仅在本地匹配本人声音。' : '在复盘中回听并确认自己的发言，再保存声纹。')}</p>{enrolled ? <button className="secondary-button" disabled={busy} onClick={() => void remove()}>{t('删除声纹')}</button> : <button className="secondary-button" onClick={() => navigate('/history')}>{t('选择录音')}</button>}{error && <p role="alert">{t(error)}<button className="text-button" onClick={() => setReload((n) => n + 1)}>{t('重试')}</button></p>}</section>
}
