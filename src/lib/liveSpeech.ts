export interface LiveSentence { id: number; text: string; start_ms: number; end_ms: number; final: boolean }

export async function connectLiveSpeech(sessionId: string, onSentence: (sentence: LiveSentence) => void, onError: (message: string) => void) {
  const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const url = new URL(`${base}/sessions/${sessionId}/live`, location.href)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  const socket = new WebSocket(url)
  let ready = false
  let ended = false
  let failed = false
  let finishResolve: (() => void) | undefined
  let rejectReady: (error: Error) => void = () => undefined
  const report = (message: string) => { if (!failed) { failed = true; onError(message) }; finishResolve?.() }
  const connected = new Promise<void>((resolve, reject) => {
    rejectReady = reject
    socket.onopen = () => {
      const token = document.cookie.split(';').map((entry) => entry.trim()).find((entry) => entry.startsWith('bw_csrf='))?.slice(8) || ''
      socket.send(JSON.stringify({ consent: true, csrf: decodeURIComponent(token) }))
    }
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data)
      if (message.type === 'ready') { ready = true; resolve() }
      if (message.type === 'sentence') onSentence(message)
      if (message.type === 'finished') { ended = true; finishResolve?.() }
      if (message.type === 'error') { report(message.message); reject(new Error(message.message)) }
    }
    socket.onerror = () => { report('实时连接失败，结束后可重新转写。'); reject(new Error('实时连接失败')) }
    socket.onclose = () => {
      if (!ended && !failed) report('实时连接已断开，录音仍会保存。')
      if (!ready) reject(new Error('实时连接未建立'))
      finishResolve?.()
    }
  })
  const timer = window.setTimeout(() => { socket.close(); rejectReady(new Error('实时连接超时')) }, 30000)
  try { await connected } finally { clearTimeout(timer) }
  return {
    send(data: ArrayBuffer) {
      if (socket.readyState !== WebSocket.OPEN || failed) return
      if (socket.bufferedAmount > 32000 * 5) { report('网络跟不上录音，已停止实时上传；结束后可重新转写。'); socket.close(); return }
      socket.send(data)
    },
    async finish() {
      if (ended || failed || socket.readyState !== WebSocket.OPEN) return
      await new Promise<void>((resolve) => {
        const timeout = window.setTimeout(() => { report('实时转写收尾超时，已保留已识别内容。'); socket.close(); resolve() }, 17000)
        finishResolve = () => { clearTimeout(timeout); resolve() }
        socket.send(JSON.stringify({ type: 'finish' }))
      })
      socket.close()
    },
    close() { ended = true; socket.close(); finishResolve?.() },
  }
}
