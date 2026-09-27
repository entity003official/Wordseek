import type { UserAccount } from '../lib/api'

export type AdminAccess = 'login' | 'forbidden' | 'granted'

export function getAdminAccess(user: Pick<UserAccount, 'role'> | null): AdminAccess {
  if (!user) return 'login'
  return user.role === 'admin' ? 'granted' : 'forbidden'
}

export function getAdminDestination(state: unknown): string {
  if (!state || typeof state !== 'object' || !('from' in state)) return '/admin/overview'
  const from = (state as { from?: unknown }).from
  if (typeof from !== 'string' || !from.startsWith('/admin') || from === '/admin/login' || from.startsWith('//')) {
    return '/admin/overview'
  }
  return from
}
