export function Brand({ light = false, compact = false }: { light?: boolean; compact?: boolean }) {
  return (
    <div className={`brand ${light ? 'brand--light' : ''}`}>
      <div className="brand-mark" aria-hidden="true"><span /><span /><span /><span /></div>
      {!compact && <strong>Beyond Words</strong>}
    </div>
  )
}
