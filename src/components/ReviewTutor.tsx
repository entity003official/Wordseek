import { useEffect, useRef, useState } from 'react'
import { getTutorHistory, sendTutorMessage, transcribePracticeAudio, type TutorHistory } from '../lib/api'
import { useRecorder } from '../hooks/useRecorder'
import { usePromptAudio } from '../hooks/usePromptAudio'
import { useAppStore } from '../store/useAppStore'
import { t } from '../lib/i18n'
import type { Language } from '../lib/languages'

export function ReviewTutor({ sessionId, language, active = true }: { sessionId: string; language: Language; active?: boolean }) {
  return <section className="review-tutor"><TutorConversation sessionId={sessionId} language={language} active={active} /></section>
}
function TutorConversation({ sessionId, language, active }: { sessionId: string; language: Language; active: boolean }) {
  const [history, setHistory] = useState<TutorHistory>({messages: [], version: 0})
  const [loaded, setLoaded] = useState(false)
  const [pendingMessage, setPendingMessage] = useState('')
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [consented, setConsented] = useState(false)
  const alive = useRef(true)
  const end = useRef<HTMLDivElement>(null)
  const sending = useRef(false)
  const recorder = useRecorder()
  const native = useAppStore((s) => s.nativeLanguage)
  const [spoken, setSpoken] = useState('')
  const audio = usePromptAudio(spoken, /[\u3040-\u30ff]/.test(spoken) ? 'ja' : /[\u3400-\u9fff]/.test(spoken) ? (native === 'ja' ? 'ja' : 'zh') : language, Boolean(spoken))
  useEffect(() => { alive.current = true; void getTutorHistory(sessionId).then((v) => { if (alive.current) { setHistory(v); setLoaded(true) } }).catch(() => { if (alive.current) setError('陪练记录加载失败') }); return () => { alive.current = false } }, [sessionId])
  useEffect(() => { if (!active) { audio.stopPrompt(); if (recorder.status === 'recording') void record() } }, [active])
  useEffect(() => { if (spoken) void audio.playPrompt() }, [spoken])
  useEffect(() => { if (active) end.current?.scrollIntoView({block: 'nearest'}) }, [history.messages.length, pendingMessage, active])
  async function send(message = input) {
    if (!message.trim() || busy || sending.current || !loaded) return
    sending.current = true
    audio.stopPrompt()
    setBusy(true); setError(''); setPendingMessage(message.trim())
    try {
      const result = await sendTutorMessage(sessionId, message.trim(), history.version)
      if (alive.current) { setHistory(result); setInput('') }
    } catch (e) {
      if (alive.current) {
        setError(e instanceof Error ? e.message : '发送失败，请重试')
        try { setHistory(await getTutorHistory(sessionId)) } catch { /* Keep the unsent answer. */ }
      }
    } finally { sending.current = false; if (alive.current) { setBusy(false); setPendingMessage('') } }
  }
  async function record() {
    if (recorder.status === 'recording' || recorder.hasAudio) {
      setBusy(true); setError('')
      try {
        const result = await recorder.stop()
        if (result) {
          const transcript = await transcribePracticeAudio(result.blob, true, language)
          if (alive.current) setInput(transcript.text)
        }
      } catch (e) { if (alive.current) setError(e instanceof Error ? e.message : '语音转写失败') }
      finally { recorder.reset(); if (alive.current) setBusy(false) }
      return
    }
    if (!consented && !window.confirm(t('语音回答会发送给千问转写为文字，文字随后发送给 DeepSeek 陪练。是否允许？'))) return
    setConsented(true); audio.stopPrompt(); await recorder.start()
  }
  return <>

    {!loaded && !error && <p role="status">{t('正在加载陪练…')}</p>}
    <div className="tutor-messages" role="log" aria-label={t('陪练对话')}>
      {loaded && <article className="tutor-message is-assistant tutor-welcome"><p>{t('你可以找我练口语，或者一起学习语法和单词哟 (｡•̀ᴗ-)✧')}</p></article>}
      {history.messages.map((message, i) => <article className={`tutor-message is-${message.role}`} key={i}><p>{message.content}</p>{message.role === 'assistant' && <button className="text-button" disabled={busy || recorder.status === 'recording'} onClick={() => setSpoken(message.content)}>{t('朗读这条')}</button>}</article>)}
      {pendingMessage && <article className="tutor-message is-user"><p>{pendingMessage}</p></article>}
      {busy && <p className="tutor-thinking" role="status">{t(pendingMessage ? '正在回复…' : '正在转写…')}</p>}<div ref={end} />
    </div>
    {spoken && <div className="tutor-playback"><button className="secondary-button" disabled={recorder.status === 'recording'} onClick={() => void audio.playPrompt()}>{t(audio.speechState === 'playing' ? '暂停' : audio.speechState === 'loading' ? '取消等待播放' : '播放语音')}</button>{audio.speechError && <p role="alert">{t(audio.speechError)}</p>}</div>}

    <form className="tutor-composer" onSubmit={(e) => { e.preventDefault(); void send() }}>
      <label className="sr-only" htmlFor="tutor-answer">{t('发送消息')}</label>
      <textarea id="tutor-answer" placeholder={t('发消息，或说点什么…')} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && recorder.status !== 'recording') { event.preventDefault(); void send() } }} value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000} rows={3} disabled={busy} />
      <div className="tutor-actions"><button type="button" className="secondary-button" disabled={busy || recorder.status === 'requesting'} onClick={() => void record()}>{t(recorder.status === 'recording' ? '停止并转写' : '语音回答')}</button><button className="primary-button" disabled={busy || !loaded || !input.trim() || recorder.status === 'recording'}>{t('发送')}</button></div>
      {recorder.status === 'recording' && <p role="status">{Math.floor(recorder.elapsedMs / 1000)}s · {t('录音中')}</p>}
    </form>
    {(error || recorder.error) && <p role="alert">{t(error || recorder.error || '')}</p>}
    {!loaded && error && <button className="text-button" onClick={() => { void getTutorHistory(sessionId).then((v) => { setHistory(v); setLoaded(true); setError('') }).catch(() => setError('陪练记录加载失败')) }}>{t('重试')}</button>}
  </>
}
