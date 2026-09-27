import { beforeEach, describe, expect, it } from 'vitest'
import { guideState, initialGuide } from './onboarding'
import { useAppStore } from '../store/useAppStore'
import type { Session } from '../types'

const session: Session = { id: 'recording-1', title: 'Test', scenario: '日常交流', createdAt: '2026-09-27', durationMs: 2000, markers: [], processingStatus: 'saved', isMockAnalysis: false, turns: [], events: [] }
const attempt = { id: 'attempt-1', eventId: 'event-1', createdAt: '2026-09-27', response: 'Hello', feedback: ['Saved'] }

describe('guided learning progress', () => {
  beforeEach(() => useAppStore.setState({ ownerId: 'user-a', guides: {}, sessions: [], attempts: [] }))
  it('starts at recording and excludes demonstration data', () => {
    expect(guideState(initialGuide, []).step).toBe(0)
    expect(guideState(initialGuide, [{ ...session, isMockAnalysis: true }]).step).toBe(0)
  })
  it('resumes a saved recording without pretending the review is finished', () => {
    expect(guideState(initialGuide, [session]).step).toBe(1)
    expect(guideState(initialGuide, [{ ...session, processingStatus: 'ready' }]).step).toBe(1)
  })
  it('does not carry a deleted recording review over to a different recording', () => {
    expect(guideState({ ...initialGuide, sessionId: 'deleted', reviewed: true }, [session]).step).toBe(1)
  })
  it('selects a saved recording and requires review before successful practice completes the guide', () => {
    const store = useAppStore.getState()
    store.addSession(session)
    store.addAttempt(attempt)
    expect(useAppStore.getState().guides['user-a'].status).toBe('active')
    store.updateGuide({ reviewed: true })
    store.addAttempt({ ...attempt, id: 'attempt-2' })
    expect(useAppStore.getState().guides['user-a'].status).toBe('completed')
  })
  it('keeps skipping scoped to the account and preserves it after switching back', () => {
    const store = useAppStore.getState()
    store.updateGuide({ status: 'dismissed' })
    store.activateUser('user-b')
    expect(useAppStore.getState().guides['user-b']).toBeUndefined()
    store.activateUser('user-a')
    expect(useAppStore.getState().guides['user-a'].status).toBe('dismissed')
  })
  it('does not reopen a skipped guide when a new recording is saved', () => {
    const store = useAppStore.getState()
    store.updateGuide({ status: 'dismissed' })
    store.addSession(session)
    expect(useAppStore.getState().guides['user-a'].status).toBe('dismissed')
  })
  it('clears only the current account guide when deleting its learning data', () => {
    const store = useAppStore.getState()
    store.updateGuide({ status: 'dismissed' })
    store.activateUser('user-b')
    store.updateGuide({ status: 'dismissed' })
    store.clearUserData()
    expect(useAppStore.getState().guides['user-b']).toBeUndefined()
    expect(useAppStore.getState().guides['user-a'].status).toBe('dismissed')
  })
})
