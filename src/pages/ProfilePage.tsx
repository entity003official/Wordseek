import { MicrophoneSettings } from '../components/MicrophoneSettings'
import { DateFormatSettings } from '../components/DateFormatSettings'
import { VoiceprintSettings } from '../components/VoiceprintSettings'
import { t } from '../lib/i18n'
import { Check, ChevronRight, Flag, History, LogOut, ShieldCheck, Sparkles, UserCog, UserRound, BookOpen } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { deleteAIContent, updatePreferences, updateRemoteSettings, updateProfile } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import { useAuth } from '../auth/AuthContext'

import { LanguageSettings } from '../components/LanguageSettings'

const goals = ['延续话题', '主动提问', '参与小组讨论', '请求澄清']

export function ProfilePage() {
  const sessions = useAppStore((state) => state.sessions)
  const attempts = useAppStore((state) => state.attempts)
  const goal = useAppStore((state) => state.goal)
  const setGoal = useAppStore((state) => state.setGoal)
  const updateGuide = useAppStore((state) => state.updateGuide)
  const navigate = useNavigate()
  const { user, logout, refresh } = useAuth()
  const [aiEnabled, setAiEnabled] = useState(Boolean(user?.ai_enabled))
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const conversationCount = sessions.length
  const [openSetting, setOpenSetting] = useState<string | null>(null)
  const nativeLanguage = useAppStore((state) => state.nativeLanguage)
  const targetLanguage = useAppStore((state) => state.targetLanguage)
  const languageNames = { zh: '中文', en: 'English', ja: '日本語' }
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [avatar, setAvatar] = useState<string | null>(null)
  const [profileBusy, setProfileBusy] = useState(false)
  const [profileError, setProfileError] = useState('')

  function editProfile() {
    setName(user?.display_name || '')
    setAvatar(user?.avatar || null)
    setProfileError('')
    setEditing(true)
  }

  async function chooseAvatar(file?: File) {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
      setProfileError('请选择 10MB 以内的 JPG、PNG 或 WebP 图片')
      return
    }
    setProfileBusy(true)
    setProfileError('')
    const url = URL.createObjectURL(file)
    try {
      const image = new Image()
      image.src = url
      await image.decode()
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = 160
      const context = canvas.getContext('2d')
      if (!context) throw new Error()
      const side = Math.min(image.naturalWidth, image.naturalHeight)
      context.drawImage(image, (image.naturalWidth - side) / 2, (image.naturalHeight - side) / 2, side, side, 0, 0, 160, 160)
      setAvatar(canvas.toDataURL('image/png'))
    } catch { setProfileError('图片无法读取，请换一张') }
    finally { URL.revokeObjectURL(url); setProfileBusy(false) }
  }

  async function saveProfile() {
    if (!name.trim() || profileBusy) return
    setProfileBusy(true)
    setProfileError('')
    try {
      await updateProfile(name.trim(), avatar)
      await refresh()
      setEditing(false)
    } catch { setProfileError('保存失败，请重试') }
    finally { setProfileBusy(false) }
  }

  async function chooseGoal(nextGoal: string) {
    if (busy || nextGoal === goal) return
    const previousGoal = goal
    setGoal(nextGoal)
    setBusy(true)
    setNotice('')
    try {
      await updateRemoteSettings(nextGoal)
    } catch (error) {
      setGoal(previousGoal)
      setNotice(error instanceof Error ? error.message : '目标保存失败，请重试。')
    } finally {
      setBusy(false)
    }
  }

  async function toggleAI() {
    const next = !aiEnabled
    if (next && !window.confirm(t("开启后，系统会把经过基础脱敏的对话文本发送给 DeepSeek 进行总结、场景分析、出题和练习反馈。不会发送原始录音。自动脱敏不能保证识别全部人名或特殊隐私，是否继续？"))) return
    setBusy(true)
    setNotice('')
    try {
      await updatePreferences({ ai_enabled: next, consent_version: '2026-09-26.1' })
      setAiEnabled(next)
      await refresh()
      setNotice(next ? 'AI 分析已开启。' : 'AI 分析已关闭。')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '设置保存失败。')
    } finally {
      setBusy(false)
    }
  }

  async function removeAIContent() {
    if (!window.confirm(t("确定删除账号下全部 AI 生成内容吗？原始录音、转写和本地规则分析会保留。"))) return
    setBusy(true)
    try {
      await deleteAIContent()
      setNotice(t("AI 生成内容已经删除。"))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '删除失败。')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="content-page profile-page">
      <header className="profile-header">
        <button type="button" className="profile-avatar" onClick={editProfile} aria-label={t("编辑资料")}>{user?.avatar ? <img src={user.avatar} alt="" /> : <UserRound size={28} />}</button>
        <div className="profile-identity"><h1>{user?.display_name || t("我的")}</h1><p>{user?.email}</p></div><button className="text-button" onClick={editProfile}>{t("编辑")}</button>
      </header>

      {editing && <form className="profile-editor" onSubmit={(event) => { event.preventDefault(); void saveProfile() }}>
        <h2>{t('编辑资料')}</h2>
        <div className="profile-editor-avatar">
          <span className="profile-avatar">{avatar ? <img src={avatar} alt={t('头像预览')} /> : <UserRound size={28} />}</span>
          <label>{t('更换头像')}<input type="file" accept="image/png,image/jpeg,image/webp" disabled={profileBusy} onChange={(event) => { void chooseAvatar(event.target.files?.[0]); event.target.value = '' }} /></label>
          {avatar && <button type="button" className="text-button" disabled={profileBusy} onClick={() => setAvatar(null)}>{t('恢复默认')}</button>}
        </div>
        <label htmlFor="profile-name">{t('昵称')}</label>
        <input id="profile-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={80} required disabled={profileBusy} autoFocus autoComplete="nickname" />
        {profileError && <p role="alert">{t(profileError)}</p>}
        <div className="profile-editor-actions"><button type="button" className="secondary-button" disabled={profileBusy} onClick={() => setEditing(false)}>{t('取消')}</button><button className="primary-button" disabled={profileBusy || !name.trim()}>{t(profileBusy ? '保存中…' : '保存')}</button></div>
      </form>}
      <section className="profile-summary">
        <div><History size={20} /><strong>{conversationCount}</strong><span>{t("对话")}</span></div>
        <div><Flag size={20} /><strong>{attempts.length}</strong><span>{t("练习")}</span></div>
      </section>

      <section className="profile-settings-group" aria-labelledby="profile-learning-title">
        <h2 id="profile-learning-title">{t('学习偏好')}</h2>
        <div className="profile-settings-surface">
          <SettingRow title={t('语言与日期')} value={`${languageNames[nativeLanguage]} → ${languageNames[targetLanguage]}`} open={openSetting === 'language'} onToggle={() => setOpenSetting(openSetting === 'language' ? null : 'language')}><LanguageSettings /><DateFormatSettings /></SettingRow>
          <SettingRow title={t('我的目标')} value={t(goal)} open={openSetting === 'goal'} onToggle={() => setOpenSetting(openSetting === 'goal' ? null : 'goal')}>
<section>
        <p className="goal-description">{t("用于 AI 复盘和出题，不改变普通练习库。")}</p>
        <div className="goal-grid">{goals.map((item) => <button key={t(item)} className={goal === item ? 'is-selected' : ''} onClick={() => void chooseGoal(item)} disabled={busy} aria-pressed={goal === item}>{goal === item && <Check size={15} />}<span>{t(item)}</span></button>)}</div>
        <p className="goal-description">{t(({ 延续话题: "补充细节，让对话继续。", 主动提问: "根据对方的话追问。", 参与小组讨论: "接住话题，表达自己的观点。", 请求澄清: "没听懂时，请对方解释或确认。" } as Record<string, string>)[goal] || "")}</p>
      </section>
          </SettingRow>
        </div>
      </section>
      <section className="profile-settings-group" aria-labelledby="profile-audio-title">
        <h2 id="profile-audio-title">{t('录音设置')}</h2>
        <div className="profile-settings-surface">
          <SettingRow title={t('麦克风设定')} open={openSetting === 'microphone'} onToggle={() => setOpenSetting(openSetting === 'microphone' ? null : 'microphone')}><MicrophoneSettings /></SettingRow>
          <div className="profile-setting-row"><button className="profile-setting-trigger" onClick={() => navigate('/devices/recorder')}><span>{t('录音豆')}</span><small>Anker</small><ChevronRight size={17} aria-hidden="true" /></button></div>
          <SettingRow title={t('我的声纹')} open={openSetting === 'voiceprint'} onToggle={() => setOpenSetting(openSetting === 'voiceprint' ? null : 'voiceprint')}><VoiceprintSettings /></SettingRow>
        </div>
      </section>

      <section className="profile-settings-group" aria-labelledby="profile-service-title">
        <h2 id="profile-service-title">{t('服务与帮助')}</h2>
        <div className="profile-settings-surface">
          <SettingRow title={t('AI 洞察')} value={t(aiEnabled ? '已开启' : '已关闭')} open={openSetting === 'ai'} onToggle={() => setOpenSetting(openSetting === 'ai' ? null : 'ai')}>
      <section className="ai-settings-card">
        <div className="ai-settings-head"><span><Sparkles size={20} /></span><div><strong>{t("AI 洞察")}</strong><small>{aiEnabled ? t("已开启") : t("已关闭")}</small></div><button className={`switch-button ${aiEnabled ? 'is-on' : ''}`} onClick={() => void toggleAI()} disabled={busy} aria-pressed={aiEnabled} aria-label={t("开启或关闭 AI 洞察")}><i /></button></div>
        <details className="service-details"><summary>{t("服务与隐私详情")}</summary><p>{t("开启后仅将基础脱敏的转写发送给 DeepSeek，不发送原始录音。生成内容会保留来源与证据话轮。")}</p><button className="text-danger-button" onClick={() => void removeAIContent()} disabled={busy}>{t("删除 AI 生成内容")}</button></details>
      </section>
          </SettingRow>
        </div>
      <section className="settings-list">
        <button onClick={() => { updateGuide({ status: 'active', sessionId: null, reviewed: false, startFresh: true }); navigate('/') }}><span><BookOpen size={19} /></span><div><strong>{t("新手引导")}</strong></div><ChevronRight size={20} /></button>
        <button onClick={() => navigate('/history')}><span><History size={19} /></span><div><strong>{t("对话历史")}</strong></div><ChevronRight size={20} /></button>
        <button onClick={() => navigate('/data')}><span><ShieldCheck size={19} /></span><div><strong>{t("隐私与数据")}</strong></div><ChevronRight size={20} /></button>
        {user?.role === 'admin' && <button onClick={() => navigate('/admin')}><span><UserCog size={19} /></span><div><strong>{t("管理控制台")}</strong></div><ChevronRight size={20} /></button>}
      </section>

      </section>
      {notice && <div className="privacy-note">{t(notice)}</div>}

      <button className="secondary-button logout-button" onClick={() => void logout()}><LogOut size={17} />{t("退出登录")}</button>
    </div>
  )
}

function SettingRow({ title, value, open, onToggle, children }: { title: string; value?: string; open: boolean; onToggle: () => void; children: ReactNode }) {
  const id = useId()
  return <div className={`profile-setting-row${open ? ' is-open' : ''}`}>
    <button type="button" className="profile-setting-trigger" aria-expanded={open} aria-controls={id} onClick={onToggle}>
      <span>{title}</span>{value && <small>{value}</small>}<ChevronRight size={17} aria-hidden="true" />
    </button>
    <div id={id} hidden={!open} className="profile-setting-content">{open && children}</div>
  </div>
}
