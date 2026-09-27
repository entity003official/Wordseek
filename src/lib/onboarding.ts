import type { Session } from '../types'

export interface GuideProgress {
  status: 'active' | 'dismissed' | 'completed'
  sessionId: string | null
  reviewed: boolean
  startFresh?: boolean
}

export const initialGuide: GuideProgress = { status: 'active', sessionId: null, reviewed: false }

export function guideState(guide: GuideProgress, sessions: Session[]) {
  const recordings = sessions.filter((session) => session.id !== 'demo-session' && !session.isMockAnalysis)
  const session = recordings.find((item) => item.id === guide.sessionId) ?? (guide.startFresh ? undefined : recordings[0])
  const reviewed = Boolean(session && guide.reviewed && guide.sessionId === session.id)
  const step = !session ? 0 : reviewed ? 2 : 1
  return { session, step, reviewed }
}
