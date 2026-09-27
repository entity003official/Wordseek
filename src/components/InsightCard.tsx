import { t } from '../lib/i18n'
import { ArrowUpRight, MessagesSquare, Play } from 'lucide-react'
import { Link } from 'react-router-dom'
import { formatDuration } from '../lib/format'
import type { InteractionEvent } from '../types'

export function InsightCard({ event, sessionId, isMock, source }: { event: InteractionEvent; sessionId: string; isMock: boolean; source?: 'local-rules' | 'deepseek' }) {
  const labels: Record<InteractionEvent['type'], { eyebrow: string; title: string }> = {
    TOPIC_DEVELOPMENT: { eyebrow: '话题延续', title: '一个继续展开话题的机会' },
    FOLLOW_UP_QUESTION: { eyebrow: '主动追问', title: '你把交流机会交还给了对方' },
    TURN_BALANCE: { eyebrow: '话轮节奏', title: '一个邀请对方加入的节点' },
    CLARIFICATION: { eyebrow: '请求澄清', title: '你主动维护了共同理解' },
  }
  const label = labels[event.type]
  return (
    <Link className="insight-card" to={`/moment/${sessionId}/${event.id}`}>
      <div className="insight-card__top"><span className="insight-icon"><MessagesSquare size={19} /></span><span className={`analysis-chip analysis-chip--${isMock ? 'mock' : 'rule'} analysis-chip--light`}>{isMock ? t("演示") : source === 'deepseek' ? t("AI 洞察") : t("互动提示")}</span><ArrowUpRight size={20} /></div>
      <span className="insight-type">{t(label.eyebrow)}</span>
      <h3>{t(label.title)}</h3>
      <p>{event.observation}</p>
      <div className="insight-evidence"><Play size={14} fill="currentColor" />{t("原声证据 ·")}{formatDuration(event.startMs)}–{formatDuration(event.endMs)}</div>
    </Link>
  )
}
