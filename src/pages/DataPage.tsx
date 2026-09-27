import { t } from '../lib/i18n'
import { ArrowLeft, Download, ShieldCheck, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAudio } from '../lib/audioDb'
import { deleteAccount, deleteAllRemoteData, getRemoteExport } from '../lib/api'
import { useAppStore } from '../store/useAppStore'

export function DataPage() {
  const navigate = useNavigate()
  const clearUserData = useAppStore((state) => state.clearUserData)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function exportData() {
    setBusy(true)
    setMessage('')
    try {
      let payload: Record<string, unknown>
      let browserFallback = false
      try {
        payload = await getRemoteExport()
      } catch {
        const state = useAppStore.getState()
        payload = {
          exported_at: new Date().toISOString(),
          source: 'browser_fallback',
          sessions: state.sessions,
          attempts: state.attempts,
          settings: { goal: state.goal },
        }
        browserFallback = true
      }
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `beyond-words-export-${new Date().toISOString().slice(0, 10)}.json`
      anchor.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setMessage(browserFallback ? '后端当前不可用，已导出浏览器中保存的数据。录音可在复盘页单独下载。' : '数据导出已经开始。录音文件可在各对话复盘页单独下载。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '导出失败，请重试。')
    } finally {
      setBusy(false)
    }
  }

  async function deleteEverything() {
    if (!window.confirm(t("确定删除全部真实会话、录音、练习和设置吗？此操作无法撤销。"))) return
    setBusy(true)
    setMessage('')
    try {
      let remoteDeleted = true
      try {
        await deleteAllRemoteData()
      } catch {
        remoteDeleted = false
      }
      await clearAudio()
      clearUserData()
      setMessage(remoteDeleted ? '全部会话、录音、练习、AI 内容和学习设置已经删除。' : '浏览器中的会话和录音已删除；后端当前不可用，恢复连接后还需再次执行删除。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '清除失败，请重试。')
    } finally {
      setBusy(false)
    }
  }

  async function removeAccount() {
    const password = window.prompt(t("删除账号会永久移除账号及全部内容。请输入当前密码确认："))
    if (!password) return
    if (!window.confirm(t("最后确认：永久删除账号且无法撤销？"))) return
    setBusy(true)
    try {
      await deleteAccount(password)
      await clearAudio()
      clearUserData()
      window.location.assign('/login')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '账号删除失败。')
      setBusy(false)
    }
  }

  return (
    <div className="content-page data-page">
      <header className="page-header">
        <button className="icon-button" onClick={() => navigate('/profile')} aria-label={t("返回")}><ArrowLeft size={21} /></button>
        <div><h1>{t("隐私与数据")}</h1><p className="header-subtitle">{t("管理你的内容")}</p></div><span />
      </header>
      <section className="privacy-panel"><ShieldCheck size={26} /><div><strong>{t("你的内容由你控制")}</strong><p>{t("录音保存在私有空间，只有获得当次授权后才会用于分析。")}</p></div></section>
      <details className="privacy-details"><summary>{t("查看保存位置与服务商详情")}</summary><p>{t("录音先保存在当前浏览器，再同步到后端的私有对象存储。每次分析前可单独选择是否把该段录音临时发送给阿里云千问。DeepSeek 授权与语音授权彼此独立：只有在“我的”页面主动开启后，经过基础脱敏的转写文字才会发送给 DeepSeek，原始录音不会发送给 DeepSeek。")}</p></details>
      <section className="privacy-panel"><ShieldCheck size={22} /><div><strong>{t("参与者同意")}</strong><p>{t("每次录音前，请确认已取得所有参与者同意。")}</p></div></section>
      <section className="data-actions">
        <button className="secondary-button" onClick={() => void exportData()} disabled={busy}><Download size={19} />{t("导出我的数据")}</button>
        <div className="danger-zone"><strong>{t("危险操作")}</strong><button className="danger-button" onClick={() => void deleteEverything()} disabled={busy}><Trash2 size={19} />{t("删除全部内容")}</button><button className="text-danger-button" onClick={() => void removeAccount()} disabled={busy}>{t("永久删除账号")}</button></div>
      </section>
      {message && <div className="privacy-note">{message}</div>}
    </div>
  )
}
