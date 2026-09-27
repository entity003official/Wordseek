import { useAppStore } from '../store/useAppStore'
import translations from './translations.json'
import { languageLocales } from './languages'

const messages: Record<string, string[]> = translations
export function t(source: string, values: Array<string | number> = []): string {
  const language = useAppStore.getState().nativeLanguage
  const message = language === 'zh' ? source : messages[source]?.[language === 'en' ? 0 : 1] ?? source
  return message.replace(/\{(\d+)\}/g, (token, index) => values[Number(index)] === undefined ? token : String(values[Number(index)]))
}
export function locale() {
  return languageLocales[useAppStore.getState().nativeLanguage] || 'zh-CN'
}
