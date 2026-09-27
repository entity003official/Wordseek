import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { synthesizePracticeSpeech } from '../lib/api'
import { t } from '../lib/i18n'
import type { Language } from '../lib/languages'
import { useAppStore } from '../store/useAppStore'

/** Warm only the visible question. Playback always requires an explicit click. */
export function usePromptAudio(text: string, language: Language, enabled: boolean) {
  const owner = useAppStore((s) => s.ownerId)
  const client = useQueryClient()
  const options = {
    queryKey: ['practice-audio', owner, language, text],
    queryFn: () => synthesizePracticeSpeech(text, language),
    staleTime: Infinity,
    gcTime: 10 * 60 * 1000,
    retry: false as const,
  }
  const query = useQuery({ ...options, enabled: enabled && Boolean(owner), refetchOnWindowFocus: false, refetchOnReconnect: false, retryOnMount: false })
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle')
  const [error, setError] = useState('')
  const prepared = useRef<{ blob: Blob; url: string; audio: HTMLAudioElement } | null>(null)
  const request = useRef(0)

  function prepare(blob: Blob) {
    if (prepared.current?.blob === blob) return prepared.current.audio
    release()
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.preload = 'auto'
    audio.load()
    prepared.current = { blob, url, audio }
    return audio
  }
  function release() {
    const previous = prepared.current
    if (!previous) return
    previous.audio.onended = null
    previous.audio.onerror = null
    previous.audio.pause()
    previous.audio.removeAttribute('src')
    previous.audio.load()
    URL.revokeObjectURL(previous.url)
    prepared.current = null
  }
  function stop() {
    request.current += 1
    prepared.current?.audio.pause()
    setState('idle')
  }

  useEffect(() => {
    request.current += 1
    release()
    setState('idle')
    setError('')
    return () => { request.current += 1; release() }
  }, [text, language, owner])

  useEffect(() => {
    if (query.data) prepare(query.data.audio)
  }, [query.data])

  async function toggle() {
    if (!enabled || !owner) return
    if (state !== 'idle') { stop(); return }
    const token = ++request.current
    setError('')
    setState('loading')
    try {
      // fetchQuery joins preloading instead of issuing a second synthesis request.
      const result = query.data ?? await client.fetchQuery(options)
      if (token !== request.current) return
      if (!result) throw new Error(t('语音生成失败，请稍后重试。'))
      const audio = prepare(result.audio)
      audio.onended = () => { if (token === request.current) setState('idle') }
      audio.onerror = () => {
        if (token !== request.current) return
        setState('idle')
        setError(t('浏览器无法播放这段语音，请再试一次。'))
      }
      if (audio.ended) audio.currentTime = 0
      await audio.play()
      if (token === request.current) setState('playing')
    } catch (reason) {
      if (token !== request.current) return
      setState('idle')
      setError(reason instanceof Error ? t(reason.message) : t('语音生成失败，请稍后重试。'))
    }
  }
  return { speechState: state, speechError: error, preparing: query.isFetching, playPrompt: toggle, stopPrompt: stop }
}
