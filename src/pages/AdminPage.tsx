import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Ban, CheckCircle2, LogOut, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listAdminUsers, revokeAdminUserSessions, setAdminUserStatus } from '../lib/api'

export function AdminPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const users = useQuery({ queryKey: ['admin-users'], queryFn: () => listAdminUsers() })
  const [busyId, setBusyId] = useState('')
  const [message, setMessage] = useState('')

  async function changeStatus(userId: string, next: 'active' | 'disabled') {
    setBusyId(userId)
    setMessage('')
    try {
      await setAdminUserStatus(userId, next)
      await queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '账号操作失败。')
    } finally {
      setBusyId('')
    }
  }

  async function revoke(userId: string) {
    setBusyId(userId)
    try {
      await revokeAdminUserSessions(userId)
      setMessage('该账号的登录会话已经撤销。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '会话撤销失败。')
    } finally {
      setBusyId('')
    }
  }

  return <div className="content-page admin-page">
    <header className="page-header"><button className="icon-button" onClick={() => navigate('/profile')} aria-label="返回"><ArrowLeft size={21} /></button><div><p className="eyebrow">系统管理</p><h1>账号控制</h1></div><ShieldCheck size={21} /></header>
    <p className="admin-note">管理员只能管理账号状态和登录会话，默认不能查看用户录音或转写正文。</p>
    {message && <div className="privacy-note">{message}</div>}
    {users.isLoading && <div className="placeholder-card">正在加载账号…</div>}
    {users.error && <div className="placeholder-card">{users.error.message}</div>}
    <section className="user-list">{users.data?.items.map((user) => <article key={user.id}>
      <div><strong>{user.display_name}</strong><span>{user.email}</span><small>{user.role === 'admin' ? '管理员' : '普通用户'} · {user.status === 'active' ? '正常' : '已冻结'}</small></div>
      <div className="user-actions"><button className="secondary-button" onClick={() => void revoke(user.id)} disabled={busyId === user.id}><LogOut size={15} /> 撤销登录</button><button className={user.status === 'active' ? 'danger-button' : 'secondary-button'} onClick={() => void changeStatus(user.id, user.status === 'active' ? 'disabled' : 'active')} disabled={busyId === user.id}>{user.status === 'active' ? <Ban size={15} /> : <CheckCircle2 size={15} />} {user.status === 'active' ? '冻结' : '启用'}</button></div>
    </article>)}</section>
  </div>
}
