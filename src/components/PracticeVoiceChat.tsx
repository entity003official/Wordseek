import { useEffect, useRef, useState } from 'react'
import { Keyboard, Mic, Send, Square, Volume2 } from 'lucide-react'
import { continueVoiceConversation, getPracticeConversation, synthesizePracticeSpeech, transcribePracticeAudio } from '../lib/api'
import { useRecorder } from '../hooks/useRecorder'
import { useAppStore } from '../store/useAppStore'
import { t } from '../lib/i18n'
import type { Language } from '../lib/languages'

type Message = {role: 'user' | 'assistant'; content: string; voice?: boolean}
export function PracticeVoiceChat({sceneId, title, prompt, openingLine, language}: {sceneId: string; title: string; prompt: string; openingLine?: string; language: Language}) {
  const initialMessages: Message[] = openingLine ? [{role: 'assistant', content: openingLine}] : []
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const history = useRef<Message[]>(initialMessages)
  const [version, setVersion] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const [input, setInput] = useState('')
  const [voiceInput, setVoiceInput] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pendingText, setPendingText] = useState('')
  const [error, setError] = useState('')
  const [playing, setPlaying] = useState<number | null>(null)
  const [retry, setRetry] = useState<{text: string; voice: boolean} | null>(null)
  const [recorded, setRecorded] = useState<Blob | null>(null)
  const consent = useRef(false)
  const lock = useRef(false)
  const alive = useRef(true)
  const playbackToken = useRef(0)
  const captureToken = useRef(0)
  const playback = useRef<{audio: HTMLAudioElement; url: string} | null>(null)
  const recorder = useRecorder()
  const recorderRef = useRef(recorder); recorderRef.current = recorder
  const native = useAppStore((s) => s.nativeLanguage)
  const addAttempt = useAppStore((s) => s.addAttempt)
  const end = useRef<HTMLDivElement>(null)
  function stopAudio() {
    playbackToken.current += 1
    const current = playback.current
    if (current) { current.audio.pause(); current.audio.onended = null; current.audio.onerror = null; current.audio.removeAttribute('src'); current.audio.load(); URL.revokeObjectURL(current.url); playback.current = null }
    if (alive.current) setPlaying(null)
  }
  useEffect(() => {
    alive.current = true
    void restoreConversation()
    const hide = () => { if (document.hidden) { captureToken.current += 1; stopAudio(); void recorderRef.current.stop() } }
    document.addEventListener('visibilitychange', hide)
    return () => { alive.current = false; captureToken.current += 1; stopAudio(); void recorderRef.current.stop(); document.removeEventListener('visibilitychange', hide) }
  }, [])
  useEffect(() => { end.current?.scrollIntoView({block: 'nearest'}) }, [messages.length, pendingText])
  async function restoreConversation() {
    setError('')
    try {
      const saved = await getPracticeConversation(sceneId, language)
      if (!alive.current) return
      const restored = saved.messages.length ? saved.messages : initialMessages
      history.current = restored
      setMessages(restored)
      setVersion(saved.version)
      setLoaded(true)
    } catch {
      if (alive.current) { setLoaded(false); setError('陪练记录加载失败') }
    }
  }
  async function speak(text: string, index: number) {
    stopAudio()
    const token = playbackToken.current
    setPlaying(index)
    try {
      const spokenLanguage = /[\u3040-\u30ff]/.test(text) ? 'ja' : /[\u3400-\u9fff]/.test(text) ? (native === 'ja' ? 'ja' : 'zh') : language
      const result = await synthesizePracticeSpeech(text, spokenLanguage)
      if (!alive.current || token !== playbackToken.current) return
      const url = URL.createObjectURL(result.audio); const audio = new Audio(url)
      playback.current = {audio, url}
      audio.onended = () => { if (token === playbackToken.current) stopAudio() }
      audio.onerror = () => { if (token === playbackToken.current) { stopAudio(); setError('语音播放失败，可点击消息重新播放') } }
      await audio.play()
    } catch {
      if (alive.current && token === playbackToken.current) { stopAudio(); setError('语音播放失败，可点击消息重新播放') }
    }
  }
  async function requestReply(text: string, voice: boolean) {
    setPendingText(text); setRetry({text, voice})
    const result = await continueVoiceConversation(sceneId, title, prompt, language, [...history.current, {role: 'user' as const, content: text}].map(({role, content}) => ({role, content})), version)
    if (!alive.current) return
    history.current = result.messages.map((message, index) => ({...message, voice: index === result.messages.length - 2 ? voice : undefined}))
    setVersion(result.version)
    setMessages(history.current); setRetry(null); setPendingText(''); setInput(''); setRecorded(null)
    if (result.attempt) addAttempt({id: result.attempt.id, eventId: result.attempt.event_id, response: result.attempt.response, feedback: result.attempt.feedback, createdAt: result.attempt.created_at})
    if (voice && !document.hidden) void speak(result.reply, history.current.length - 1)
  }
  async function send(text = input, voice = false) {
    if (!text.trim() || lock.current || !loaded) return
    lock.current = true; setBusy(true); setError(''); stopAudio()
    try { await requestReply(text.trim(), voice) }
    catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : '发送失败，请重试') }
    finally { lock.current = false; if (alive.current) { setBusy(false); setPendingText('') } }
  }
  async function transcribe(blob: Blob) {
    if (!blob.size) throw new Error(t('没有识别到语音，请再试一次。'))
    if (alive.current) setRecorded(blob)
    const result = await transcribePracticeAudio(blob, true, language)
    if (!alive.current) return
    const text = result.text.trim()
    if (!text) throw new Error(t('没有识别到语音，请再试一次。'))
    setInput(text)
    await requestReply(text, true)
  }
  async function finish(blob?: Blob) {
    if (lock.current) return
    lock.current = true; setBusy(true); setError('')
    try {
      const audio = blob || (await recorderRef.current.stop())?.blob
      if (alive.current && audio) await transcribe(audio)
    } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : '语音转写失败。') }
    finally { lock.current = false; if (alive.current) { recorderRef.current.reset(); setBusy(false); setPendingText('') } }
  }
  async function record() {
    if (lock.current || recorderRef.current.status === 'requesting') return
    if (recorderRef.current.status === 'recording') { await finish(); return }
    if (!consent.current && !window.confirm(t('语音将发送给千问转写，文字发送给 DeepSeek 陪练。是否开始？'))) return
    consent.current = true; stopAudio(); setError(''); setRecorded(null)
    const token = ++captureToken.current
    await recorderRef.current.start()
    if (!alive.current || token !== captureToken.current) await recorderRef.current.stop()
  }
  useEffect(() => { if (recorder.status === 'recording' && recorder.elapsedMs >= 60000) void finish() }, [recorder.status, recorder.elapsedMs])
  const recording = recorder.status === 'recording'
  return <section className="practice-messenger">
    <div className="messenger-log" role="log" aria-label={t('陪练对话')}>
      {!loaded && !error && <p className="messenger-empty" role="status">{t('正在加载陪练…')}</p>}
      {loaded && !messages.length && !pendingText && <p className="messenger-empty">{t('发消息，开始对话')}</p>}
      {messages.map((message, index) => <article className={`messenger-message is-${message.role}`} key={index}>
        <div className="messenger-bubble"><p>{message.content}</p>
          {(message.role === 'assistant' || message.voice) && <button className="messenger-play" disabled={recording || busy || recorder.status === 'requesting'} onClick={() => playing === index ? stopAudio() : void speak(message.content, index)} aria-label={t(playing === index ? '停止播放' : '朗读这条')}>{playing === index ? <Square size={15} /> : <Volume2 size={17} />}</button>}
        </div>
      </article>)}
      {pendingText && <article className="messenger-message is-user"><div className="messenger-bubble"><p>{pendingText}</p></div></article>}
      {busy && <p className="messenger-status" role="status">{t(pendingText ? '正在回复…' : '正在转写…')}</p>}
      <div ref={end} />
    </div>
    {(error || recorder.error) && <div className="messenger-error" role="alert">{t(error || recorder.error)}{!loaded && !busy && <button className="text-button" onClick={() => void restoreConversation()}>{t('重试')}</button>}{retry && loaded && !busy && <button className="text-button" onClick={() => void send(retry.text, retry.voice)}>{t('重新发送')}</button>}{recorded && !retry && !busy && <button className="text-button" onClick={() => void finish(recorded)}>{t('重试转写')}</button>}</div>}
    {recording && <div className="messenger-recording"><meter min={0} max={1} value={Math.min(1, (recorder.inputLevel ?? 0) * 8)} aria-label={t('麦克风音量')} /><span>{Math.floor(recorder.elapsedMs / 1000)}s</span><button className="text-button" onClick={() => { captureToken.current += 1; void recorder.stop().then(() => { if (alive.current) recorder.reset() }) }}>{t('取消')}</button></div>}
    <form className="messenger-composer" onSubmit={(e) => { e.preventDefault(); void send() }}>
      <button type="button" className="messenger-input-toggle" disabled={!loaded || busy || recording || recorder.status === 'requesting'} aria-label={t(voiceInput ? '切换键盘' : '语音输入')} onClick={() => setVoiceInput((v) => !v)}>{voiceInput ? <Keyboard size={22} /> : <Mic size={22} />}</button>
      {voiceInput ? <button type="button" className={`messenger-talk ${recording ? 'is-recording' : ''}`} disabled={!loaded || busy || recorder.status === 'requesting'} onClick={() => void record()}>{t(recording ? '点击发送' : recorder.status === 'requesting' ? '正在打开麦克风…' : '点击说话')}</button> : <textarea rows={1} maxLength={2000} value={input} disabled={!loaded || busy} onChange={(e) => { setInput(e.target.value); setRetry(null) }} aria-label={t('发送消息')} placeholder={t('发送消息')} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send() } }} />}
      {!voiceInput && <button className="messenger-send" disabled={!loaded || busy || !input.trim()} aria-label={t('发送')}><Send size={19} /></button>}
    </form>
  </section>
}
