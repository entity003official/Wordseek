import { useRef, useState } from 'react'
import { Bookmark } from 'lucide-react'
import { updateRemoteSession } from '../lib/api'
import { t } from '../lib/i18n'
import { useAppStore } from '../store/useAppStore'
import type { Session } from '../types'

export function FavoriteButton({ session }: { session: Session }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)
  async function toggle() {
    if (pending.current) return
    pending.current = true
    const owner = useAppStore.getState().ownerId
    const next = !session.isFavorite
    setBusy(true)
    setError('')
    try {
      if (session.remoteId) await updateRemoteSession(session.remoteId, { is_favorite: next })
      if (useAppStore.getState().ownerId === owner) useAppStore.getState().updateSession(session.id, { isFavorite: next })
    } catch {
      setError(t('收藏未保存，请重试'))
    } finally {
      pending.current = false
      setBusy(false)
    }
  }
  return <div className="favorite-control">
    <button type="button" className="favorite-button" disabled={busy} aria-pressed={Boolean(session.isFavorite)} aria-label={t(session.isFavorite ? '取消收藏' : '收藏对话')} title={t(session.isFavorite ? '取消收藏' : '收藏对话')} onClick={() => void toggle()}>
      <Bookmark size={19} strokeWidth={1.7} fill={session.isFavorite ? 'currentColor' : 'none'} aria-hidden="true" />
    </button>
    {error && <span className="favorite-error" role="alert">{error}</span>}
  </div>
}
