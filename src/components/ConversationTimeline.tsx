import { t } from '../lib/i18n'
import { Flag } from 'lucide-react'
import { formatDuration } from '../lib/format'
import type { Marker, Turn } from '../types'

export function ConversationTimeline({ turns, markers, durationMs, onSelect }: { turns: Turn[]; markers: Marker[]; durationMs: number; onSelect?: (turn: Turn) => void }) {
  const duration = Math.max(durationMs, ...turns.map((turn) => turn.endMs), 1)
  return (
    <div className="timeline-scroll">
      <div className="timeline" style={{ minWidth: duration > 90000 ? '620px' : '100%' }}>
        <div className="timeline-axis"><span>0:00</span><span>{formatDuration(duration / 2)}</span><span>{formatDuration(duration)}</span></div>
        <div className="timeline-row"><span className="speaker-label speaker-label--you">{t("你")}</span><div className="timeline-track">
          {turns.filter((turn) => turn.speaker === 'you').map((turn) => <button key={turn.id} className="turn-block turn-block--you" style={{ left: `${turn.startMs / duration * 100}%`, width: `${Math.max(3, (turn.endMs - turn.startMs) / duration * 100)}%` }} onClick={() => onSelect?.(turn)} aria-label={`播放你在 ${formatDuration(turn.startMs)} 的话轮`} />)}
        </div></div>
        <div className="timeline-row"><span className="speaker-label speaker-label--partner">{t("伙伴")}</span><div className="timeline-track">
          {turns.filter((turn) => turn.speaker === 'partner').map((turn) => <button key={turn.id} className="turn-block turn-block--partner" style={{ left: `${turn.startMs / duration * 100}%`, width: `${Math.max(3, (turn.endMs - turn.startMs) / duration * 100)}%` }} onClick={() => onSelect?.(turn)} aria-label={`播放伙伴在 ${formatDuration(turn.startMs)} 的话轮`} />)}
          {markers.map((marker) => <span className="timeline-marker" key={marker.id} style={{ left: `${marker.timestampMs / duration * 100}%` }} title={`重点标记：${formatDuration(marker.timestampMs)}`}><Flag size={12} /></span>)}
        </div></div>
        {turns.some((turn) => turn.speaker === 'unknown') && <div className="timeline-row"><span className="speaker-label speaker-label--unknown">{t("待确认")}</span><div className="timeline-track">
          {turns.filter((turn) => turn.speaker === 'unknown').map((turn) => <button key={turn.id} className="turn-block turn-block--unknown" style={{ left: `${turn.startMs / duration * 100}%`, width: `${Math.max(3, (turn.endMs - turn.startMs) / duration * 100)}%` }} onClick={() => onSelect?.(turn)} aria-label={`播放 ${formatDuration(turn.startMs)} 的未确认话轮`} />)}
        </div></div>}
      </div>
    </div>
  )
}
