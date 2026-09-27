import { t } from '../lib/i18n'
import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  target: string
  step: number
  title: string
  description: string
  done?: boolean
  navigation?: { page: number; total: number; previous: () => void; next: () => void }
  dismiss: () => void
}

export function GuideSpotlight({ target, step, title, description, dismiss, done, navigation }: Props) {
  const id = useId().replace(/:/g, '')
  const tip = useRef<HTMLElement>(null)
  const [position, setPosition] = useState<{ x: number; y: number; w: number; h: number; left: number; top: number; width: number; maxHeight: number } | null>(null)

  useEffect(() => {
    let frame = 0
    let current: HTMLElement | undefined
    let previousDescription: string | null = null
    const restore = () => {
      if (!current) return
      if (previousDescription === null) current.removeAttribute('aria-describedby')
      else current.setAttribute('aria-describedby', previousDescription)
    }
    const measure = () => {
      const element = target.split('|').map((selector) => document.querySelector<HTMLElement>(selector)).find((node) => node && node.getBoundingClientRect().height > 0)
      if (!element) { setPosition(null); return }
      if (current !== element) {
        restore()
        current = element
        previousDescription = element.getAttribute('aria-describedby')
        element.setAttribute('aria-describedby', `${previousDescription ?? ''} ${id}-description`.trim())
        const r = element.getBoundingClientRect()
        if (r.top < 12 || r.bottom > window.innerHeight - 100) element.scrollIntoView({ block: 'center', behavior: 'auto' })
      }
      const rect = element.getBoundingClientRect()
      const vw = document.documentElement.clientWidth
      const vh = window.innerHeight
      const width = Math.min(304, vw - 24)
      const height = tip.current ? tip.current.scrollHeight + 2 : 240
      const x = Math.max(6, rect.left - 5)
      const y = Math.max(6, rect.top - 5)
      const w = Math.min(rect.width + 10, vw - x - 6)
      const h = Math.min(rect.height + 10, 180)
      const below = y + h + 12
      const roomBelow = Math.max(0, vh - below - 12)
      const roomAbove = Math.max(0, y - 24)
      const placeBelow = roomBelow >= height || roomBelow >= roomAbove
      const maxHeight = Math.max(0, placeBelow ? roomBelow : roomAbove)
      const top = placeBelow ? below : Math.max(12, y - Math.min(height, maxHeight) - 12)
      setPosition({ x, y, w, h, width, maxHeight, left: Math.max(12, Math.min(rect.left, vw - width - 12)), top })
    }
    const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(measure) }
    schedule()
    window.addEventListener('resize', schedule)
    window.addEventListener('scroll', schedule, true)
    const observer = new MutationObserver(schedule)
    observer.observe(document.querySelector('.app-frame') ?? document.body, { childList: true, subtree: true })
    const resize = new ResizeObserver(schedule)
    if (tip.current) resize.observe(tip.current)
    return () => {
      restore()
      cancelAnimationFrame(frame)
      observer.disconnect()
      resize.disconnect()
      window.removeEventListener('resize', schedule)
      window.removeEventListener('scroll', schedule, true)
    }
  }, [target, id, title, description])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') dismiss() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dismiss])

  return createPortal(<div className="guide-overlay">
    {position && <><svg className="guide-shade" width="100%" height="100%" aria-hidden="true"><defs><mask id={`${id}-mask`}><rect width="100%" height="100%" fill="white" /><rect x={position.x} y={position.y} width={position.w} height={position.h} rx="14" fill="black" /></mask></defs><rect width="100%" height="100%" fill="#111820" opacity=".48" mask={`url(#${id}-mask)`} /></svg><div className="guide-outline" style={{ left: position.x, top: position.y, width: position.w, height: position.h }} /></>}
    <aside ref={tip} className="guide-tip" aria-label={t("操作引导")} style={position ? { left: position.left, top: position.top, width: position.width, maxHeight: position.maxHeight } : { left: 12, bottom: 88, width: 'min(304px, calc(100vw - 24px))' }}>
      <div className="guide-tip-head"><span>{done ? t("引导完成") : navigation ? `${navigation.page + 1}/${navigation.total}` : `${step + 1}/3 · ${['录一段', '看复盘', '练一次'][step]}`}</span><button onClick={dismiss} aria-label={done ? t("结束引导") : t("跳过引导")}>{done ? t("完成") : t("跳过")}</button></div>
      <div aria-live="polite"><h2>{t(title)}</h2><p id={`${id}-description`}>{t(description)}</p></div>
      {navigation && <div className="guide-pagination"><button onClick={navigation.previous} disabled={navigation.page === 0}>{t("上一步")}</button><button onClick={navigation.next}>{navigation.page === navigation.total - 1 ? t("完成引导") : t("下一步")}</button></div>}
    </aside>
  </div>, document.body)
}
