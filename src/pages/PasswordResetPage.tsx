import { t } from '../lib/i18n'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { requestPasswordReset, resetAccountPassword } from '../lib/api'

export function PasswordResetPage({ mode }: { mode: 'request' | 'reset' }) {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      if (mode === 'request') {
        const result = await requestPasswordReset(email)
        setMessage(result.development_reset_token ? `${result.message} 开发环境令牌：${result.development_reset_token}` : result.message)
      } else {
        await resetAccountPassword(params.get('token') || '', password)
        navigate('/login', { replace: true })
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '操作失败。')
    } finally {
      setBusy(false)
    }
  }

  return <main className="auth-page"><section className="auth-panel"><Brand /><div className="auth-heading"><h1>{mode === 'request' ? t("找回密码") : t("设置新密码")}</h1><p>{mode === 'request' ? t("输入注册邮箱以继续") : t("新密码至少需要 12 个字符")}</p></div><form onSubmit={(event) => void submit(event)}>{mode === 'request' ? <label>{t("邮箱")}<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label> : <label>{t("新密码")}<input type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>}<button className="primary-button" disabled={busy}>{busy ? t("正在处理…") : t("确认")}</button></form>{message && <p className="privacy-note">{message}</p>}<p className="auth-switch"><Link to="/login">{t("返回登录")}</Link></p></section></main>
}
