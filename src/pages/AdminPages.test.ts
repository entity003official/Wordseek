import { describe, expect, it } from 'vitest'
import { formatAdminDate, formatAdminDuration } from './AdminPages'

describe('admin presentation helpers', () => {
  it('formats task duration without exposing raw values as seconds', () => {
    expect(formatAdminDuration(null)).toBe('—')
    expect(formatAdminDuration(880)).toBe('880 ms')
    expect(formatAdminDuration(2_500)).toBe('2.5 秒')
    expect(formatAdminDuration(90_000)).toBe('1.5 分钟')
  })

  it('uses a stable empty value for missing audit timestamps', () => {
    expect(formatAdminDate()).toBe('—')
  })
})
