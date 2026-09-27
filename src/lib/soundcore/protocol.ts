// Independent implementation of the documented D3200 wire protocol.
// Reference: https://github.com/tacshi/Soundcore/blob/main/PROTOCOL.md
export const SERVICE = '020cf5da-0000-1000-8000-00805f9b34fb'
export const WRITE = '00007777-0000-1000-8000-00805f9b34fb'
export const NOTIFY = '00008888-0000-1000-8000-00805f9b34fb'
export const u32 = (data: Uint8Array, offset: number) => new DataView(data.buffer, data.byteOffset, data.byteLength).getUint32(offset, true)
export function command(type: number, id: number, payload = new Uint8Array(0)) {
  const data = new Uint8Array(10 + payload.length)
  data.set([8, 238, 0, 0, 0, type, id]); new DataView(data.buffer).setUint16(7, data.length, true)
  data.set(payload, 9); data[data.length - 1] = data.slice(0, -1).reduce((sum, n) => sum + n, 0) & 255
  return data
}
export class FrameReader {
  private buffer = new Uint8Array(0)
  push(bytes: Uint8Array): Uint8Array[] {
    const next = new Uint8Array(this.buffer.length + bytes.length); next.set(this.buffer); next.set(bytes, this.buffer.length); this.buffer = next
    const frames: Uint8Array[] = []
    while (this.buffer.length >= 10) {
      if (this.buffer[0] !== 9 || this.buffer[1] !== 255 || this.buffer[2] !== 0 || this.buffer[3] !== 0) { this.buffer = this.buffer.slice(1); continue }
      const length = this.buffer[7] | this.buffer[8] << 8
      if (length < 10 || length > 60000) { this.buffer = this.buffer.slice(1); continue }
      if (this.buffer.length < length) break
      const frame = this.buffer.slice(0, length)
      if ((frame.slice(0, -1).reduce((a, b) => a + b, 0) & 255) !== frame[length - 1]) { this.buffer = this.buffer.slice(1); continue }
      frames.push(frame); this.buffer = this.buffer.slice(length)
    }
    return frames
  }
}
export type DeviceFile = {id: number; size: number}
export type DeviceInfo = {battery: number | null; caseBattery: number | null; serial: string; firmware: string; recording: boolean; freeKB: number; totalKB: number}
const battery = (n: number) => n <= 9 ? (n + 1) * 10 : n <= 100 ? n : null
export function deviceInfo(frame: Uint8Array): DeviceInfo {
  if (frame.length < 60) throw new Error('设备信息不完整，请重连')
  const text = (a: number, b: number) => new TextDecoder().decode(frame.slice(a, b)).replace(/\0/g, '').trim()
  return {battery: battery(frame[10]), caseBattery: battery(frame[47]), firmware: text(12, 17), serial: text(17, 33), totalKB: u32(frame, 33), freeKB: u32(frame, 37), recording: frame[59] === 1}
}
export async function sessionKey(publicReply: Uint8Array, privateKey: CryptoKey) {
  if (publicReply.length < 107) throw new Error('设备握手响应不完整')
  const publicKey = await crypto.subtle.importKey('raw', publicReply.slice(9, 74), {name: 'ECDH', namedCurve: 'P-256'}, false, [])
  const shared = await crypto.subtle.deriveBits({name: 'ECDH', public: publicKey}, privateKey, 256)
  if (!new Uint8Array(shared).every((n, i) => n === publicReply[74 + i])) throw new Error('设备密钥校验失败，请重新连接')
  const hkdf = await crypto.subtle.importKey('raw', shared, 'HKDF', false, ['deriveKey'])
  return crypto.subtle.deriveKey({name: 'HKDF', hash: 'SHA-256', salt: new Uint8Array([1, 2, 3]), info: new Uint8Array([1, 2, 3])}, hkdf, {name: 'AES-CTR', length: 256}, false, ['decrypt'])
}
export async function unwrapFile(frame: Uint8Array, key: CryptoKey) {
  if (frame.length < 97 || frame[95] !== 0) throw new Error('设备拒绝读取此录音')
  const plain = new Uint8Array(await crypto.subtle.decrypt({name: 'AES-CTR', counter: frame.slice(79, 95), length: 128}, key, frame.slice(33, 79)))
  if (new TextDecoder().decode(plain.slice(0, 14)) !== 'soundcored3200') throw new Error('录音解密失败，请重连设备')
  return {key: await crypto.subtle.importKey('raw', plain.slice(14, 46), 'AES-CTR', false, ['decrypt']), nonce: frame.slice(17, 29)}
}
export async function decryptSlice(bytes: Uint8Array, sequence: number, key: CryptoKey, nonce: Uint8Array) {
  const counter = new Uint8Array(16); counter.set(nonce); new DataView(counter.buffer).setUint32(12, sequence * 10, false)
  return new Uint8Array(await crypto.subtle.decrypt({name: 'AES-CTR', counter, length: 128}, key, bytes.slice()))
}
