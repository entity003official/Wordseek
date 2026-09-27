import type { Language } from './languages'
import type { PracticeLibraryCategory } from './api'

export function practiceScopeKey(owner: string | null, native: Language, target: Language) {
  return `${owner || 'anonymous'}-${native}-${target}`
}

export function scenesForCategory(categories: PracticeLibraryCategory[], categoryCode: string) {
  if (!categoryCode) return []
  return categories.find((category) => category.code === categoryCode)?.scenes || []
}

export function nextPracticePage(current: number, total: number, pageSize: number) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return current >= pages ? 1 : current + 1
}
