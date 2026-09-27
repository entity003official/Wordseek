import { t } from '../lib/i18n'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { guideState, initialGuide } from '../lib/onboarding'
import { useAppStore } from '../store/useAppStore'
import type { Session } from '../types'
import { GuideSpotlight } from './GuideSpotlight'

export function useLearningGuide() {
  const ownerId = useAppStore((state) => state.ownerId)
  const guides = useAppStore((state) => state.guides)
  const sessions = useAppStore((state) => state.sessions)
  const attempts = useAppStore((state) => state.attempts)
  const guide = (ownerId && guides[ownerId]) || initialGuide
  const experienced = ownerId && !guides[ownerId] && attempts.length > 0 && sessions.some((s) => !s.isMockAnalysis && s.processingStatus === 'ready')
  return { guide, ...guideState(guide, sessions), visible: Boolean(ownerId && !experienced && guide.status !== 'dismissed') }
}

interface Props {
  surface: 'home' | 'history' | 'review' | 'practice' | 'recording'
  session?: Session
  transcriptOpen?: boolean
  hasResponse?: boolean
  cloudConsent?: boolean
  recordingPhase?: 'prepare' | 'recording' | 'saved' | 'unsaved' | 'error' | 'requesting' | 'analyzing' | 'syncing' | 'sync-failed' | 'unavailable' | 'analysis-failed'
}

export function LearningGuide({ surface, session: currentSession, transcriptOpen, hasResponse, cloudConsent, recordingPhase }: Props) {
  const { guide, session, step, visible } = useLearningGuide()
  const updateGuide = useAppStore((state) => state.updateGuide)
  const navigate = useNavigate()
  const location = useLocation()
  const [selection, setSelection] = useState<{ key: string; page: number } | null>(null)
  const routePage: unknown = location.state?.guidePage
  const manualPage = selection?.key === location.key ? selection.page : typeof routePage === 'number' && Number.isInteger(routePage) && routePage >= 0 && routePage < 5 ? routePage : null
  if (!visible) return null
  const dismiss = () => updateGuide({ status: 'dismissed' })
  if (guide.status === 'completed') {
    if (surface !== 'home' && surface !== 'practice') return null
    return <GuideSpotlight target={surface === 'practice' ? '.feedback-card|.prompt-card' : '.home-record-entry'} step={2} title={t("引导完成")} description={t("随时回来继续练习。")} done dismiss={dismiss} />
  }
  const pages = [
    { step: 0, target: '.home-record-entry', title: '录音', description: '点「开始录音」，记录一段对话。' },
    { step: 0, target: '.recording-setup|.recording-actions', title: '保存', description: '确认参与者同意后录音，说完点「结束」。' },
    { step: 1, target: '[data-guide="analyze-recording"]|.review-resume-analysis', title: '转写', description: '授权将录音发送给千问，生成文字。' },
    { step: 1, target: '#review-panel-transcript|#review-tab-transcript', title: '核对', description: '点时间戳回听，点铅笔改字。' },
    { step: 2, target: '#practice-response|.home-practice-link|.review-practice-cta', title: '练习', description: '用学习语言回答，提交后查看反馈。' },
  ]
  const contextualPage = surface === 'practice' ? 4 : surface === 'review' ? 3 : surface === 'recording' ? ['prepare', 'recording', 'requesting'].includes(recordingPhase ?? '') ? 1 : 2 : step === 0 ? 0 : step === 1 ? 3 : 4
  const page = manualPage ?? contextualPage
  let content = { ...pages[page] }
  if (manualPage === null) {
    const recording = currentSession ?? session
    if (surface === 'home' || surface === 'history') {
      if (recording && step === 1) content = { ...content, target: `a[href=${JSON.stringify(`/review/${recording.id}`)}]|.bottom-nav a[href="/history"]`, description: '打开一条记录，查看转写。' }
    }
    if (surface === 'practice' && hasResponse) content = { ...content, target: '.send-button', description: '点「提交回答」查看反馈。' }
    if (surface === 'review' && recording) {
      if (['transcribing', 'analyzing'].includes(recording.processingStatus)) content = { ...content, target: '.review-player', title: '正在转写', description: '可以先离开，稍后从历史查看。' }
      else if (recording.processingStatus === 'failed') content = { ...content, target: '.review-resume-analysis|.speaker-error', title: '转写失败', description: '查看错误提示，处理后重试。' }
      else if (!recording.turns.length) content = { ...content, target: '.review-resume-analysis|.review-sync-action', title: '转写', description: '上传录音后，点「开始转写」。' }
      else if (!transcriptOpen) content = { ...content, target: '#review-tab-transcript', description: '点「转写」查看对话文字。' }
    }
    if (surface === 'recording') {
      if (recordingPhase === 'prepare') content = { ...content, target: '.recording-setup .primary-button', title: '准备录音', description: '点「开始录音」，允许麦克风权限。' }
      else if (recordingPhase === 'recording') content = { ...content, target: '.recording-actions .is-danger', description: '说完点「结束」，自动保存录音。' }
      else if (recordingPhase === 'saved') content = { ...content, target: cloudConsent ? '[data-guide="analyze-recording"]' : '.analysis-consent', description: cloudConsent ? '点「开始分析」生成转写。' : '勾选授权，将录音发送给千问转写。' }
      else if (recordingPhase === 'syncing' || recordingPhase === 'analyzing') content = { ...content, title: '正在处理', description: '稍等片刻，无需重复点击。' }
      else if (recordingPhase === 'sync-failed') content = { ...content, target: '.sync-retry', title: '上传失败', description: '点「重试上传」，录音仍在本机。' }
      else if (recordingPhase === 'unsaved') content = { ...content, target: '.recording-result .primary-button', title: '保存录音', description: '点「重试保存」，再离开页面。' }
      else if (recordingPhase === 'requesting') content = { ...content, target: '.recording-status', title: '麦克风授权', description: '在浏览器权限提示中选择「允许」。' }
      else content = { ...content, target: '.error-banner|.recording-status', title: '检查提示', description: '录音已保留，处理提示后再继续。' }
    }
  }
  const recording = currentSession ?? session
  if (manualPage !== null) {
    if (surface === 'history' && !recording) content = { ...content, target: '.empty-state|.history-list|.page-header', description: page === 2 ? '录音保存后，可以在记录中开始转写。' : '打开历史记录，即可回听和修改文字。' }
    if (surface === 'review' && page === 2) content.target = '.review-resume-analysis|.review-player'
    if (surface === 'recording' && page === 1) content.target = recordingPhase === 'prepare' ? '.recording-setup .primary-button' : '.recording-actions|.recording-result'
  }
  function turnPage(nextPage: number) {
    const destination = nextPage === 0 ? '/' : nextPage === 1 ? '/recording' : nextPage === 4 ? '/practice' : recording ? `/review/${recording.id}` : '/history'
    // Keep unsaved audio mounted; paging the guide never stops the microphone.
    const keepRecording = surface === 'recording' && ['recording', 'requesting', 'unsaved', 'error', 'syncing', 'analyzing'].includes(recordingPhase ?? '')
    setSelection({ key: location.key, page: nextPage })
    if (destination !== location.pathname && !keepRecording) navigate(destination, { state: { guidePage: nextPage } })
  }
  return <GuideSpotlight {...content} dismiss={dismiss} navigation={{ page, total: pages.length, previous: () => turnPage(Math.max(0, page - 1)), next: () => { if (page === pages.length - 1) dismiss(); else turnPage(page + 1) } }} />
}
