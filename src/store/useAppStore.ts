import type { DateFormat } from '../lib/dateFormat'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PracticeAttempt, Session } from '../types'
import { initialGuide, type GuideProgress } from '../lib/onboarding'
import type { Language } from '../lib/languages'

interface AppState {
  dateFormat: DateFormat
  setDateFormat: (dateFormat: DateFormat) => void
  nativeLanguage: Language
  targetLanguage: Language
  setLanguages: (nativeLanguage: Language, targetLanguage: Language) => void
  guides: Record<string, GuideProgress>
  updateGuide: (patch: Partial<GuideProgress>) => void
  ownerId: string | null
  sessions: Session[]
  attempts: PracticeAttempt[]
  goal: string
  addSession: (session: Session) => void
  updateSession: (id: string, patch: Partial<Session>) => void
  removeSession: (id: string) => void
  clearUserData: () => void
  activateUser: (ownerId: string) => void
  replaceAttempts: (attempts: PracticeAttempt[]) => void
  mergeRemoteSessions: (sessions: Session[]) => void
  addAttempt: (attempt: PracticeAttempt) => void
  setGoal: (goal: string) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      dateFormat: 'auto',
      setDateFormat: (dateFormat) => set({ dateFormat }),
      nativeLanguage: 'zh',
      targetLanguage: 'en',
      setLanguages: (nativeLanguage, targetLanguage) => set({ nativeLanguage, targetLanguage }),
      guides: {},
      updateGuide: (patch) => set((state) => state.ownerId ? {
        guides: { ...state.guides, [state.ownerId]: { ...initialGuide, ...state.guides[state.ownerId], ...patch } },
      } : {}),
      ownerId: null,
      sessions: [],
      attempts: [],
      goal: '延续话题',
      addSession: (session) => set((state) => ({
        sessions: [session, ...state.sessions],
        ...(state.ownerId && !state.guides[state.ownerId]?.sessionId && (state.guides[state.ownerId]?.status ?? 'active') === 'active'
          ? { guides: { ...state.guides, [state.ownerId]: { ...initialGuide, sessionId: session.id } } } : {}),
      })),
      updateSession: (id, patch) => set((state) => ({
        sessions: state.sessions.map((session) => session.id === id ? { ...session, ...patch } : session),
      })),
      removeSession: (id) => set((state) => ({ sessions: state.sessions.filter((session) => session.id !== id) })),
      clearUserData: () => set((state) => {
        const guides = { ...state.guides }
        if (state.ownerId) delete guides[state.ownerId]
        return { sessions: [], attempts: [], goal: '延续话题', guides, nativeLanguage: 'zh', targetLanguage: 'en', dateFormat: 'auto' }
      }),
      activateUser: (ownerId) => set((state) => state.ownerId === ownerId
        ? { ownerId }
        : { ownerId, sessions: [], attempts: [], goal: '延续话题', nativeLanguage: 'zh', targetLanguage: 'en', dateFormat: 'auto' }),
      replaceAttempts: (attempts) => set({ attempts }),
      mergeRemoteSessions: (remoteSessions) => set((state) => {
        const localSessions = state.sessions.filter((session) => !session.remoteId)
        const mergedRemote = remoteSessions.map((remote) => {
          const local = state.sessions.find((session) => session.remoteId === remote.remoteId)
          return local ? {
            ...remote,
            ...local,
            isFavorite: remote.isFavorite,
            processingStatus: remote.processingStatus,
            turns: remote.turns,
            events: remote.events,
            isMockAnalysis: remote.isMockAnalysis,
            analysisNotice: remote.analysisNotice,
            analysisSource: remote.analysisSource,
            speakerIds: remote.speakerIds,
            userSpeakerId: remote.userSpeakerId,
            diarizationStatus: remote.diarizationStatus,
            diarizationReason: remote.diarizationReason,
            summary: remote.summary,
            metrics: remote.metrics,
          } : remote
        })
        return { sessions: [...localSessions, ...mergedRemote].sort((a, b) => b.createdAt.localeCompare(a.createdAt)) }
      }),
      addAttempt: (attempt) => set((state) => {
        const guide = state.ownerId ? state.guides[state.ownerId] : undefined
        const completed = guide?.status === 'active' && guide.reviewed && state.sessions.some((session) => session.id === guide.sessionId)
        return {
          attempts: [attempt, ...state.attempts],
          ...(completed && state.ownerId ? { guides: { ...state.guides, [state.ownerId]: { ...guide, status: 'completed' as const } } } : {}),
        }
      }),
      setGoal: (goal) => set({ goal }),
    }),
    {
      name: 'beyond-words-state',
      version: 2,
      migrate: (persistedState) => {
        const state = persistedState as AppState
        const goalMap: Record<string, string> = {
          'Extend a topic': '延续话题',
          'Ask more questions': '主动提问',
          'Join group discussions': '参与小组讨论',
          'Ask for clarification': '请求澄清',
        }
        const scenarioMap: Record<string, string> = {
          'Casual Conversation': '日常交流',
          'English Corner': '英语角',
          'Group Discussion': '小组讨论',
          Classroom: '课堂交流',
          Interview: '英语面试',
          Other: '其他',
        }
        return {
          ...state,
          goal: goalMap[state.goal] ?? state.goal,
          ownerId: state.ownerId ?? null,
          sessions: (state.sessions || [])
            .filter((session) => session.id !== 'demo-session')
            .map((session) => ({ ...session, scenario: scenarioMap[session.scenario] ?? session.scenario })),
        }
      },
    },
  ),
)
