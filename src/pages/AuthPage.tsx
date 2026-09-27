import { t } from '../lib/i18n'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, KeyRound } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Brand } from '../components/Brand'
import { getAuthCapabilities, oidcLoginUrl } from '../lib/api'

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { user, login, register } = useAuth()
  const location = useLocation()
  const capabilities = useQuery({ queryKey: ['auth-capabilities'], queryFn: getAuthCapabilities, staleTime: 300_000 })
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (user) return <Navigate to={(location.state as { from?: string } | null)?.from || '/'} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (mode === 'login') await login(email, password)
      else await register(email, password, displayName)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '操作失败，请稍后重试。')
    } finally {
      setBusy(false)
    }
  }

  const registering = mode === 'register'
  return (
    <main className="auth-page">
      <section className="auth-panel">
        <Brand />
        <div className="auth-heading"><h1>{registering ? t("创建账号") : t("欢迎回来")}</h1>{registering && <p>{t("记录并复盘真实对话")}</p>}</div>
        <form onSubmit={(event) => void submit(event)}>
          {registering && <label>{t("显示名称")}<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" required maxLength={80} /></label>}
          <label>{t("邮箱")}<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label>
          <label>{t("密码")}<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={registering ? 'new-password' : 'current-password'} required minLength={registering ? 12 : 1} />{registering && <small>{t("至少 12 个字符")}</small>}</label>
          {error && <p className="form-error">{t(error)}</p>}
          <button className="primary-button auth-submit" disabled={busy}>{busy ? t("正在处理…") : registering ? t("创建账号") : t("登录")} <ArrowRight size={17} /></button>
        </form>
        {capabilities.data?.oidc_enabled && <a className="secondary-button auth-oidc" href={oidcLoginUrl()}><KeyRound size={17} />{t("使用")}{capabilities.data.oidc_display_name}{t("登录")}</a>}
        <p className="auth-switch">{registering ? t("已经有账号？") : t("还没有账号？")} <Link to={registering ? '/login' : '/register'}>{registering ? t("直接登录") : t("创建账号")}</Link></p>
        {!registering && <p className="auth-switch"><Link to="/forgot-password">{t("忘记密码")}</Link></p>}
      </section>
    </main>
  )
}
