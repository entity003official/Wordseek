import type { DateFormat } from './dateFormat'
import type { AIReview, InteractionEvent, Marker, ProcessingStatus, Session, Turn } from '../types'
import type { Language } from './languages'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

function cookie(name: string): string {
  const prefix = `${name}=`
  const entry = document.cookie.split(';').map((item) => item.trim()).find((item) => item.startsWith(prefix))
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : ''
}

interface RemoteMarker {
  id: string
  timestamp_ms: number
}

interface RemoteTurn {
  id: string
  speaker_id: string
  start_ms: number
  end_ms: number
  text: string
}

interface RemoteEvent {
  id: string
  type: InteractionEvent['type']
  start_ms: number
  end_ms: number
  turn_ids: string[]
  marker_ids: string[]
  confidence?: number | null
  insight: {
    observation: string
    context: string
    suggestion: string
    example?: string
    evidence_turn_ids: string[]
  }
}

interface RemoteSpeaker {
  id: string
  user_confirmed_identity?: boolean | null
}

export interface RemoteAnalysis {
  user_speaker_id?: string | null
  identity_source?: 'manual' | 'voiceprint'
  schema_version?: 'speech-analysis.v2'
  mode: 'mock' | 'real'
  notice?: string
  semantic_provider?: 'local-rules' | 'deepseek'
  ai_review?: AIReview
  speakers?: RemoteSpeaker[]
  diarization?: {
    status: 'complete' | 'unavailable' | 'failed' | 'mock'
    reason?: string | null
  }
  summary?: {
    title: string
    description: string
    keywords: string[]
  }
  metrics?: {
    user_speaking_ms: number
    speaking_share: number
    user_turn_count: number
    total_turn_count: number
  }
  turns: RemoteTurn[]
  events: RemoteEvent[]
  execution?: {
    provider: 'qwen'
    model?: string | null
    provider_task_id?: string | null
    latency_ms: number
    audio_duration_ms: number
    retry_count: number
    resumed_existing_task: boolean
  }
}

export interface RemoteHealth {
  status: string
  analysis_mode: 'qwen_cloud' | 'unconfigured'
  speech?: {
    default_backend: 'qwen'
    qwen: { available: boolean; model: string; short_model: string; region: string; workspace_domain: boolean; audio_url_mode: string }
  }
}

export interface RemoteSession {
  is_favorite?: boolean
  target_language?: Language
  id: string
  title: string
  scenario: string
  created_at: string
  duration_ms: number
  processing_status: ProcessingStatus
  user_speaker_id?: string | null
  audio_path?: string | null
  failure_reason?: string | null
  markers: RemoteMarker[]
  analysis?: RemoteAnalysis | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || 'GET').toUpperCase()
  const headers = new Headers(init?.headers)
  if (typeof init?.body === 'string' && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = cookie('bw_csrf')
    if (csrf) headers.set('X-CSRF-Token', csrf)
  }
  let response: Response
  try { response = await fetch(`${API_BASE}${path}`, { ...init, method, headers, credentials: 'include' }) }
  catch { throw new Error('无法连接服务，请检查网络或刷新页面后重试。') }
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { detail?: string; error?: { message?: string } } | null
    throw new Error(detail?.error?.message || detail?.detail || `请求失败（${response.status}）`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function createRemoteSession(title: string, scenario: string, targetLanguage: Language = 'en') {
  return request<RemoteSession>('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, scenario, target_language: targetLanguage }),
  })
}

export function uploadRemoteAudio(sessionId: string, blob: Blob, durationMs: number) {
  const form = new FormData()
  form.append('audio', blob, `recording.${blob.type.includes('ogg') ? 'ogg' : blob.type.includes('mp4') ? 'mp4' : 'webm'}`)
  return request<{ status: string }>(`/sessions/${sessionId}/audio?duration_ms=${durationMs}`, { method: 'POST', body: form })
}

export function addRemoteMarker(sessionId: string, marker: Marker) {
  return request<RemoteMarker>(`/sessions/${sessionId}/markers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: marker.id, timestamp_ms: marker.timestampMs }),
  })
}

export interface AnalyzeOptions {
  language_hints: string[]
  speaker_policy: { mode: 'auto' | 'expected'; min_count: number; max_count: number; expected_count: number | null }
  cloud_audio_consent: { accepted: boolean; version: string }
}

export function startRemoteAnalysis(sessionId: string, options: AnalyzeOptions) {
  return request<{ processing_status: ProcessingStatus; requested_backend: string }>(`/sessions/${sessionId}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  })
}

export function getRemoteStatus(sessionId: string) {
  return request<{ processing_status: ProcessingStatus; failure_reason?: string | null; error_code?: string | null; retryable?: boolean }>(`/sessions/${sessionId}/status`)
}

export function getRemoteAnalysis(sessionId: string) {
  return request<RemoteAnalysis>(`/sessions/${sessionId}/analysis`)
}

export function getRemoteHealth() {
  return request<RemoteHealth>('/health')
}

export function confirmRemoteSpeaker(sessionId: string, userSpeakerId: string) {
  return request<{ user_speaker_id: string; confirmed: boolean; analysis: RemoteAnalysis }>(`/sessions/${sessionId}/speakers`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_speaker_id: userSpeakerId }),
  })
}

export function updateRemoteSession(sessionId: string, patch: { title?: string; scenario?: string; is_favorite?: boolean }) {
  return request<RemoteSession>(`/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
}

export function deleteRemoteSession(sessionId: string) {
  return request<void>(`/sessions/${sessionId}`, { method: 'DELETE' })
}

export function updateRemoteTurn(sessionId: string, turnId: string, patch: { text?: string; speaker_id?: string }) {
  return request<{ analysis: RemoteAnalysis }>(`/sessions/${sessionId}/turns/${turnId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
}

export interface RemotePractice {
  target_language: Language
  id: string
  session_id?: string | null
  event_id?: string | null
  title: string
  prompt: string
  hint: string
  rubric?: string[]
  source?: 'local' | 'deepseek' | 'taskmaster' | 'realpersonachat'
  created_at: string
}

export interface PracticeLibraryItem {
  id: string
  category: string
  category_code: string
  category_label: string
  scene_code: string
  scene_label: string
  title: string
  prompt: string
  opening_line: string
  hidden_context: string
  relationship?: string | null
  register?: string | null
  hint: string
  rubric: string[]
  source: {
    dataset: string
    version?: string
    split?: string
    instruction_id?: string
    conversation_id: string
    utterance_index: number
    license: string
    review_status?: string
  }
}

export interface PracticeLibraryScene {
  code: string
  label: string
  item_count: number
}

export interface PracticeLibraryCategory {
  code: string
  label: string
  item_count: number
  scenes: PracticeLibraryScene[]
}

export interface PracticeAttribution {
  dataset: string
  version?: string
  label: string
  license: string
  url: string
}

export interface PracticeLibraryResponse {
  items: PracticeLibraryItem[]
  total: number
  page: number
  page_size: number
  categories: PracticeLibraryCategory[]
  attributions: PracticeAttribution[]
  attribution: PracticeAttribution
}

export function listPracticeLibrary(
  target: Language = 'en',
  native: Language = 'zh',
  filters: {category?: string; scene?: string; page?: number; page_size?: number} = {},
) {
  const query = new URLSearchParams({
    target_language: target,
    native_language: native,
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 12),
  })
  if (filters.category) query.set('category', filters.category)
  if (filters.scene) query.set('scene', filters.scene)
  return request<PracticeLibraryResponse>(`/practice-library?${query.toString()}`)
}

export function createRemotePractice(payload: { target_language?: Language; session_id?: string; event_id?: string; title: string; prompt: string; hint: string }) {
  return request<RemotePractice>('/practices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function transcribePracticeAudio(blob: Blob, cloudAudioConsent = false, language: Language = 'en') {
  const form = new FormData()
  form.append('audio', blob, `practice.${blob.type.includes('ogg') ? 'ogg' : blob.type.includes('mp4') ? 'mp4' : 'webm'}`)
  return request<{ text: string; language: string; model: string; provider: 'qwen' }>(`/practice/transcribe?cloud_audio_consent=${cloudAudioConsent}&language=${language}`, { method: 'POST', body: form })
}

export async function synthesizePracticeSpeech(text: string, language: Language = 'en') {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const csrf = cookie('bw_csrf')
  if (csrf) headers.set('X-CSRF-Token', csrf)
  const response = await fetch(`${API_BASE}/practice/tts`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ text, language }),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { error?: { message?: string } } | null
    throw new Error(detail?.error?.message || `语音生成失败（${response.status}）`)
  }
  return {
    audio: await response.blob(),
    model: response.headers.get('X-Beyond-Words-TTS-Model') || 'qwen3-tts-flash',
    voice: response.headers.get('X-Beyond-Words-TTS-Voice') || 'Cherry',
    cached: response.headers.get('X-Beyond-Words-TTS-Cache') === 'hit',
  }
}

export function createRemoteAttempt(practiceId: string, response: string) {
  return request<{ id: string; event_id: string; response: string; feedback: string[]; feedback_source?: 'local-rules' | 'deepseek'; created_at: string }>(`/practice/${practiceId}/attempts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ response }),
  })
}

export function listRemoteAttempts() {
  return request<Array<{ id: string; event_id: string; response: string; feedback: string[]; created_at: string }>>('/practice-attempts')
}

export function getRemoteSettings() {
  return request<UserPreferences>('/me/preferences')
}

export function updateRemoteSettings(goal: string) {
  return request<UserPreferences>('/me/preferences', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal }),
  })
}

export function getRemoteExport() {
  return request<Record<string, unknown>>('/me/export')
}

export function deleteAllRemoteData() {
  return request<void>('/me/data', { method: 'DELETE' })
}

export function deleteAccount(password: string) {
  return request<void>('/me/account', {
    method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirmation: 'DELETE', password }),
  })
}

export function listRemoteSessions() {
  return request<RemoteSession[]>('/sessions')
}

export function remoteAudioUrl(sessionId: string) {
  return `${API_BASE}/sessions/${sessionId}/audio`
}

export interface UserAccount {
  id: string
  email: string
  display_name: string
  avatar?: string | null
  role: 'user' | 'admin'
  status: 'active' | 'disabled'
  ai_enabled: boolean
  goal: string
  created_at: string
  last_login_at?: string | null
}

export interface UserPreferences {
  date_format: DateFormat
  native_language: Language
  target_language: Language
  goal: string
  ai_enabled: boolean
  ai_consent_version?: string | null
  ai_consent_at?: string | null
  pii_aliases: string[]
}

export function getAuthCapabilities() {
  return request<{ password_login: boolean; oidc_enabled: boolean; oidc_display_name: string }>('/auth/capabilities')
}

export function getCurrentUser() {
  return request<{ user: UserAccount; csrf_token: string }>('/auth/me')
}

export function registerAccount(email: string, password: string, displayName: string) {
  return request<{ user: UserAccount; csrf_token: string }>('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, display_name: displayName }),
  })
}

export function loginAccount(email: string, password: string) {
  return request<{ user: UserAccount; csrf_token: string }>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
}

export function logoutAccount() {
  return request<void>('/auth/logout', { method: 'POST' })
}

export function requestPasswordReset(email: string) {
  return request<{ message: string; development_reset_token?: string }>('/auth/forgot-password', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }),
  })
}

export function resetAccountPassword(token: string, newPassword: string) {
  return request<void>('/auth/reset-password', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, new_password: newPassword }),
  })
}

export function updatePreferences(patch: Partial<Pick<UserPreferences, 'date_format' | 'goal' | 'ai_enabled' | 'pii_aliases' | 'native_language' | 'target_language'>> & { consent_version?: string }) {
  return request<UserPreferences>('/me/preferences', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
}

export function deleteAIContent() {
  return request<void>('/me/ai-content', { method: 'DELETE' })
}

export function previewAIText(sessionId: string) {
  return request<{ audio_shared: false; turns: RemoteTurn[] }>(`/sessions/${sessionId}/ai-preview`)
}

export function generateAIReview(sessionId: string, force = false) {
  return request<{ session_id: string; job_id: string; status: string; provider: 'deepseek'; model: string }>(`/sessions/${sessionId}/ai-review?force=${force}`, { method: 'POST' })
}

export function generatePracticeSet(sessionId: string, eventId?: string) {
  const query = eventId ? `?event_id=${encodeURIComponent(eventId)}` : ''
  return request<{ job_id: string; status: string }>(`/sessions/${sessionId}/practice-sets${query}`, { method: 'POST' })
}

export function getAnalysisJob(jobId: string) {
  return request<{ id: string; status: 'queued' | 'running' | 'complete' | 'failed'; progress: number; error?: string | null; result?: Record<string, unknown> | null }>(`/analysis-jobs/${jobId}`)
}

export function listRemotePractices() {
  return request<RemotePractice[]>('/practices')
}

export function oidcLoginUrl() {
  return `${API_BASE}/auth/oidc/login`
}

export type AdminRange = '24h' | '7d' | '30d'

export interface AdminPageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface AdminProviderUsage {
  provider: 'qwen' | 'deepseek'
  model: string
  configured: boolean
  calls: number
  successful_calls: number
  failed_calls: number
  success_rate: number
  average_latency_ms: number
  audio_minutes: number
  input_tokens: number
  output_tokens: number
  last_success_at?: string | null
  last_error_code?: string | null
  task_types: Record<string, number>
}

export interface AdminSeriesPoint {
  bucket_start: string
  sessions: number
  jobs_complete: number
  jobs_failed: number
  qwen_calls: number
  deepseek_calls: number
  qwen_audio_minutes: number
  deepseek_input_tokens: number
  deepseek_output_tokens: number
}

export interface AdminOverview {
  range: AdminRange
  generated_at: string
  totals: {
    users: number
    active_users: number
    active_sessions: number
    sessions: number
    jobs: number
    pending_jobs: number
  }
  job_health: { complete: number; failed: number; success_rate: number }
  providers: AdminProviderUsage[]
  series: AdminSeriesPoint[]
}

export interface AdminJob {
  id: string
  owner: { id: string; display_name: string; email: string }
  session_id: string
  kind: 'speech' | 'ai_review' | 'practice_set'
  status: 'queued' | 'running' | 'complete' | 'failed'
  progress: number
  provider: 'qwen' | 'deepseek'
  model?: string | null
  attempt_count: number
  retryable: boolean
  retry_of_job_id?: string | null
  error_code?: string | null
  error_summary?: string | null
  duration_ms?: number | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
}

export interface AdminAuditEntry {
  id: string
  actor?: { id: string; display_name: string; email: string } | null
  action: string
  target_type?: string | null
  target_id?: string | null
  metadata: Record<string, string>
  created_at: string
}

export interface AdminSystemHealth {
  status: 'ok' | 'degraded'
  checked_at: string
  checks: Record<string, { status: 'ok' | 'error' | 'unknown' | 'not_applicable'; detail: string }>
  queues: { default: number; speech: number }
  grafana_url?: string | null
}

export interface AdminModelUsage {
  range: AdminRange
  generated_at: string
  providers: AdminProviderUsage[]
  series: AdminSeriesPoint[]
  billing_notice: string
}

function adminQuery(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  return search.toString()
}

export function getAdminOverview(range: AdminRange) {
  return request<AdminOverview>(`/admin/overview?${adminQuery({ range })}`)
}

export function listAdminUsers(params: { query?: string; role?: string; status?: string; page?: number; page_size?: number } = {}) {
  return request<AdminPageResult<UserAccount>>(`/admin/users?${adminQuery({ page: params.page ?? 1, page_size: params.page_size ?? 25, query: params.query, role: params.role, status: params.status })}`)
}

export function setAdminUserStatus(userId: string, status: 'active' | 'disabled') {
  return request<UserAccount>(`/admin/users/${userId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
}

export function revokeAdminUserSessions(userId: string) {
  return request<void>(`/admin/users/${userId}/revoke-sessions`, { method: 'POST' })
}

export function listAdminJobs(params: { kind?: string; status?: string; provider?: string; date_from?: string; date_to?: string; page?: number; page_size?: number } = {}) {
  return request<AdminPageResult<AdminJob>>(`/admin/jobs?${adminQuery({ page: params.page ?? 1, page_size: params.page_size ?? 25, kind: params.kind, status: params.status, provider: params.provider, date_from: params.date_from, date_to: params.date_to })}`)
}

export function retryAdminJob(jobId: string) {
  return request<{ source_job_id: string; job_id: string; status: 'queued' }>(`/admin/jobs/${jobId}/retry`, { method: 'POST' })
}

export function getAdminModelUsage(range: AdminRange) {
  return request<AdminModelUsage>(`/admin/model-usage?${adminQuery({ range })}`)
}

export function listAdminAuditLogs(params: { action?: string; actor_id?: string; page?: number; page_size?: number } = {}) {
  return request<AdminPageResult<AdminAuditEntry>>(`/admin/audit-logs?${adminQuery({ page: params.page ?? 1, page_size: params.page_size ?? 25, action: params.action, actor_id: params.actor_id })}`)
}

export function getAdminSystemHealth() {
  return request<AdminSystemHealth>('/admin/system-health')
}

function mapTurns(turns: RemoteTurn[], mode: RemoteAnalysis['mode'], userSpeakerId?: string | null): Turn[] {
  return turns.map((turn) => ({
    id: turn.id,
    speaker: mode === 'mock'
      ? turn.speaker_id === 'SPEAKER_01' ? 'you' : turn.speaker_id === 'SPEAKER_00' ? 'partner' : 'unknown'
      : userSpeakerId
        ? turn.speaker_id === userSpeakerId ? 'you' : turn.speaker_id === 'SPEAKER_UNKNOWN' ? 'unknown' : 'partner'
        : 'unknown',
    speakerId: turn.speaker_id,
    startMs: turn.start_ms,
    endMs: turn.end_ms,
    text: turn.text,
  }))
}

function mapEvents(events: RemoteEvent[]): InteractionEvent[] {
  return events.map((event) => ({
    id: event.id,
    type: event.type,
    startMs: event.start_ms,
    endMs: event.end_ms,
    turnIds: event.turn_ids,
    markerIds: event.marker_ids,
    observation: event.insight.observation,
    context: event.insight.context,
    suggestion: event.insight.suggestion,
    example: event.insight.example || 'I like the idea because it gives us a relaxed way to practise. What do you think?',
    uncertainty: '这一解释由自动分析生成，请结合原始录音和完整语境核对。',
  }))
}

export function analysisToPatch(analysis: RemoteAnalysis, userSpeakerId?: string | null): Pick<Session, 'turns' | 'events' | 'isMockAnalysis' | 'analysisNotice' | 'analysisSource' | 'speakerIds' | 'userSpeakerId' | 'diarizationStatus' | 'diarizationReason' | 'summary' | 'metrics' | 'aiReview' | 'speechExecution'> {
  userSpeakerId = analysis.user_speaker_id ?? userSpeakerId
  return {
    turns: mapTurns(analysis.turns, analysis.mode, userSpeakerId),
    events: mapEvents(analysis.events),
    isMockAnalysis: analysis.mode === 'mock',
    analysisNotice: analysis.notice,
    analysisSource: analysis.semantic_provider,
    aiReview: analysis.ai_review,
    speakerIds: analysis.speakers?.map((speaker) => speaker.id).filter((id) => id !== 'SPEAKER_UNKNOWN') || [],
    userSpeakerId: userSpeakerId || undefined,
    diarizationStatus: analysis.diarization?.status,
    diarizationReason: analysis.diarization?.reason,
    summary: analysis.summary,
    metrics: analysis.metrics ? {
      userSpeakingMs: analysis.metrics.user_speaking_ms,
      speakingShare: analysis.metrics.speaking_share,
      userTurnCount: analysis.metrics.user_turn_count,
      totalTurnCount: analysis.metrics.total_turn_count,
    } : undefined,
    speechExecution: analysis.execution ? {
      provider: analysis.execution.provider,
      model: analysis.execution.model,
      providerTaskId: analysis.execution.provider_task_id,
      latencyMs: analysis.execution.latency_ms,
      audioDurationMs: analysis.execution.audio_duration_ms,
      retryCount: analysis.execution.retry_count ?? 0,
      resumedExistingTask: analysis.execution.resumed_existing_task ?? false,
    } : undefined,
  }
}

export function remoteToSession(remote: RemoteSession): Session {
  return {
    id: `remote-${remote.id}`,
    remoteId: remote.id,
    title: remote.title,
    isFavorite: remote.is_favorite ?? false,
    scenario: remote.scenario,
    targetLanguage: remote.target_language || 'en',
    createdAt: remote.created_at,
    durationMs: remote.duration_ms,
    processingStatus: remote.processing_status,
    syncStatus: 'synced',
    isMockAnalysis: remote.analysis?.mode === 'mock',
    analysisNotice: remote.analysis?.notice,
    analysisSource: remote.analysis?.semantic_provider,
    aiReview: remote.analysis?.ai_review,
    speakerIds: remote.analysis?.speakers?.map((speaker) => speaker.id).filter((id) => id !== 'SPEAKER_UNKNOWN') || [],
    userSpeakerId: remote.user_speaker_id || undefined,
    diarizationStatus: remote.analysis?.diarization?.status,
    diarizationReason: remote.analysis?.diarization?.reason,
    summary: remote.analysis?.summary,
    metrics: remote.analysis?.metrics ? {
      userSpeakingMs: remote.analysis.metrics.user_speaking_ms,
      speakingShare: remote.analysis.metrics.speaking_share,
      userTurnCount: remote.analysis.metrics.user_turn_count,
      totalTurnCount: remote.analysis.metrics.total_turn_count,
    } : undefined,
    speechExecution: remote.analysis?.execution ? {
      provider: remote.analysis.execution.provider,
      model: remote.analysis.execution.model,
      providerTaskId: remote.analysis.execution.provider_task_id,
      latencyMs: remote.analysis.execution.latency_ms,
      audioDurationMs: remote.analysis.execution.audio_duration_ms,
      retryCount: remote.analysis.execution.retry_count ?? 0,
      resumedExistingTask: remote.analysis.execution.resumed_existing_task ?? false,
    } : undefined,
    markers: remote.markers.map((marker) => ({ id: marker.id, timestampMs: marker.timestamp_ms })),
    turns: remote.analysis ? mapTurns(remote.analysis.turns, remote.analysis.mode, remote.user_speaker_id) : [],
    events: remote.analysis ? mapEvents(remote.analysis.events) : [],
  }
}

export function updateProfile(display_name: string, avatar: string | null) {
  return request<UserAccount>('/me/profile', { method: 'PUT', body: JSON.stringify({ display_name, avatar }) })
}

export const getVoiceprint = () => request<{ enrolled: boolean; available: boolean }>('/me/voiceprint')
export const deleteVoiceprint = () => request<void>('/me/voiceprint', { method: 'DELETE' })
export const enrollVoiceprint = (id: string) => request<{ enrolled: boolean }>(`/sessions/${id}/voiceprint?consent=true`, { method: 'POST' })
export const matchVoiceprint = (id: string) => request<{ status: string; speaker_id?: string }>(`/sessions/${id}/voiceprint-match`, { method: 'POST' })
export interface TutorHistory { messages: Array<{role: 'user' | 'assistant'; content: string}>; version: number }
export const getTutorHistory = (id: string) => request<TutorHistory>(`/sessions/${id}/tutor`)
export function sendTutorMessage(id: string, message: string, version: number) {
  return request<TutorHistory>(`/sessions/${id}/tutor`, {method: 'POST', body: JSON.stringify({message, mode: 'chat', version})})
}
export async function downloadReviewWord(id: string) {
  const result = await fetch(`${API_BASE}/sessions/${id}/export.docx`, {credentials: 'include'})
  if (!result.ok) throw new Error('导出失败，请重试')
  return result.blob()
}

export interface PracticeConversationHistory {
  messages: Array<{role: 'user' | 'assistant'; content: string}>
  version: number
  saved: boolean
}

export function getPracticeConversation(sceneId: string, targetLanguage: Language) {
  return request<PracticeConversationHistory>(`/practice/conversations/${encodeURIComponent(sceneId)}?target_language=${targetLanguage}`)
}

export function continueVoiceConversation(
  sceneId: string,
  title: string,
  prompt: string,
  targetLanguage: Language,
  messages: Array<{role: 'user' | 'assistant'; content: string}>,
  version: number,
) {
  return request<PracticeConversationHistory & {
    reply: string
    attempt?: {id: string; event_id: string; response: string; feedback: string[]; created_at: string} | null
  }>('/practice/conversation', {method: 'POST', body: JSON.stringify({scene_id: sceneId, title, prompt, target_language: targetLanguage, messages: messages.slice(-39), version, consent: true})})
}

export interface WeeklyEntry { id: string; week: string; kind: 'word' | 'sentence'; text: string; note: string }
export const getWeeklyEntries = (week: string) => request<WeeklyEntry[]>(`/me/weekly-entries?week=${week}`)
export const addWeeklyEntry = (entry: Omit<WeeklyEntry, 'id'>) => request<WeeklyEntry>('/me/weekly-entries', {method: 'POST', body: JSON.stringify(entry)})
export const deleteWeeklyEntry = (id: string) => request<void>(`/me/weekly-entries/${id}`, {method: 'DELETE'})

export interface WeeklyJournalData {
  week: string
  words: Array<{text: string; note: string; source_id: string}>
  sentences: Array<{text: string; note: string; source_id: string}>
  sources: Array<{id: string; title: string}>
  skipped: number
  generated_at: string
}
export const getWeeklyJournal = (week: string) => request<WeeklyJournalData | null>(`/me/weekly-journal?week=${week}`)
export const generateWeeklyJournal = (week: string, session_ids?: string[]) => request<WeeklyJournalData>('/me/weekly-journal', {method: 'POST', body: JSON.stringify({week, timezone_offset: new Date(`${week}T00:00:00`).getTimezoneOffset(), session_ids})})
