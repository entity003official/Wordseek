import { displayDate } from './dateFormat'
import { useAppStore } from '../store/useAppStore'
import { locale } from './i18n'
export function formatDuration(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export function formatShortDate(value: string) {
  return displayDate(new Date(value), useAppStore.getState().dateFormat || 'auto', locale())
}
