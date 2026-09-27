import { describe, expect, it } from 'vitest'
import { createMockEvent } from '../data/mock'
import { formatDuration } from './format'

describe('formatDuration', () => {
  it('formats a shared millisecond timebase without rounding up', () => {
    expect(formatDuration(0)).toBe('00:00')
    expect(formatDuration(8_999)).toBe('00:08')
    expect(formatDuration(134_000)).toBe('02:14')
  })

  it('clamps negative times to zero', () => {
    expect(formatDuration(-1)).toBe('00:00')
  })
})

describe('mock interaction event disclosure', () => {
  it('keeps evidence references and avoids fabricated confidence', () => {
    const event = createMockEvent('marker-42')
    expect(event.markerIds).toEqual(['marker-42'])
    expect(event.turnIds.length).toBeGreaterThan(1)
    expect(event.uncertainty).toContain('结合原始录音核对')
  })
})
