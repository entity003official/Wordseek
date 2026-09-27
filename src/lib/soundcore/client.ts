import { SERVICE, WRITE, NOTIFY, command, FrameReader, deviceInfo, sessionKey, unwrapFile, decryptSlice, u32, type DeviceFile, type DeviceInfo } from './protocol'
import { wrapOpus } from './ogg'
interface Characteristic extends EventTarget { value?: DataView; startNotifications(): Promise<Characteristic>; writeValueWithResponse(value: Uint8Array): Promise<void> }
interface Device extends EventTarget { name?: string; gatt?: {connected: boolean; connect(): Promise<{getPrimaryService(uuid: string): Promise<{getCharacteristic(uuid: string): Promise<Characteristic>}>}>; disconnect(): void} }
interface Bluetooth { requestDevice(options: {filters: Array<{services: string[]}>}): Promise<Device> }
const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))
export const supportsBluetooth = () => window.isSecureContext && Boolean((navigator as Navigator & {bluetooth?: Bluetooth}).bluetooth)
export class SoundcoreClient {
  private device?: Device
  private writer?: Characteristic
  private notify?: Characteristic
  private reader = new FrameReader()
  private listeners = new Set<(frame: Uint8Array) => void>()
  private failures = new Set<(error: Error) => void>()
  private queue: Promise<unknown> = Promise.resolve()
  private key?: CryptoKey
  private cancelled = false
  onDisconnect?: () => void
  onInfo?: (info: DeviceInfo) => void
  private received = (event: Event) => {
    const value = (event.target as Characteristic).value
    if (!value) return
    for (const frame of this.reader.push(new Uint8Array(value.buffer, value.byteOffset, value.byteLength))) {
      if (frame[5] === 1 && frame[6] === 1) { try { this.onInfo?.(deviceInfo(frame)) } catch { /* A short unsolicited frame is ignored. */ } }
      for (const listener of this.listeners) listener(frame)
    }
  }
  private disconnected = () => {
    this.writer = undefined; this.key = undefined
    for (const reject of [...this.failures]) reject(new Error('设备已断开，请重新连接'))
    this.onDisconnect?.()
  }
  async connect() {
    this.cancelled = false
    const bluetooth = (navigator as Navigator & {bluetooth?: Bluetooth}).bluetooth
    if (!bluetooth || !window.isSecureContext) throw new Error('请在支持蓝牙的 Chrome 或 Edge 中打开网站')
    const device = await bluetooth.requestDevice({filters: [{services: [SERVICE]}]})
    if (this.cancelled) return
    this.device = device; device.addEventListener('gattserverdisconnected', this.disconnected)
    try {
      const server = await device.gatt?.connect()
      if (!server || this.cancelled) throw new Error('设备连接已取消')
      const service = await server.getPrimaryService(SERVICE)
      this.writer = await service.getCharacteristic(WRITE)
      this.notify = await service.getCharacteristic(NOTIFY)
      this.notify.addEventListener('characteristicvaluechanged', this.received)
      await this.notify.startNotifications()
      if (this.cancelled) throw new Error('设备连接已取消')
      return await this.info()
    } catch (error) { this.disconnect(); throw error }
  }
  disconnect() {
    this.cancelled = true
    this.notify?.removeEventListener('characteristicvaluechanged', this.received)
    this.device?.removeEventListener('gattserverdisconnected', this.disconnected)
    this.device?.gatt?.disconnect(); this.disconnected()
    this.reader = new FrameReader(); this.device = undefined; this.notify = undefined
  }
  private async write(frame: Uint8Array) {
    const writer = this.writer
    if (!writer) throw new Error('请先连接录音豆')
    for (let at = 0; at < frame.length; at += 20) {
      if (!this.writer || this.cancelled) throw new Error('设备已断开，请重新连接')
      await writer.writeValueWithResponse(frame.slice(at, at + 20))
    }
  }
  private async request(type: number, id: number, payload = new Uint8Array(0)) {
    const task = this.queue.then(async () => {
      await delay(350)
      return new Promise<Uint8Array>((resolve, reject) => {
        const finish = (error?: Error, data?: Uint8Array) => { clearTimeout(timer); this.listeners.delete(receive); this.failures.delete(fail); error ? reject(error) : resolve(data!) }
        const fail = (error: Error) => finish(error)
        const receive = (frame: Uint8Array) => { if (frame[5] === type && frame[6] === id) finish(undefined, frame) }
        const timer = setTimeout(() => finish(new Error('设备响应超时，请唤醒设备后重试')), 15000)
        this.listeners.add(receive); this.failures.add(fail)
        void this.write(command(type, id, payload)).catch(fail)
      })
    })
    this.queue = task.catch(() => undefined)
    return task
  }
  async info() { return deviceInfo(await this.request(1, 1)) }
  async bind() {
    const reply = await this.request(0x0b, 0x87, new Uint8Array([1]))
    if ((reply[4] & 15) !== 1) throw new Error('绑定未完成，请按设备按钮确认后重试')
    return this.info()
  }
  async record(start: boolean) {
    const reply = await this.request(0x18, 0x82, new Uint8Array([start ? 1 : 2]))
    if ((reply[4] & 15) !== 1) throw new Error('设备未接受录音指令')
    return this.info()
  }
  async files() {
    const files = new Map<number, DeviceFile>()
    for (let page = 0; page < 256; page++) {
      const payload = new Uint8Array(2); new DataView(payload.buffer).setUint16(0, page, true)
      const frame = await this.request(0x1a, 0x0e, payload)
      if (frame.length < 20) throw new Error('录音列表不完整，请重试')
      const count = frame[9] | frame[10] << 8
      if (11 + count * 8 + 8 > frame.length - 1) throw new Error('录音列表格式不支持')
      let added = 0
      for (let i = 0; i < count; i++) { const id = u32(frame, 11 + i * 8); if (!files.has(id)) added++; files.set(id, {id, size: u32(frame, 15 + i * 8)}) }
      if (!count || !added) return [...files.values()].sort((a, b) => b.id - a.id)
    }
    throw new Error('录音过多，请先在设备 App 中整理')
  }
  private async handshake() {
    if (this.key) return this.key
    const pair = await crypto.subtle.generateKey({name: 'ECDH', namedCurve: 'P-256'}, false, ['deriveBits'])
    const pub = new Uint8Array(await crypto.subtle.exportKey('raw', pair.publicKey))
    this.key = await sessionKey(await this.request(0x2e, 1, pub), pair.privateKey)
    return this.key
  }
  async download(file: DeviceFile, progress: (percent: number) => void, signal: AbortSignal) {
    if (file.size <= 0 || file.size > 100 * 1024 * 1024) throw new Error('此录音为空或超过 100 MB')
    const session = await this.handshake()
    if (signal.aborted) throw new Error('已取消导入')
    return new Promise<ReturnType<typeof wrapOpus>>((resolve, reject) => {
      let expected = file.size
      let secret: Awaited<ReturnType<typeof unwrapFile>> | undefined
      const parts = new Map<number, Uint8Array>()
      let processing = Promise.resolve()
      let finished = false
      let timer: ReturnType<typeof setTimeout>
      const cleanup = () => { clearTimeout(timer); this.listeners.delete(receive); this.failures.delete(fail); signal.removeEventListener('abort', abort) }
      const fail = (error: Error) => { if (!finished) { finished = true; cleanup(); this.disconnect(); reject(error) } }
      const abort = () => { fail(new Error('已取消导入')); this.disconnect() }
      const touch = () => { clearTimeout(timer); timer = setTimeout(() => fail(new Error('录音传输超时，请靠近设备后重试')), 45000) }
      const receive = (frame: Uint8Array) => {
        if (frame[5] !== 0x1a && frame[5] !== 0x1b) return
        if (![7, 8, 10, 18].includes(frame[6])) return
        touch()
        processing = processing.then(async () => {
          if (finished) return
          if (frame[6] === 7) {
            if (frame.length < 97 || u32(frame, 9) !== file.id) throw new Error('设备返回了不匹配的录音')
            expected = u32(frame, 13)
            if (!expected || expected > 100 * 1024 * 1024) throw new Error('录音大小无效')
            secret = await unwrapFile(frame, session)
          } else if (frame[6] === 8 || frame[6] === 18) {
            if (!secret) throw new Error('未收到录音解密信息')
            for (let at = 9; at + 165 <= frame.length - 1; at += 166) {
              const seq = u32(frame, at)
              if (!parts.has(seq)) parts.set(seq, await decryptSlice(frame.slice(at + 5, at + 165), seq, secret.key, secret.nonce))
            }
            if (parts.size * 160 > expected + 160) throw new Error('录音传输大小不匹配')
            progress(Math.min(99, Math.floor(parts.size * 160 / expected * 100)))
          } else {
            const ids = [...parts.keys()].sort((a, b) => a - b)
            if (!secret || !ids.length || ids.some((id, i) => id !== ids[0] + i) || parts.size * 160 < expected) throw new Error('录音不完整，请重新导入')
            finished = true; cleanup(); progress(100); resolve(wrapOpus(ids.map((id) => parts.get(id)!)))
          }
        }).catch((reason) => fail(reason instanceof Error ? reason : new Error('录音解密失败')))
      }
      this.listeners.add(receive); this.failures.add(fail); signal.addEventListener('abort', abort); touch()
      const payload = new Uint8Array(9); new DataView(payload.buffer).setUint32(4, file.id, true)
      void this.write(command(0x1a, 7, payload)).catch(fail)
    })
  }
}
