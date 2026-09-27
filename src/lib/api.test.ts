import { describe, expect, it } from 'vitest'
import { analysisToPatch, remoteToSession, type RemoteSession } from './api'

const remote: RemoteSession = {
  id: 'server-1',
  title: '后端会话',
  scenario: '日常交流',
  created_at: '2026-09-24T10:00:00Z',
  duration_ms: 12000,
  processing_status: 'ready',
  markers: [{ id: 'marker-1', timestamp_ms: 5000 }],
  analysis: {
    mode: 'mock',
    turns: [
      { id: 'turn-1', speaker_id: 'SPEAKER_00', start_ms: 0, end_ms: 3000, text: 'Hello.' },
      { id: 'turn-2', speaker_id: 'SPEAKER_01', start_ms: 4000, end_ms: 6000, text: 'Hi.' },
    ],
    events: [{
      id: 'event-1',
      type: 'TOPIC_DEVELOPMENT',
      start_ms: 0,
      end_ms: 6000,
      turn_ids: ['turn-1', 'turn-2'],
      marker_ids: ['marker-1'],
      insight: { observation: '观察', context: '语境', suggestion: '建议', evidence_turn_ids: ['turn-1', 'turn-2'] },
    }],
  },
}

describe('remote session mapping', () => {
  it('restores server sessions using the shared frontend model', () => {
    const session = remoteToSession(remote)
    expect(session.remoteId).toBe('server-1')
    expect(session.markers[0].timestampMs).toBe(5000)
    expect(session.turns.map((turn) => turn.speaker)).toEqual(['partner', 'you'])
    expect(session.syncStatus).toBe('synced')
  })

  it('keeps mock disclosure when mapping analysis results', () => {
    const patch = analysisToPatch(remote.analysis!)
    expect(patch.isMockAnalysis).toBe(true)
    expect(patch.events[0].markerIds).toEqual(['marker-1'])
  })
})
