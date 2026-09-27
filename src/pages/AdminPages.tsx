import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, AlertTriangle, AudioLines, Ban, Bot, CheckCircle2, Clock3, Database, ExternalLink, HardDrive, KeyRound, ListRestart, LogOut, RefreshCw, Search, Server, ShieldCheck, UsersRound } from 'lucide-react'
import { useDeferredValue, useState, type ReactNode } from 'react'
import {
  getAdminModelUsage,
  getAdminOverview,
  getAdminSystemHealth,
  listAdminAuditLogs,
  listAdminJobs,
  listAdminUsers,
  retryAdminJob,
  revokeAdminUserSessions,
  setAdminUserStatus,
  type AdminJob,
  type AdminRange,
  type AdminSeriesPoint,
} from '../lib/api'

const rangeLabels: Record<AdminRange, string> = { '24h': '24小时', '7d': '7天', '30d': '30天' }
const jobLabels: Record<string, string> = { speech: '语音识别', ai_review: 'AI复盘', practice_set: 'AI出题' }
const statusLabels: Record<string, string> = { queued: '等待中', running: '处理中', complete: '已完成', failed: '失败', active: '正常', disabled: '已冻结' }
const auditLabels: Record<string, string> = {
  'auth.register': '注册账号', 'auth.login': '登录', 'auth.logout': '退出登录',
  'auth.password_changed': '修改密码', 'auth.password_reset_requested': '请求重置密码',
  'auth.password_reset_completed': '完成密码重置', 'auth.revoke_other_sessions': '撤销其他登录',
  'admin.user_status_changed': '修改账号状态', 'admin.sessions_revoked': '管理员撤销登录',
  'admin.job_retried': '管理员重试任务',
}

export function formatAdminDate(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
}

export function formatAdminDuration(value?: number | null) {
  if (value === null || value === undefined) return '—'
  if (value < 1000) return `${value} ms`
  if (value < 60_000) return `${(value / 1000).toFixed(1)} 秒`
  return `${(value / 60_000).toFixed(1)} 分钟`
}

function PageHeader({ title, description, aside }: { title: string; description: string; aside?: ReactNode }) {
  return <div className="admin-page-head"><div><h2>{title}</h2><p>{description}</p></div>{aside}</div>
}

function RangeTabs({ value, onChange }: { value: AdminRange; onChange: (range: AdminRange) => void }) {
  return <div className="admin-range-tabs" aria-label="统计时间范围">{(['24h', '7d', '30d'] as AdminRange[]).map((item) => <button key={item} className={item === value ? 'is-active' : ''} onClick={() => onChange(item)}>{rangeLabels[item]}</button>)}</div>
}

function StatePanel({ loading, error, empty }: { loading: boolean; error?: Error | null; empty?: boolean }) {
  if (loading) return <div className="admin-state"><span className="admin-spinner" />正在加载数据…</div>
  if (error) return <div className="admin-state is-error"><AlertTriangle size={18} />{error.message}</div>
  if (empty) return <div className="admin-state">当前筛选条件下没有记录。</div>
  return null
}

function StatusPill({ value }: { value: string }) {
  return <span className={`admin-status status-${value}`}>{statusLabels[value] || value}</span>
}

function Pagination({ page, pageSize, total, onChange }: { page: number; pageSize: number; total: number; onChange: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return <div className="admin-pagination"><span>共 {total} 条，第 {page}/{pages} 页</span><div><button disabled={page <= 1} onClick={() => onChange(page - 1)}>上一页</button><button disabled={page >= pages} onClick={() => onChange(page + 1)}>下一页</button></div></div>
}

function TrendChart({ data, lines }: { data: AdminSeriesPoint[]; lines: Array<{ key: keyof AdminSeriesPoint; label: string; color: string }> }) {
  const width = 760
  const height = 210
  const pad = 24
  const values = data.flatMap((point) => lines.map((line) => Number(point[line.key]) || 0))
  const max = Math.max(...values, 1)
  const x = (index: number) => pad + (index * (width - pad * 2)) / Math.max(1, data.length - 1)
  const y = (value: number) => height - pad - (value / max) * (height - pad * 2)
  return <div className="admin-chart-wrap">
    <div className="admin-chart-legend">{lines.map((line) => <span key={String(line.key)}><i style={{ background: line.color }} />{line.label}</span>)}</div>
    <svg className="admin-line-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={lines.map((line) => line.label).join('、') + '趋势'}>
      {[0, .25, .5, .75, 1].map((tick) => <line key={tick} x1={pad} x2={width - pad} y1={y(max * tick)} y2={y(max * tick)} className="chart-grid" />)}
      {lines.map((line) => <polyline key={String(line.key)} fill="none" stroke={line.color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" points={data.map((point, index) => `${x(index)},${y(Number(point[line.key]) || 0)}`).join(' ')} />)}
    </svg>
    <div className="admin-chart-axis"><span>{data[0] ? formatAdminDate(data[0].bucket_start) : '—'}</span><span>{data.at(-1) ? formatAdminDate(data.at(-1)!.bucket_start) : '—'}</span></div>
  </div>
}

function Metric({ label, value, detail, icon }: { label: string; value: ReactNode; detail: string; icon: ReactNode }) {
  return <article className="admin-metric"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong><p>{detail}</p></div></article>
}

export function AdminOverviewPage() {
  const [range, setRange] = useState<AdminRange>('7d')
  const overview = useQuery({ queryKey: ['admin-overview', range], queryFn: () => getAdminOverview(range), refetchInterval: 15_000, refetchIntervalInBackground: false })
  const data = overview.data
  return <div className="admin-page">
    <PageHeader title="运行概览" description="查看产品使用、后台任务和模型服务的整体状态。" aside={<RangeTabs value={range} onChange={setRange} />} />
    <StatePanel loading={overview.isLoading} error={overview.error} />
    {data && <>
      <section className="admin-metric-grid">
        <Metric label="全部用户" value={data.totals.users} detail={`${rangeLabels[range]}内活跃 ${data.totals.active_users} 人`} icon={<UsersRound size={20} />} />
        <Metric label="对话会话" value={data.totals.sessions} detail={`当前有效登录 ${data.totals.active_sessions} 个`} icon={<AudioLines size={20} />} />
        <Metric label="任务成功率" value={`${Math.round(data.job_health.success_rate * 100)}%`} detail={`完成 ${data.job_health.complete} · 失败 ${data.job_health.failed}`} icon={<CheckCircle2 size={20} />} />
        <Metric label="等待处理" value={data.totals.pending_jobs} detail={`${rangeLabels[range]}内任务 ${data.totals.jobs} 个`} icon={<Clock3 size={20} />} />
      </section>
      <section className="admin-panel">
        <div className="admin-panel-head"><div><h3>业务处理趋势</h3><p>只显示数量，不包含用户录音或转写内容。</p></div><span>更新于 {formatAdminDate(data.generated_at)}</span></div>
        <TrendChart data={data.series} lines={[
          { key: 'sessions', label: '新会话', color: '#2563eb' },
          { key: 'jobs_complete', label: '完成任务', color: '#168166' },
          { key: 'jobs_failed', label: '失败任务', color: '#d14343' },
        ]} />
      </section>
      <section className="admin-provider-row">{data.providers.map((provider) => <article key={provider.provider} className="admin-provider-card">
        <div><span className={provider.configured ? 'is-ok' : 'is-error'}><i />{provider.configured ? '配置就绪' : '未配置'}</span><strong>{provider.provider === 'qwen' ? '千问语音' : 'DeepSeek分析'}</strong><small>{provider.model}</small></div>
        <dl><div><dt>调用</dt><dd>{provider.calls}</dd></div><div><dt>成功率</dt><dd>{Math.round(provider.success_rate * 100)}%</dd></div><div><dt>平均耗时</dt><dd>{formatAdminDuration(provider.average_latency_ms)}</dd></div></dl>
      </article>)}</section>
    </>}
  </div>
}

export function AdminUsersPage() {
  const client = useQueryClient()
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [role, setRole] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState('')
  const users = useQuery({ queryKey: ['admin-users', deferredSearch, role, status, page], queryFn: () => listAdminUsers({ query: deferredSearch, role, status, page, page_size: 25 }) })

  async function changeStatus(userId: string, next: 'active' | 'disabled') {
    const label = next === 'disabled' ? '冻结' : '启用'
    if (!window.confirm(`确定${label}这个账号吗？${next === 'disabled' ? '账号的所有登录会话将立即失效。' : ''}`)) return
    setBusy(userId); setNotice('')
    try {
      await setAdminUserStatus(userId, next)
      setNotice(`账号已${label}。`)
      await client.invalidateQueries({ queryKey: ['admin-users'] })
    } catch (error) { setNotice(error instanceof Error ? error.message : '账号操作失败。') } finally { setBusy('') }
  }

  async function revoke(userId: string) {
    if (!window.confirm('确定撤销这个账号的全部登录会话吗？用户需要重新登录。')) return
    setBusy(userId); setNotice('')
    try { await revokeAdminUserSessions(userId); setNotice('登录会话已经撤销。') }
    catch (error) { setNotice(error instanceof Error ? error.message : '会话撤销失败。') }
    finally { setBusy('') }
  }

  return <div className="admin-page">
    <PageHeader title="用户账号" description="管理账号状态和登录会话；这里无法查看用户录音或转写正文。" />
    <div className="admin-toolbar">
      <label className="admin-search"><Search size={17} /><input aria-label="搜索用户" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="搜索姓名或邮箱" /></label>
      <select aria-label="按角色筛选用户" value={role} onChange={(event) => { setRole(event.target.value); setPage(1) }}><option value="">全部角色</option><option value="user">普通用户</option><option value="admin">管理员</option></select>
      <select aria-label="按状态筛选用户" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}><option value="">全部状态</option><option value="active">正常</option><option value="disabled">已冻结</option></select>
    </div>
    {notice && <div className="admin-notice">{notice}</div>}
    <StatePanel loading={users.isLoading} error={users.error} empty={!users.data?.items.length} />
    {users.data?.items.length ? <section className="admin-table-panel"><div className="admin-table-scroll"><table className="admin-table"><thead><tr><th>账号</th><th>角色</th><th>状态</th><th>创建时间</th><th>最近登录</th><th>操作</th></tr></thead><tbody>
      {users.data.items.map((user) => <tr key={user.id}><td><strong>{user.display_name}</strong><small>{user.email}</small></td><td>{user.role === 'admin' ? '管理员' : '普通用户'}</td><td><StatusPill value={user.status} /></td><td>{formatAdminDate(user.created_at)}</td><td>{formatAdminDate(user.last_login_at)}</td><td><div className="admin-row-actions"><button onClick={() => void revoke(user.id)} disabled={busy === user.id}><LogOut size={15} />撤销登录</button><button className={user.status === 'active' ? 'is-danger' : ''} onClick={() => void changeStatus(user.id, user.status === 'active' ? 'disabled' : 'active')} disabled={busy === user.id}>{user.status === 'active' ? <Ban size={15} /> : <CheckCircle2 size={15} />}{user.status === 'active' ? '冻结' : '启用'}</button></div></td></tr>)}
    </tbody></table></div><Pagination page={page} pageSize={users.data.page_size} total={users.data.total} onChange={setPage} /></section> : null}
  </div>
}

export function AdminJobsPage() {
  const client = useQueryClient()
  const [kind, setKind] = useState('')
  const [status, setStatus] = useState('')
  const [provider, setProvider] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState('')
  const jobs = useQuery({
    queryKey: ['admin-jobs', kind, status, provider, dateFrom, dateTo, page],
    queryFn: () => listAdminJobs({ kind, status, provider, date_from: dateFrom, date_to: dateTo, page, page_size: 25 }),
    refetchInterval: (query) => query.state.data?.items.some((job) => job.status === 'queued' || job.status === 'running') ? 10_000 : false,
    refetchIntervalInBackground: false,
  })

  async function retry(job: AdminJob) {
    if (!window.confirm(`确定重试这项${jobLabels[job.kind]}任务吗？系统会保留原失败记录并创建新任务。`)) return
    setBusy(job.id); setNotice('')
    try {
      const result = await retryAdminJob(job.id)
      setNotice(`已创建重试任务 ${result.job_id.slice(0, 8)}。`)
      await client.invalidateQueries({ queryKey: ['admin-jobs'] })
    } catch (error) { setNotice(error instanceof Error ? error.message : '任务重试失败。') } finally { setBusy('') }
  }

  return <div className="admin-page">
    <PageHeader title="任务中心" description="监控语音和AI后台任务；失败原因经过脱敏，不显示输入正文和模型完整输出。" />
    <div className="admin-toolbar">
      <select aria-label="按类型筛选任务" value={kind} onChange={(event) => { setKind(event.target.value); setPage(1) }}><option value="">全部任务</option><option value="speech">语音识别</option><option value="ai_review">AI复盘</option><option value="practice_set">AI出题</option></select>
      <select aria-label="按状态筛选任务" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}><option value="">全部状态</option><option value="queued">等待中</option><option value="running">处理中</option><option value="complete">已完成</option><option value="failed">失败</option></select>
      <select aria-label="按模型筛选任务" value={provider} onChange={(event) => { setProvider(event.target.value); setPage(1) }}><option value="">全部模型</option><option value="qwen">千问</option><option value="deepseek">DeepSeek</option></select>
      <label className="admin-date-filter"><span>起始</span><input aria-label="任务起始日期" type="date" value={dateFrom} max={dateTo || undefined} onChange={(event) => { setDateFrom(event.target.value); setPage(1) }} /></label>
      <label className="admin-date-filter"><span>结束</span><input aria-label="任务结束日期" type="date" value={dateTo} min={dateFrom || undefined} onChange={(event) => { setDateTo(event.target.value); setPage(1) }} /></label>
      <button className="admin-refresh" onClick={() => void jobs.refetch()}><RefreshCw size={16} />刷新</button>
    </div>
    {notice && <div className="admin-notice">{notice}</div>}
    <StatePanel loading={jobs.isLoading} error={jobs.error} empty={!jobs.data?.items.length} />
    {jobs.data?.items.length ? <section className="admin-table-panel"><div className="admin-table-scroll"><table className="admin-table admin-jobs-table"><thead><tr><th>任务</th><th>账号</th><th>模型</th><th>状态</th><th>耗时</th><th>创建时间</th><th>操作</th></tr></thead><tbody>
      {jobs.data.items.map((job) => <tr key={job.id}><td><strong>{jobLabels[job.kind]}</strong><small>{job.id.slice(0, 8)} · 尝试 {job.attempt_count} 次{job.retry_of_job_id ? ' · 管理员重试' : ''}</small></td><td><span>{job.owner.display_name}</span><small>{job.owner.email}</small></td><td><span>{job.provider === 'qwen' ? '千问' : 'DeepSeek'}</span><small>{job.model}</small></td><td><StatusPill value={job.status} />{job.error_summary && <small className="admin-error-text">{job.error_code} · {job.error_summary}</small>}</td><td>{formatAdminDuration(job.duration_ms)}</td><td>{formatAdminDate(job.created_at)}</td><td>{job.status === 'failed' && job.retryable ? <button className="admin-action-button" disabled={busy === job.id} onClick={() => void retry(job)}><ListRestart size={15} />重试</button> : <span className="admin-muted">—</span>}</td></tr>)}
    </tbody></table></div><Pagination page={page} pageSize={jobs.data.page_size} total={jobs.data.total} onChange={setPage} /></section> : null}
  </div>
}

export function AdminModelsPage() {
  const [range, setRange] = useState<AdminRange>('7d')
  const usage = useQuery({ queryKey: ['admin-model-usage', range], queryFn: () => getAdminModelUsage(range), refetchInterval: 15_000, refetchIntervalInBackground: false })
  return <div className="admin-page">
    <PageHeader title="模型用量" description="查看应用记录的千问与DeepSeek调用情况，不包含API Key或请求正文。" aside={<RangeTabs value={range} onChange={setRange} />} />
    <StatePanel loading={usage.isLoading} error={usage.error} />
    {usage.data && <>
      <div className="admin-notice"><KeyRound size={17} />{usage.data.billing_notice}</div>
      <section className="admin-provider-row">{usage.data.providers.map((item) => <article key={item.provider} className="admin-usage-card">
        <header><span>{item.provider === 'qwen' ? <AudioLines size={19} /> : <Bot size={19} />}</span><div><strong>{item.provider === 'qwen' ? '千问语音' : 'DeepSeek分析'}</strong><small>{item.model}</small></div><StatusPill value={item.configured ? 'active' : 'disabled'} /></header>
        <dl><div><dt>记录调用</dt><dd>{item.calls}</dd></div><div><dt>成功率</dt><dd>{Math.round(item.success_rate * 100)}%</dd></div><div><dt>平均耗时</dt><dd>{formatAdminDuration(item.average_latency_ms)}</dd></div><div><dt>{item.provider === 'qwen' ? '音频分钟' : '输入Token'}</dt><dd>{item.provider === 'qwen' ? item.audio_minutes.toLocaleString() : item.input_tokens.toLocaleString()}</dd></div><div><dt>输出Token</dt><dd>{item.output_tokens.toLocaleString()}</dd></div><div><dt>最近成功</dt><dd>{formatAdminDate(item.last_success_at)}</dd></div></dl>
      </article>)}</section>
      <section className="admin-panel"><div className="admin-panel-head"><div><h3>模型调用趋势</h3><p>按实际持久化记录汇总。</p></div></div><TrendChart data={usage.data.series} lines={[{ key: 'qwen_calls', label: '千问调用', color: '#2563eb' }, { key: 'deepseek_calls', label: 'DeepSeek调用', color: '#7c3aed' }]} /></section>
    </>}
  </div>
}

export function AdminAuditPage() {
  const [action, setAction] = useState('')
  const [page, setPage] = useState(1)
  const logs = useQuery({ queryKey: ['admin-audit', action, page], queryFn: () => listAdminAuditLogs({ action, page, page_size: 25 }) })
  return <div className="admin-page">
    <PageHeader title="审计日志" description="追踪账号、安全和管理员操作；审计元数据经过字段白名单过滤。" />
    <div className="admin-toolbar"><select aria-label="按操作类型筛选审计日志" value={action} onChange={(event) => { setAction(event.target.value); setPage(1) }}><option value="">全部操作</option>{Object.entries(auditLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button className="admin-refresh" onClick={() => void logs.refetch()}><RefreshCw size={16} />刷新</button></div>
    <StatePanel loading={logs.isLoading} error={logs.error} empty={!logs.data?.items.length} />
    {logs.data?.items.length ? <section className="admin-table-panel"><div className="admin-table-scroll"><table className="admin-table"><thead><tr><th>时间</th><th>操作者</th><th>操作</th><th>目标</th><th>结果信息</th></tr></thead><tbody>
      {logs.data.items.map((entry) => <tr key={entry.id}><td>{formatAdminDate(entry.created_at)}</td><td><strong>{entry.actor?.display_name || '系统'}</strong><small>{entry.actor?.email || 'system'}</small></td><td>{auditLabels[entry.action] || entry.action}</td><td><span>{entry.target_type || '—'}</span><small>{entry.target_id?.slice(0, 12) || '—'}</small></td><td>{Object.keys(entry.metadata).length ? Object.entries(entry.metadata).map(([key, value]) => <small key={key}>{key}: {value}</small>) : '—'}</td></tr>)}
    </tbody></table></div><Pagination page={page} pageSize={logs.data.page_size} total={logs.data.total} onChange={setPage} /></section> : null}
  </div>
}

const healthLabels: Record<string, { title: string; icon: ReactNode }> = {
  api: { title: 'API服务', icon: <Server size={19} /> }, database: { title: 'PostgreSQL', icon: <Database size={19} /> },
  redis: { title: 'Redis队列', icon: <Activity size={19} /> }, storage: { title: '对象存储', icon: <HardDrive size={19} /> },
  worker_default: { title: 'AI Worker', icon: <Bot size={19} /> }, worker_speech: { title: '千问 Worker', icon: <AudioLines size={19} /> },
  qwen: { title: '千问配置', icon: <ShieldCheck size={19} /> }, deepseek: { title: 'DeepSeek配置', icon: <ShieldCheck size={19} /> },
}

export function AdminSystemPage() {
  const health = useQuery({ queryKey: ['admin-system-health'], queryFn: getAdminSystemHealth, refetchInterval: 15_000, refetchIntervalInBackground: false })
  return <div className="admin-page">
    <PageHeader title="系统状态" description="进行不产生模型费用的依赖检查；专业性能指标在Grafana中查看。" aside={<button className="admin-refresh" onClick={() => void health.refetch()}><RefreshCw size={16} />立即检查</button>} />
    <StatePanel loading={health.isLoading} error={health.error} />
    {health.data && <>
      <div className={`admin-health-summary ${health.data.status === 'ok' ? 'is-ok' : 'is-warning'}`}>{health.data.status === 'ok' ? <CheckCircle2 size={21} /> : <AlertTriangle size={21} />}<div><strong>{health.data.status === 'ok' ? '所有必要服务运行正常' : '部分服务需要处理'}</strong><small>检查时间：{formatAdminDate(health.data.checked_at)}</small></div></div>
      <section className="admin-health-grid">{Object.entries(health.data.checks).map(([key, item]) => <article key={key}><span>{healthLabels[key]?.icon || <Activity size={19} />}</span><div><strong>{healthLabels[key]?.title || key}</strong><p>{item.detail}</p></div><i className={`health-dot is-${item.status}`} title={item.status} /></article>)}</section>
      <section className="admin-system-row"><article><div><h3>任务队列</h3><p>等待进入Worker的任务数量。</p></div><dl><div><dt>普通AI队列</dt><dd>{health.data.queues.default}</dd></div><div><dt>千问语音队列</dt><dd>{health.data.queues.speech}</dd></div></dl></article><article><div><h3>Grafana专业监控</h3><p>查看接口延迟、错误率、Worker和基础设施指标。</p></div>{health.data.grafana_url ? <a href={health.data.grafana_url} target="_blank" rel="noreferrer"><ExternalLink size={16} />打开Grafana</a> : <span className="admin-muted">生产环境请通过内网、VPN或SSH隧道访问</span>}</article></section>
      <div className="admin-privacy-boundary"><ShieldCheck size={18} /><p><strong>隐私边界</strong>本页面不会探测真实模型接口，不显示密钥、录音地址、转写正文或模型完整输出。</p></div>
    </>}
  </div>
}
