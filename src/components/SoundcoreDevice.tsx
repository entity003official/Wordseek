import { useEffect, useRef, useState } from 'react'
import { Bluetooth, Download, RefreshCw } from 'lucide-react'
import { SoundcoreClient, supportsBluetooth } from '../lib/soundcore/client'
import type { DeviceFile, DeviceInfo } from '../lib/soundcore/protocol'
import { t } from '../lib/i18n'
import { formatShortDate } from '../lib/format'
export function SoundcoreDevice({onImport}: {onImport: (blob: Blob, duration: number, title: string) => Promise<void>}) {
  const [client] = useState(() => new SoundcoreClient())
  const [info, setInfo] = useState<DeviceInfo | null>(null)
  const [files, setFiles] = useState<DeviceFile[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [transfer, setTransfer] = useState<number | null>(null)
  const [progress, setProgress] = useState(0)
  const alive = useRef(true)
  const lock = useRef(false)
  const abort = useRef<AbortController | null>(null)
  useEffect(() => {
    alive.current = true
    client.onInfo = (value) => { if (alive.current) setInfo(value) }
    client.onDisconnect = () => { if (alive.current) { setInfo(null); setFiles([]) } }
    return () => { alive.current = false; abort.current?.abort(); client.disconnect() }
  }, [client])
  async function perform(action: () => Promise<void>) {
    if (lock.current) return
    lock.current = true; setBusy(true); setError('')
    try { await action() }
    catch (reason) { if (alive.current) setError(reason instanceof DOMException && reason.name === 'NotFoundError' ? '未选择设备，或附近没有录音豆' : reason instanceof Error ? reason.message : '设备操作失败，请重试') }
    finally { lock.current = false; if (alive.current) { setBusy(false); setTransfer(null) } }
  }
  async function refresh() {
    const status = await client.info()
    if (alive.current) setInfo(status)
    if (!status.recording) { const items = await client.files(); if (alive.current) setFiles(items) }
  }
  async function connect() { await client.connect(); if (alive.current) await refresh() }
  async function download(file: DeviceFile) {
    const controller = new AbortController(); abort.current = controller
    setTransfer(file.id); setProgress(0)
    try {
      const result = await client.download(file, (value) => { if (alive.current) setProgress(value) }, controller.signal)
      if (alive.current && !controller.signal.aborted) await onImport(result.blob, result.durationMs, `soundcore · ${file.id}`)
    } finally { abort.current = null }
  }
  return <section className="device-card soundcore-device">
    <header><span>soundcore Work D3200</span><small>{t(info ? '已连接' : '未连接')}</small></header>
    {!supportsBluetooth() ? <p>{t('当前浏览器不支持蓝牙直连，请用 Chrome 或 Edge 打开此网址。')}</p> : <>
      {!info ? <><p>{t('唤醒录音豆并靠近设备，关闭其他 App 的连接。')}</p><button className="primary-button" disabled={busy} onClick={() => void perform(connect)}><Bluetooth size={18} />{t(busy ? '正在连接…' : '连接录音豆')}</button></> : <>
        <div className="device-stats"><span>{t('录音豆')} <strong>{info.battery === null ? '—' : `${info.battery}%`}</strong></span><span>{t('充电盒')} <strong>{info.caseBattery === null ? '—' : `${info.caseBattery}%`}</strong></span></div>
        <div className="device-controls"><button className="secondary-button" disabled={busy} onClick={() => void perform(async () => { await client.record(!info.recording); await refresh() })}>{t(info.recording ? '暂停录音' : '开始录音')}</button><button className="text-button" onClick={() => { abort.current?.abort(); client.disconnect() }}>{t('断开连接')}</button></div>
        <details className="service-details"><summary>{t('设备信息')}</summary><p>{info.serial} · {info.firmware}</p><p>{Math.round(info.freeKB / 1024)} MB {t('可用')}</p><button className="secondary-button" disabled={busy} onClick={() => void perform(async () => { const status = await client.bind(); if (alive.current) setInfo(status) })}>{t('绑定设备')}</button><small>{t('如设备提示，请按录音豆按钮确认。')}</small></details>
        <div className="device-file-heading"><h2>{t('设备录音')}</h2><button className="icon-button" disabled={busy} aria-label={t('刷新')} onClick={() => void perform(refresh)}><RefreshCw size={17} /></button></div>
        {info.recording ? <p>{t('录音中，暂停后可导入。')}</p> : !files.length && !busy ? <p>{t('设备上暂无录音')}</p> : files.map((file) => <div className="device-file" key={file.id}><div><span>{file.id > 1000000000 && file.id < 4102444800 ? formatShortDate(new Date(file.id * 1000).toISOString()) : String(file.id)}</span><small>{(file.size / 1024 / 1024).toFixed(1)} MB</small></div><button className="text-button" disabled={busy} onClick={() => void perform(() => download(file))}><Download size={15} />{t('导入')}</button></div>)}
      </>}
    </>}
    {transfer !== null && <div className="device-transfer"><progress max={100} value={progress} /><span>{progress}%</span><button className="text-button" onClick={() => abort.current?.abort()}>{t('取消')}</button></div>}
    {error && <p className="speaker-error" role="alert">{t(error)}</p>}
  </section>
}
