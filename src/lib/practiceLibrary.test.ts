import { describe, expect, it } from 'vitest'
import { nextPracticePage, practiceScopeKey, scenesForCategory } from './practiceLibrary'

const categories = [{
  code: 'daily_life', label: '日常生活', item_count: 2,
  scenes: [
    {code: 'weather', label: '天气', item_count: 1},
    {code: 'hobbies', label: '兴趣爱好', item_count: 1},
  ],
}]

describe('practice library navigation', () => {
  it('uses the selected major category to determine minor categories', () => {
    expect(scenesForCategory(categories, 'daily_life').map((scene) => scene.code)).toEqual(['weather', 'hobbies'])
    expect(scenesForCategory(categories, 'missing')).toEqual([])
  })

  it('wraps the next batch after the final page', () => {
    expect(nextPracticePage(1, 25, 12)).toBe(2)
    expect(nextPracticePage(3, 25, 12)).toBe(1)
  })

  it('changes scope when either language changes so local filters reset', () => {
    expect(practiceScopeKey('user', 'zh', 'ja')).not.toBe(practiceScopeKey('user', 'zh', 'en'))
    expect(practiceScopeKey('user', 'zh', 'ja')).not.toBe(practiceScopeKey('user', 'en', 'ja'))
  })
})
