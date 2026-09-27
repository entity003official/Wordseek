import { create } from 'zustand'
import { persist } from 'zustand/middleware'
// Device IDs belong to this browser/device, not to a cloud account.
export const useAudioSettings = create<{ microphoneId: string; setMicrophoneId: (id: string) => void }>()(persist((set) => ({microphoneId: '', setMicrophoneId: (microphoneId) => set({microphoneId})}), {name: 'beyond-words-audio-device'}))
