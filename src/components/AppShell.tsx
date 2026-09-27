import { t } from '../lib/i18n'
import { useLayoutEffect, type MouseEvent, type PropsWithChildren } from 'react'
import { useSceneTransition } from '../hooks/useSceneTransition'
import { House, History, MessageCircle, UserRound } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'


const items = [
  { to: '/', label: '首页', id: 'home', icon: House },
  { to: '/history', label: '复盘', id: 'review', icon: History },
  { to: '/practice', label: '练习', id: 'practice', icon: MessageCircle },
  { to: '/profile', label: '我的', id: 'profile', icon: UserRound },
]

export function AppShell({ children }: PropsWithChildren) {
  const location = useLocation()
  const navigate = useNavigate()
  const { pageRef, transitionTo } = useSceneTransition()
  const immersive = location.pathname === '/recording'
  const currentTab = location.pathname === '/' ? 'home'
    : /^\/(review|history|moment)(\/|$)/.test(location.pathname) ? 'review'
    : location.pathname.startsWith('/practice') ? 'practice' : 'profile'

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [location.pathname])

  function switchScene(event: MouseEvent<HTMLAnchorElement>, to: string) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    if (to === location.pathname) return
    transitionTo(() => navigate(to))
  }

  return (
    <div className={`app-frame ${immersive ? 'app-frame--dark' : ''}`}>
      <main className="page app-scene" ref={pageRef}>{children}</main>
      {!immersive && (
        <nav className="bottom-nav" aria-label={t("主导航")}>
          {items.map(({ to, label, id, icon: Icon }) => (
            <Link key={id} to={to} onClick={(event) => switchScene(event, to)} className={`nav-item ${currentTab === id ? 'is-active' : ''}`} aria-current={currentTab === id ? 'page' : undefined}>
              <span className="nav-icon"><Icon size={20} strokeWidth={1.8} aria-hidden="true" /></span>
              <span>{t(label)}</span>
            </Link>
          ))}
        </nav>
      )}
    </div>
  )
}
