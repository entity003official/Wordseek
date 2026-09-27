import { t } from '../lib/i18n'
import type { AIReview, Turn } from '../types'

export function LanguageReview({ review, language, turns, onPlay }: { review: AIReview; language: string; turns: Turn[]; onPlay: (turn: Turn) => void }) {
  const groups = [
    ['vocabulary', '重点词汇'],
    ['synonym', '同义替换'],
    ['natural_expression', '更自然的表达'],
  ] as const
  if (!review.learning_points) return <p className="privacy-note">{t('这是旧版复盘，重新生成可查看词汇和表达。')}</p>
  if (!review.learning_points.length) return <p className="privacy-note">{t('这段转写暂无足够的语言学习内容。')}{review.summary.limitations.join(' ')}</p>
  return <div className="language-review">
    {groups.map(([kind, title]) => {
      const points = review.learning_points?.filter((item) => item.kind === kind) || []
      if (!points.length) return null
      return <section key={kind}>
        <h3>{t(title)}</h3>
        {points.map((point, index) => {
          const turn = turns.find((item) => point.evidence_turn_ids.includes(item.id))
          return <article className="language-point" key={`${kind}-${index}`}>
            <div className="language-point-source"><span>{t('原句')}</span>{turn && <button type="button" className="text-button" onClick={() => onPlay(turn)}>{t('回听原句')}</button>}</div>
            <blockquote lang={language}>{point.original}</blockquote>
            <p>{point.explanation}</p>
            <div className="language-point-alternative"><span>{t(kind === 'vocabulary' ? '常用搭配' : kind === 'synonym' ? '可以换成' : '自然说法')}</span><p lang={language}>{point.alternative}</p></div>
            <p className="language-point-note">{point.usage_note}</p>
            <div className="language-point-example"><span>{t('例句')}</span><p lang={language}>{point.example}</p></div>
          </article>
        })}
      </section>
    })}
  </div>
}
