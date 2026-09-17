<template>
<section class="wb-panel"><div class="wb-panel-title"><div><h3>{{primary?'主策略 · 最近10个交易日':'热点对照 · 最近5个交易日'}}</h3><span>{{ report?.dates?.join(' / ') }} · 后续行情截至 {{ report?.asof || '—' }}</span></div><button class="wb-button" @click="load">刷新回溯结果</button></div>
<p v-if="error" role="alert" class="wb-notice error">{{ error }}</p><p v-if="!report?.complete" class="wb-notice">回溯尚未完成，以下可能为部分结果。</p>
<details class="wb-desk-detail"><summary>规则与成交假设</summary><p>{{ report?.note }}</p><div class="wb-rules"><strong>先固定规则，再看结果</strong><p>{{primary?'前日三类热点至少命中两类、成交额≥1亿，行业最多2只、总共最多5只，再核对次晨竞价':'前日涨停池 / 强势池 / 龙虎榜并集'}} → 当日竞价涨幅1%—8%、规则分≥60 → 排名前3只普通沪深主板股票 → 09:35首根五分钟收阳 → 模拟09:40入场。未触发不补选，涨跌停或数据缺失单列。</p></div></details>
<div class="wb-tags"><span v-for="(v,k) in report?.entry_counts || {}" :key="k">{{ names[k] || k }} {{ v }}</span></div>
<div class="wb-table-scroll"><table class="wb-table"><thead><tr><th>买入后退出</th><th>已评估</th><th>未到期 / 待核验 / 卖出受阻</th><th>已评估平均净变化</th><th>已评估盈利比例</th></tr></thead><tbody><tr v-for="r in report?.summary || []" :key="r.hold"><td>第{{ r.hold }}交易日收盘</td><td>{{ r.count }}笔</td><td>{{ r.counts.pending || 0 }} / {{ r.counts.unknown || 0 }} / {{ r.counts.blocked || 0 }}</td><td :class="r.mean_net_pct>0?'wb-up':'wb-down'">{{ pct(r.mean_net_pct) }}</td><td>{{ pct(r.win_rate) }}</td></tr></tbody></table></div>
<p class="wb-notice">不同持有期的已评估样本可能不同，不能直接据此选最佳天数。三种持有期均可评估的共同样本：{{ report?.common_cohort?.count || 0 }}笔；对应平均净变化 1日 {{ pct(report?.common_cohort?.means?.['1']) }} / 2日 {{ pct(report?.common_cohort?.means?.['2']) }} / 3日 {{ pct(report?.common_cohort?.means?.['3']) }}。</p>
<details class="wb-desk-detail"><summary>固定筛选条件对比 · T+1</summary><div class="wb-table-scroll"><table class="wb-table"><thead><tr><th>条件</th><th>候选 / 可评估</th><th>盈利比例</th><th>平均净变化</th></tr></thead><tbody><tr v-for="r in report?.comparisons || []" :key="r.name"><td>{{ r.name }}</td><td>{{ r.candidates }} / {{ r.evaluated }}</td><td>{{ pct(r.win_rate) }}</td><td>{{ pct(r.mean_net_pct) }}</td></tr></tbody></table></div><p>仅在原前三名内加条件，不补选；探索性对照，未做样本外验证。可评估样本不足时不能判断哪个条件更好。</p></details><div class="wb-panel-title"><h3>逐日候选与模拟结果</h3><select v-model="selectedDay" aria-label="回溯日期筛选"><option value="">全部日期</option><option v-for="d in report?.dates || []" :key="d">{{ d }}</option></select></div>
<details class="wb-desk-detail"><summary>逐日候选数量与数据覆盖 · {{visibleDays.length}}个交易日</summary><div v-for="d in visibleDays" :key="d.date" class="wb-rules"><strong>{{ d.date }} · 前日证据 {{ d.previous_date }} · 竞价 {{ d.auction_rows }}条 · 入选 {{ d.picked }}只</strong><small v-for="s in d.sources" :key="s.api">{{ s.api }}：{{ s.count }}条 / {{ sourceNames[s.status] || s.status }}　</small><p v-if="!d.picked">没有合格候选或来源核验未通过，保留空仓。</p></div></details>
<div class="wb-table-scroll"><table class="wb-table"><thead><tr><th>日期 / 标的</th><th>当时依据</th><th>入场结果</th><th>T+1及后续退出</th></tr></thead><tbody><tr v-for="(t,i) in trades" :key="i"><td>{{ t.signal_date }}<strong>{{ t.name }}</strong><small>{{ t.code }}</small></td><td>竞价涨幅 {{ pct(t.auction_pct) }}<small>规则分 {{ t.score }} / 100</small></td><td>{{ names[t.entry_status] || t.entry_status }}<small>{{ t.reason }}</small><small v-if="t.entry_price">09:40参考价 {{ t.entry_price }} · {{ t.shares }}股 · 含买入成本 {{ t.entry_cost }}元</small></td><td><div v-for="p in t.paths" :key="p.hold"><strong>{{ p.hold }}日 / {{ p.exit_date || '日历不足' }} · {{ names[p.status] || p.status }}</strong><small v-if="p.status==='evaluated'">参考价 {{ p.exit_price }} · 净变化 {{ pct(p.net_pct) }} · 模拟盈亏 {{ p.pnl }}元 · 费用与滑点 {{ p.total_costs }}元</small><small v-else>{{ p.reason }}</small></div><small v-if="!t.paths.length">未确认入场，不计算后续盈利。</small></td></tr></tbody></table></div>
<p class="wb-footnote">这是复核规则的探索性模拟，不是既往实盘业绩。尚未建立组合资金曲线；被阻碍或未完成退出的仓位，不能按零收益或已平仓处理。不得通过删除失败样本来美化收益。</p>
</section>
</template>
<script setup>
import {ref,computed,onMounted} from 'vue'
import axios from 'axios'
const props=defineProps({primary:Boolean})
const report=ref(null),error=ref(''),selectedDay=ref('')
const names={simulated:'模拟入场',not_entered:'未触发 / 不入场',unknown:'待核验',pending:'未到期',blocked:'卖出受阻',evaluated:'模拟已评估'}
const sourceNames={dated:'响应日期匹配',date_parameter_only:'仅请求日期，响应无日期',error:'请求失败',mismatch:'日期不匹配'}
const pct=n=>n==null?'—':(n>0?'+':'')+Number(n).toFixed(2)+'%'
const trades=computed(()=>(report.value?.trades||[]).filter(t=>!selectedDay.value||t.signal_date===selectedDay.value))
const visibleDays=computed(()=>(report.value?.days||[]).filter(t=>!selectedDay.value||t.date===selectedDay.value))
async function load(){error.value='';try{report.value=(await axios.get(props.primary?'/api/workbench/primary-replay':'/api/workbench/recent-replay')).data}catch{error.value='回溯结果读取失败，请重试。'}}
onMounted(load)
</script>
