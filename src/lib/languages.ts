export type Language = 'zh' | 'en' | 'ja'
export const languageOptions: { code: Language; label: string }[] = [
  { code: 'zh', label: '中文' }, { code: 'en', label: 'English' }, { code: 'ja', label: '日本語' },
]
export const languageLocales = { zh: 'zh-CN', en: 'en-US', ja: 'ja-JP' }
