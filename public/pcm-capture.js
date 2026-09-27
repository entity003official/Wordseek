class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super()
    this.buffer = []
    this.sum = 0
    this.count = 0
    this.phase = 0
    this.port.onmessage = () => { this.flush(); this.port.postMessage('flushed') }
  }
  flush() {
    if (!this.buffer.length) return
    const bytes = new ArrayBuffer(this.buffer.length * 2)
    const view = new DataView(bytes)
    this.buffer.forEach((value, i) => view.setInt16(i * 2, value, true))
    this.port.postMessage(bytes, [bytes])
    this.buffer = []
  }
  process(inputs) {
    const input = inputs[0]?.[0]
    if (input) for (const sample of input) {
      this.sum += sample
      this.count++
      this.phase += 16000
      if (this.phase >= sampleRate) {
        this.phase -= sampleRate
        const value = Math.max(-1, Math.min(1, this.sum / this.count))
        this.buffer.push(Math.round(value * (value < 0 ? 32768 : 32767)))
        this.sum = 0
        this.count = 0
        if (this.buffer.length >= 1600) this.flush()
      }
    }
    return true
  }
}
registerProcessor('pcm-capture', PcmCapture)
