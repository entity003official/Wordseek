import { t } from '../lib/i18n'
import type { ProcessingStatus } from '../types'

const labels: Record<ProcessingStatus, string> = {
  saved: '已保存',
  transcribing: '正在分析',
  analyzing: '正在分析',
  ready: '分析完成',
  failed: '需要重试',
}

export function StatusBadge({ status }: { status: ProcessingStatus }) {
  return <span className={`status-badge status-badge--${status}`}><i />{t(labels[status])}</span>
}
