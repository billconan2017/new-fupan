// Research triage, not a probability model or executable recommendation.
export function triage(row, phase, mode) {
  const reasons=[]
  const pct=phase==='pre'?row.auction_pct:row.pct_chg
  const amount=phase==='pre'?row.auction_amount:row.amount
  if (/ST|退/i.test(row.name||'')) return {tier:'excluded',reason:'风险名称标记'}
  if (pct!=null && (pct<0 || pct>7)) return {tier:'excluded',reason:pct<0?'当下弱于昨收':'涨幅偏高，暂不追涨'}
  if (phase!=='pre' && row.in_pool) return {tier:'excluded',reason:'涨停状态，先核验能否成交'}
  if (row.score==null) reasons.push('评分字段未齐')
  else if(row.score<(mode==='trend'?75:65)) reasons.push('尚未达到重点阈值')
  if (phase!=='pre' && !['fresh','history'].includes(row.freshness?.state)) reasons.push('报价时效待确认')
  if (pct==null) reasons.push('涨幅缺失')
  if (amount==null || amount<(phase==='pre'?1e7:1e8)) reasons.push('成交活跃度不足或缺失')
  if (mode==='short' && phase!=='pre' && !(row.volume_ratio>=1.2)) reasons.push('量比不足或缺失')
  if (phase==='pre' && !(row.in_pool||row.strong||row.tags?.includes('前日龙虎榜'))) reasons.push('前日热点证据待确认')
  return {tier:reasons.length?'pending':'focus',reason:reasons.join('；')||'评分、活跃度与时点条件通过；入场仍需分时确认'}
}

export function diversify(rows, limit=5, perIndustry=2) {
  const counts=new Map(),out=[]
  for(const r of rows){
    // Unknown industry cannot be treated as independent verified sectors.
    const industry=r.industry||'未归类'
    if((counts.get(industry)||0)>=perIndustry)continue
    out.push(r);counts.set(industry,(counts.get(industry)||0)+1)
    if(out.length>=limit)break
  }
  return out
}

export function preparationFocus(rows) {
  return diversify(rows.filter(r=>r.overlap>=2 && r.amount>=1e8 && r.price>0 && !/ST|退/i.test(r.name||'')),8,2)
}
