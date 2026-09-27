import { useEffect, useRef } from 'react'
import { flushSync } from 'react-dom'

type Transition = { ready: Promise<void>; finished: Promise<void>; skipTransition: () => void }

/** Uniform page-depth transition, with no decorative overlay or raster particles. */
export function useSceneTransition() {
  const pageRef = useRef<HTMLElement>(null)
  const active = useRef<Transition | null>(null)
  const animation = useRef<Animation | null>(null)
  const sequence = useRef(0)

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
    const stop = () => { active.current?.skipTransition(); animation.current?.finish() }
    const history = () => { sequence.current += 1; active.current?.skipTransition(); animation.current?.cancel() }
    const hidden = () => { if (document.hidden) stop() }
    reduced.addEventListener('change', stop)
    window.addEventListener('popstate', history)
    document.addEventListener('visibilitychange', hidden)
    return () => {
      sequence.current += 1
      active.current?.skipTransition()
      animation.current?.cancel()
      reduced.removeEventListener('change', stop)
      window.removeEventListener('popstate', history)
      document.removeEventListener('visibilitychange', hidden)
    }
  }, [])

  function transitionTo(change: () => void) {
    const token = ++sequence.current
    active.current?.skipTransition()
    animation.current?.cancel()
    const commit = () => { if (token === sequence.current) flushSync(change) }
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (reduced.matches || document.hidden) { commit(); return }
    const doc = document as Document & { startViewTransition?: (update: () => void) => Transition }
    if (doc.startViewTransition) {
      const next = doc.startViewTransition(commit)
      active.current = next
      void next.ready.catch(() => undefined)
      void next.finished.catch(() => undefined).then(() => { if (active.current === next) active.current = null })
      return
    }
    // Older browsers use the same quiet depth/fade rhythm without a black curtain.
    const page = pageRef.current
    if (!page?.animate) { commit(); return }
    const leave = page.animate([{ opacity: 1, transform: 'scale(1)' }, { opacity: .25, transform: 'scale(.985)' }], { duration: 120, easing: 'ease-out', fill: 'forwards' })
    animation.current = leave
    void leave.finished.then(() => {
      if (token !== sequence.current) return
      leave.cancel()
      commit()
      if (reduced.matches) return
      animation.current = page.animate([{ opacity: .25, transform: 'translateY(8px) scale(.995)' }, { opacity: 1, transform: 'translateY(0) scale(1)' }], { duration: 280, easing: 'cubic-bezier(.22,1,.36,1)' })
    }).catch(() => undefined)
  }
  return { pageRef, transitionTo }
}
