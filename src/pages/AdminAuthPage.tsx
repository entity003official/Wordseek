import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, KeyRound, LockKeyhole, LogOut, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { getAdminDestination } from '../auth/adminAccess'
import { getAuthCapabilities, oidcLoginUrl } from '../lib/api'

export function AdminLoginPage() {
  const { login } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const destination = getAdminDestination(location.state)
  const capabilities = useQuery({ queryKey: ['auth-capabilities'], queryFn: getAuthCapabilities, staleTime: 300_000 })
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(email, password)
      navigate(destination, { replace: true })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败，请稍后重试。')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="admin-auth-page">
      <section className="admin-auth-card" aria-labelledby="admin-login-title">
        <aside className="admin-auth-intro">
          <div className="admin-auth-brand"><span><ShieldCheck size={22} /></span><div><strong>Beyond Words</strong><small>管理控制台</small></div></div>
          <div><p className="admin-auth-kicker">ADMINISTRATION</p><h1>业务与运行管理</h1><p>管理用户、任务、模型用量和系统运行状态。用户录音与转写正文不在管理后台展示。</p></div>
          <div className="admin-auth-security"><LockKeyhole size={18} /><span>仅管理员账号可以进入，所有管理操作都会写入审计日志。</span></div>
        </aside>
        <div className="admin-auth-form">
          <div className="admin-auth-heading"><span>管理员入口</span><h2 id="admin-login-title">登录管理控制台</h2><p>请使用已由部署方授权的管理员账号。</p></div>
          <form onSubmit={(event) => void submit(event)}>
            <label>管理员邮箱<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required /></label>
            <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="admin-auth-submit" disabled={busy}>{busy ? '正在验证身份…' : '进入管理控制台'} <ArrowRight size={17} /></button>
          </form>
          {capabilities.data?.oidc_enabled && <a className="admin-auth-oidc" href={oidcLoginUrl()}><KeyRound size={17} /> 使用{capabilities.data.oidc_display_name}登录</a>}
          <div className="admin-auth-links"><Link to="/"><ArrowLeft size={15} />返回用户端</Link><span>管理员账号不支持网页自助注册</span></div>
        </div>
      </section>
    </main>
  )
}

export function AdminAccessDeniedPage() {
  const { user, logout } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function switchAccount() {
    setBusy(true)
    setError('')
    try {
      await logout()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '退出失败，请稍后重试。')
      setBusy(false)
    }
  }

  return (
    <main className="admin-auth-page">
      <section className="admin-denied-card" aria-labelledby="admin-denied-title">
        <span className="admin-denied-icon"><LockKeyhole size={28} /></span>
        <p className="admin-auth-kicker">ACCESS RESTRICTED</p>
        <h1 id="admin-denied-title">当前账号没有管理员权限</h1>
        <p>你现在登录的是普通用户账号 <strong>{user?.email}</strong>。管理后台与用户端相互独立，不会自动把普通用户当作管理员。</p>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="admin-denied-actions">
          <button onClick={() => void switchAccount()} disabled={busy}><LogOut size={17} />{busy ? '正在退出…' : '切换管理员账号'}</button>
          <Link to="/"><ArrowLeft size={17} />返回用户端</Link>
        </div>
      </section>
    </main>
  )
}
