import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ChevronRight, RefreshCw } from 'lucide-react'
import { listPracticeLibrary, listRemotePractices } from '../lib/api'
import type { PracticeLibraryItem } from '../lib/api'
import { t } from '../lib/i18n'
import { useAppStore } from '../store/useAppStore'
import { LanguageSettings } from '../components/LanguageSettings'
import { PracticeVoiceChat } from '../components/PracticeVoiceChat'
import { LearningGuide } from '../components/LearningGuide'
import { nextPracticePage, practiceScopeKey, scenesForCategory } from '../lib/practiceLibrary'

type Scene = {
  id: string
  title: string
  prompt: string
  hint: string
  openingLine?: string
  sceneLabel?: string
  relationship?: string | null
  register?: string | null
}

function libraryScene(item: PracticeLibraryItem): Scene {
  return {
    id: item.id,
    title: item.title,
    prompt: item.hidden_context || item.prompt,
    hint: item.hint,
    openingLine: item.opening_line,
    sceneLabel: item.scene_label,
    relationship: item.relationship,
    register: item.register,
  }
}

export function PracticePage() {
  const native = useAppStore((state) => state.nativeLanguage)
  const target = useAppStore((state) => state.targetLanguage)
  const owner = useAppStore((state) => state.ownerId)
  return <PracticeContent key={practiceScopeKey(owner, native, target)} />
}

function PracticeContent() {
  const native = useAppStore((state) => state.nativeLanguage)
  const target = useAppStore((state) => state.targetLanguage)
  const sessions = useAppStore((state) => state.sessions)
  const {eventId} = useParams()
  const [params] = useSearchParams()
  const generated = params.get('source') === 'ai'
  const [category, setCategory] = useState('')
  const [scene, setScene] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Scene | null>(null)
  const library = useQuery({
    queryKey: ['practice-library-v3', target, native, category, scene, page],
    queryFn: () => listPracticeLibrary(target, native, {
      category: category || undefined,
      scene: scene || undefined,
      page,
      page_size: 12,
    }),
    staleTime: 86400000,
    enabled: !generated && !eventId,
  })
  const practices = useQuery({queryKey: ['practices'], queryFn: listRemotePractices, enabled: generated})
  const source = sessions.find((session) =>
    (session.targetLanguage || 'en') === target && session.events.some((candidate) => candidate.id === eventId)
  )
  const event = source?.events.find((candidate) => candidate.id === eventId)
  const sourceScene = event ? {
    id: event.id,
    title: source!.title,
    prompt: source!.turns.filter((turn) => event.turnIds.includes(turn.id) && turn.speaker !== 'you').at(-1)?.text || event.context,
    hint: event.suggestion,
  } : null
  const items: Scene[] = generated
    ? (practices.data || [])
        .filter((practice) => practice.source === 'deepseek' && (practice.target_language || 'en') === target)
        .map((practice) => ({id: practice.id, title: practice.title, prompt: practice.prompt, hint: practice.hint}))
    : sourceScene
      ? [sourceScene]
      : (library.data?.items || []).map(libraryScene)
  const query = generated ? practices : library
  const sceneOptions = scenesForCategory(library.data?.categories || [], category)

  return <div className={`content-page practice-page practice-chat-page${selected ? ' in-conversation' : ''}`}>
    <header className="page-header">
      {selected && <button className="icon-button" aria-label={t('选择场景')} onClick={() => {
        if (window.confirm(t('返回场景选择会结束当前对话，继续吗？'))) setSelected(null)
      }}><ArrowLeft size={20} /></button>}
      <div><h1>{t('对话练习')}</h1>{selected && <p className="header-subtitle">{selected.sceneLabel || selected.title}</p>}</div>
    </header>
    {selected
      ? <PracticeVoiceChat
          key={selected.id}
          sceneId={selected.id}
          title={selected.sceneLabel || selected.title}
          prompt={selected.prompt}
          openingLine={selected.openingLine}
          language={target}
        />
      : <>
          <LanguageSettings compact />
          <LearningGuide surface="practice" />
          {!generated && !sourceScene && <div className="practice-filters" aria-label={t('选择练习场景')}>
            <label>
              <span>{t('大类')}</span>
              <select value={category} onChange={(changeEvent) => {
                setCategory(changeEvent.target.value)
                setScene('')
                setPage(1)
              }}>
                <option value="">{t('全部大类')}</option>
                {(library.data?.categories || []).map((item) =>
                  <option key={item.code} value={item.code}>{item.label}（{item.item_count}）</option>
                )}
              </select>
            </label>
            <label>
              <span>{t('小类')}</span>
              <select value={scene} disabled={!category} onChange={(changeEvent) => {
                setScene(changeEvent.target.value)
                setPage(1)
              }}>
                <option value="">{t('全部小类')}</option>
                {sceneOptions.map((item) =>
                  <option key={item.code} value={item.code}>{item.label}（{item.item_count}）</option>
                )}
              </select>
            </label>
          </div>}
          <section className="practice-scenes" aria-label={t('选择场景')}>
            {items.map((item) => <button className="practice-scene" key={item.id} onClick={() => setSelected(item)}>
              <span className="practice-scene-content">
                <strong>{item.sceneLabel || item.title}</strong>
                {item.openingLine && <span className="practice-scene-opening">{item.openingLine}</span>}
                {(item.relationship || item.register) && <span className="practice-scene-meta">
                  {item.relationship && <span>{item.relationship}</span>}
                  {item.register && <span>{item.register}</span>}
                </span>}
              </span>
              <ChevronRight size={17} aria-hidden="true" />
            </button>)}
          </section>
          {query.isPending && <p role="status">{t('正在加载练习…')}</p>}
          {query.isError && <p role="alert" className="practice-load-error">{t('练习素材加载失败')}<button className="text-button" onClick={() => void query.refetch()}>{t('重试')}</button></p>}
          {!query.isPending && !query.isError && !items.length && <p className="journal-empty">{t('暂无练习')}</p>}
          {!generated && !sourceScene && !query.isError && (library.data?.total || 0) > 12 && <button
            className="practice-next-batch"
            onClick={() => setPage((current) => nextPracticePage(current, library.data?.total || 0, library.data?.page_size || 12))}
          ><RefreshCw size={17} />{t('换一批')}</button>}
          {!generated && !sourceScene && library.data?.attributions?.length ? <footer className="practice-attribution">
            <span>{t('练习来源')}：</span>
            {library.data.attributions.map((sourceItem) => <a key={`${sourceItem.dataset}-${sourceItem.license}`} href={sourceItem.url} target="_blank" rel="noreferrer">
              {sourceItem.dataset}{sourceItem.version ? ` ${sourceItem.version}` : ''} · {sourceItem.license}
            </a>)}
          </footer> : null}
        </>}
  </div>
}
