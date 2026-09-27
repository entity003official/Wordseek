import { t } from '../lib/i18n'
export function AudioWaveform({ levels, dark = false }: { levels: number[]; dark?: boolean }) {
  return (
    <div className={`waveform ${dark ? 'waveform--dark' : ''}`} aria-label={t("实时麦克风音量")}>
      {levels.map((level, index) => <i key={index} style={{ height: `${Math.max(8, Math.round(level * 62))}px` }} />)}
    </div>
  )
}
