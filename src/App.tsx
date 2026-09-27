import { RecorderDevicePage } from './pages/RecorderDevicePage'
import { t } from './lib/i18n'
import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { AdminLayout } from './components/AdminLayout'
import { HomePage } from './pages/HomePage'
import { MomentPage } from './pages/MomentPage'
import { PracticePage } from './pages/PracticePage'
import { ProfilePage } from './pages/ProfilePage'
import { HistoryPage } from './pages/HistoryPage'
import { DataPage } from './pages/DataPage'
import { RecordingPage } from './pages/RecordingPage'
import { ReviewPage } from './pages/ReviewPage'
import { AuthPage } from './pages/AuthPage'
import { AdminAccessDeniedPage, AdminLoginPage } from './pages/AdminAuthPage'
import { AdminAuditPage, AdminJobsPage, AdminModelsPage, AdminOverviewPage, AdminSystemPage, AdminUsersPage } from './pages/AdminPages'
import { PasswordResetPage } from './pages/PasswordResetPage'
import { getRemoteSettings, listRemoteAttempts, listRemoteSessions, remoteToSession } from './lib/api'
import { useAppStore } from './store/useAppStore'
import { useAuth } from './auth/AuthContext'
import { getAdminAccess } from './auth/adminAccess'

export default function App() {
  const { user, loading } = useAuth()
  const location = useLocation()
  const mergeRemoteSessions = useAppStore((state) => state.mergeRemoteSessions)
  const replaceAttempts = useAppStore((state) => state.replaceAttempts)
  useAppStore((state) => state.dateFormat)
  const setDateFormat = useAppStore((state) => state.setDateFormat)
  const setGoal = useAppStore((state) => state.setGoal)
  const nativeLanguage = useAppStore((state) => state.nativeLanguage)
  const setLanguages = useAppStore((state) => state.setLanguages)
  useEffect(() => { document.documentElement.lang = nativeLanguage }, [nativeLanguage])
  const ownerId = useAppStore((state) => state.ownerId)
  const activateUser = useAppStore((state) => state.activateUser)
  const isAdminPath = location.pathname.startsWith('/admin')
  const adminAccess = getAdminAccess(user)

  useEffect(() => {
    if (!user) return
    activateUser(user.id)
    void listRemoteSessions()
      .then((sessions) => mergeRemoteSessions(sessions.map(remoteToSession)))
      .catch(() => undefined)
    void listRemoteAttempts()
      .then((attempts) => replaceAttempts(attempts.map((attempt) => ({
        id: attempt.id,
        eventId: attempt.event_id,
        createdAt: attempt.created_at,
        response: attempt.response,
        feedback: attempt.feedback,
      }))))
      .catch(() => undefined)
    void getRemoteSettings().then((settings) => { if (useAppStore.getState().ownerId !== user.id) return; setGoal(settings.goal); setDateFormat(settings.date_format || 'auto'); setLanguages(settings.native_language || 'zh', settings.target_language || 'en') }).catch(() => undefined)
  }, [activateUser, mergeRemoteSessions, replaceAttempts, setGoal, setLanguages, setDateFormat, user?.id])

  if (loading) return <div className="app-loading"><span /><p>{t("正在确认登录状态…")}</p></div>
  if (!user) {
    if (isAdminPath) return <Routes>
      <Route path="/admin/login" element={<AdminLoginPage />} />
      <Route path="/admin/*" element={<Navigate to="/admin/login" replace state={{ from: location.pathname }} />} />
    </Routes>
    return <Routes><Route path="/register" element={<AuthPage mode="register" />} /><Route path="/forgot-password" element={<PasswordResetPage mode="request" />} /><Route path="/reset-password" element={<PasswordResetPage mode="reset" />} /><Route path="*" element={<AuthPage mode="login" />} /></Routes>
  }
  if (ownerId !== user.id) return <div className="app-loading"><span /><p>{t("正在加载你的数据…")}</p></div>

  if (isAdminPath) {
    if (adminAccess === 'forbidden') return <AdminAccessDeniedPage />
    return <Routes>
      <Route path="/admin/login" element={<Navigate to="/admin/overview" replace />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<AdminOverviewPage />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="jobs" element={<AdminJobsPage />} />
        <Route path="models" element={<AdminModelsPage />} />
        <Route path="audit" element={<AdminAuditPage />} />
        <Route path="system" element={<AdminSystemPage />} />
        <Route path="*" element={<Navigate to="overview" replace />} />
      </Route>
    </Routes>
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/recording" element={<RecordingPage />} />
        <Route path="/review/:sessionId" element={<ReviewPage />} />
        <Route path="/moment/:sessionId/:eventId" element={<MomentPage />} />
        <Route path="/practice" element={<PracticePage />} />
        <Route path="/practice/:eventId" element={<PracticePage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/devices/recorder" element={<RecorderDevicePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/data" element={<DataPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}
