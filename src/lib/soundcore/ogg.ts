// Ogg encapsulation for the D3200 fixed 160-byte, mono Opus packet stream.
const text = (s: string) => new TextEncoder().encode(s)
export function wrapOpus(frames: Uint8Array[]) {
  const serial = crypto.getRandomValues(new Uint32Array(1))[0]
  let sequence = 0
  function page(packets: Uint8Array[], flags: number, granule: number) {
    const laces = packets.flatMap((p) => [...Array(Math.floor(p.length / 255)).fill(255), p.length % 255])
    const data = new Uint8Array(27 + laces.length + packets.reduce((n, p) => n + p.length, 0)); const view = new DataView(data.buffer)
    data.set(text('OggS')); data[5] = flags; view.setBigUint64(6, BigInt(granule), true); view.setUint32(14, serial, true); view.setUint32(18, sequence++, true)
    data[26] = laces.length; data.set(laces, 27)
    let at = 27 + laces.length; for (const packet of packets) { data.set(packet, at); at += packet.length }
    let crc = 0; for (const byte of data) { crc ^= byte << 24; for (let i = 0; i < 8; i++) crc = crc & 0x80000000 ? (crc << 1) ^ 0x04c11db7 : crc << 1 }
    view.setUint32(22, crc >>> 0, true); return data
  }
  const head = new Uint8Array(19); head.set(text('OpusHead')); head[8] = 1; head[9] = 1; new DataView(head.buffer).setUint32(12, 48000, true)
  const vendor = text('Beyond Words'); const tags = new Uint8Array(16 + vendor.length); tags.set(text('OpusTags')); new DataView(tags.buffer).setUint32(8, vendor.length, true); tags.set(vendor, 12)
  const pages = [page([head], 2, 0), page([tags], 0, 0)]
  let granule = 0
  for (let at = 0; at < frames.length; at += 50) {
    const batch = frames.slice(at, at + 50).map((p) => { let length = p.length; while (length > 1 && p[length - 1] === 0) length--; return p.slice(0, length) })
    granule += batch.length * 960; pages.push(page(batch, at + 50 >= frames.length ? 4 : 0, granule))
  }
  return {blob: new Blob(pages, {type: 'audio/ogg'}), durationMs: frames.length * 20}
}
