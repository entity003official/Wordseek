export type ProcessingStatus = 'saved' | 'transcribing' | 'analyzing' | 'ready' | 'failed'

export interface Marker {
  id: string
  timestampMs: number
}

export interface Turn {
  id: string
  speaker: 'you' | 'partner' | 'unknown'
  speakerId?: string
  startMs: number
  endMs: number
  text: string
}

export interface InteractionEvent {
  id: string
  type: 'TOPIC_DEVELOPMENT' | 'FOLLOW_UP_QUESTION' | 'TURN_BALANCE' | 'CLARIFICATION'
  startMs: number
  endMs: number
  turnIds: string[]
  markerIds: string[]
  observation: string
  context: string
  suggestion: string
  example: string
  uncertainty: string
}

export interface ConversationSummary {
  title: string
  description: string
  keywords: string[]
}

export interface ConversationMetrics {
  userSpeakingMs: number
  speakingShare: number
  userTurnCount: number
  totalTurnCount: number
}

export interface SpeechExecution {
  provider: 'qwen'
  model?: string | null
  providerTaskId?: string | null
  latencyMs: number
  audioDurationMs: number
  retryCount: number
  resumedExistingTask: boolean
}

export interface AIReview {
  learning_points?: Array<{
    kind: 'vocabulary' | 'synonym' | 'natural_expression'
    original: string
    explanation: string
    alternative: string
    usage_note: string
    example: string
    evidence_turn_ids: string[]
  }>
  summary: {
    title: string
    summary: string
    topics: string[]
    evidence_turn_ids: string[]
    limitations: string[]
  }
  scene: {
    scene_type: 'casual_chat' | 'classroom' | 'group_discussion' | 'interview' | 'meeting' | 'service_encounter' | 'other'
    communication_goal: string
    context_notes: string[]
    evidence_turn_ids: string[]
    confidence: number
  }
  events: Array<{
    type: InteractionEvent['type']
    observation: string
    context: string
    suggestion: string
    example: string
    evidence_turn_ids: string[]
    confidence: number
  }>
}

export interface Session {
  isFavorite?: boolean
  targetLanguage?: 'zh' | 'en' | 'ja'
  id: string
  title: string
  scenario: string
  createdAt: string
  durationMs: number
  markers: Marker[]
  processingStatus: ProcessingStatus
  audioKey?: string
  remoteId?: string
  syncStatus?: 'local' | 'syncing' | 'synced' | 'failed'
  isMockAnalysis: boolean
  analysisNotice?: string
  analysisSource?: 'local-rules' | 'deepseek'
  aiReview?: AIReview
  speakerIds?: string[]
  userSpeakerId?: string
  diarizationStatus?: 'complete' | 'unavailable' | 'failed' | 'mock'
  diarizationReason?: string | null
  summary?: ConversationSummary
  metrics?: ConversationMetrics
  speechExecution?: SpeechExecution
  turns: Turn[]
  events: InteractionEvent[]
}

export interface PracticeAttempt {
  id: string
  eventId: string
  createdAt: string
  response: string
  feedback: string[]
}
