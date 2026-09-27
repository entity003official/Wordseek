import { Activity, ArrowLeft, BrainCircuit, LayoutDashboard, ListTodo, LogOut, Menu, ScrollText, ShieldCheck, Users, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const sections = [
  { to: '/admin/overview', label: '运行概览', icon: LayoutDashboard },
  { to: '/admin/users', label: '用户账号', icon: Users },
  { to: '/admin/jobs', label: '任务中心', icon: ListTodo },
  { to: '/admin/models', label: '模型用量', icon: BrainCircuit },
  { to: '/admin/audit', label: '审计日志', icon: ScrollText },
  { to: '/admin/system', label: '系统状态', icon: Activity },
]

export function AdminLayout() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const current = sections.find((item) => location.pathname.startsWith(item.to)) || sections[0]

  return (
    <div className="admin-shell">
      <aside className={`admin-sidebar ${open ? 'is-open' : ''}`}>
        <div className="admin-brand">
          <span><ShieldCheck size={20} /></span>
          <div><strong>Beyond Words</strong><small>管理控制台</small></div>
          <button className="admin-mobile-close" onClick={() => setOpen(false)} aria-label="关闭导航"><X size={19} /></button>
        </div>
        <nav className="admin-nav" aria-label="管理员导航">
          {sections.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={() => setOpen(false)} className={({ isActive }) => isActive ? 'is-active' : ''}>
              <Icon size={18} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="admin-sidebar-foot">
          <div className="admin-identity"><span>{user?.display_name.slice(0, 1) || '管'}</span><div><strong>{user?.display_name}</strong><small>{user?.email}</small></div></div>
          <button onClick={() => navigate('/profile')}><ArrowLeft size={17} /> 返回用户端</button>
          <button onClick={() => void logout()}><LogOut size={17} /> 退出登录</button>
        </div>
      </aside>
      {open && <button className="admin-sidebar-mask" onClick={() => setOpen(false)} aria-label="关闭导航遮罩" />}
      <div className="admin-workspace">
        <header className="admin-topbar">
          <button className="admin-menu-button" onClick={() => setOpen(true)} aria-label="打开导航"><Menu size={20} /></button>
          <div><p>系统管理</p><h1>{current.label}</h1></div>
          <span className="admin-role"><i /> 管理员</span>
        </header>
        <main className="admin-main"><Outlet /></main>
      </div>
    </div>
  )
}
