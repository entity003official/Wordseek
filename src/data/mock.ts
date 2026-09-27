import type { InteractionEvent, Turn } from '../types'

export const mockTurns: Turn[] = [
  { id: 'turn-1', speaker: 'partner', startMs: 2600, endMs: 6700, text: 'What do you think about organizing an English movie night?' },
  { id: 'turn-2', speaker: 'you', startMs: 7600, endMs: 9100, text: "Yeah, it sounds good." },
  { id: 'turn-3', speaker: 'partner', startMs: 10300, endMs: 13200, text: 'Okay... What kind of movies do you like?' },
  { id: 'turn-4', speaker: 'you', startMs: 14200, endMs: 18400, text: 'Maybe a comedy. It would be easy for everyone to follow.' },
  { id: 'turn-5', speaker: 'partner', startMs: 19100, endMs: 22500, text: 'That makes sense. Do you have one in mind?' },
]

export function createMockEvent(markerId = 'demo-marker'): InteractionEvent {
  return {
    id: 'topic-development-1',
    type: 'TOPIC_DEVELOPMENT',
    startMs: 2600,
    endMs: 13200,
    turnIds: ['turn-1', 'turn-2', 'turn-3'],
    markerIds: [markerId],
    observation: '对方邀请你表达看法。你简短表示赞同，随后由对方提出新问题来继续对话。',
    context: '简短回答本身并不是问题。在这个语境里，对方的问题为补充理由、继续展开想法留出了空间。',
    suggestion: '如果你希望继续这个话题，可以补充一个理由，再邀请对方参与进来。',
    example: "I like the idea because it gives us a relaxed way to practise. What kind of film would work for everyone?",
    uncertainty: '这一解释基于当前话轮序列，仍需结合原始录音核对。',
  }
}

export const demoSession = {
  id: 'demo-session',
  title: '英语电影之夜',
  scenario: '日常交流',
  createdAt: new Date(Date.now() - 86400000).toISOString(),
  durationMs: 24500,
  markers: [{ id: 'demo-marker', timestampMs: 8900 }],
  processingStatus: 'ready' as const,
  isMockAnalysis: true,
  turns: mockTurns,
  events: [createMockEvent()],
}
