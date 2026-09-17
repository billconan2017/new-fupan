<template>
  <div>
    <div class="toolbar">
      <input aria-label="观察日期" type="date" class="date-input" v-model="day" @change="load" />
      <button class="btn btn-primary" :disabled="loading" @click="load">{{ loading ? '读取中…' : '刷新本地数据' }}</button>
      <button class="btn" :disabled="fetching || loading || day !== today" @click="fetchQuotes">{{ fetching ? '采集中…' : '采集今日行情' }}</button>
      <select aria-label="已有数据日期" class="date-input" @change="day=$event.target.value; load()" :value="day">
        <option value="" disabled>已有数据日期</option>
        <option v-for="d in payload?.available_dates || []" :key="d">{{ d }}</option>
      </select>
      <router-link class="btn" to="/admin/data-sources">检查缺失数据</router-link>
    </div>
    <p v-if="fetchMessage" role="status">{{ fetchMessage }}</p>
    <div v-if="error" class="card" role="alert">{{ error }}</div>
    <div v-if="selected" class="card" style="margin-bottom:16px">
      <div class="card-header"><strong>{{ selected.code }} {{ selected.name }} · 本地历史日线</strong><button class="btn" @click="selected=null; historyRequest++">关闭</button></div>
      <p>{{ historyLoading ? '读取旧库中…' : historyData?.msg }}</p>
      <p v-if="historyError" role="alert">{{ historyError }}</p>
      <template v-if="historyData?.items?.length">
        <p>截止 {{ historyEnd }} · 实际最新日期 {{ historyData.latest_date }} · {{ historyData.items.length }} 条 · 外部请求 0 次</p>
        <svg viewBox="0 0 700 130" style="width:100%;height:150px" role="img" aria-label="历史收盘价走势，复权口径未核验"><polyline :points="points" fill="none" stroke="var(--color-main)" stroke-width="2" /></svg>
        <details><summary>查看日线数值与来源</summary><div class="table-wrap"><table class="data-table"><thead><tr><th>日期</th><th>开</th><th>高</th><th>低</th><th>收</th><th>原始来源</th></tr></thead><tbody><tr v-for="b in historyData.items" :key="b.trade_date"><td>{{ b.trade_date }}</td><td>{{ b.open }}</td><td>{{ b.high }}</td><td>{{ b.low }}</td><td>{{ b.close }}</td><td>{{ b.source || '未标记' }}</td></tr></tbody></table></div></details>
      </template>
      <p v-else-if="!historyLoading && historyData?.ok">该股票在所选日期之前没有可用日线。</p>
    </div>
    <template v-if="payload">
      <div class="card evidence-banner">
        <strong>{{ payload.review.overall_score == null ? '证据不完整 · 暂不综合评分' : '规则评分 ' + payload.review.overall_score }}</strong>
        <p>观察日期 {{ payload.date }} · 基准日期 {{ payload.baseline_date || '缺失' }} · {{ payload.snapshot.freshness.label }}</p>
        <p>缺少：{{ payload.review.quality.missing.join('、') || '各模块已有记录，完整覆盖尚需核验' }}</p>
        <p class="muted">{{ payload.baseline_note }}。{{ payload.note }}</p>
      </div>
      <div class="kpi-row" style="grid-template-columns:repeat(auto-fit,minmax(140px,1fr))">
        <div v-for="k in kpis" :key="k.label" class="stat-card"><div class="stat-label">{{ k.label }}</div><div class="stat-value neutral">{{ k.value ?? '—' }}</div></div>
      </div>
      <div class="card" style="margin-top:16px">
        <div class="card-header"><div class="card-title">复盘 → 盘中观察</div><span class="tag tag-blue">{{ payload.watchlist.quoted }}/{{ payload.watchlist.total }} 只具有目标日快照报价</span></div>
        <p class="muted">按基准日连板数排序。刷新只读本地库，不消耗行情额度；涨停池成员不能代替实时价格。</p>
        <div class="toolbar"><input class="date-input" aria-label="筛选观察股票" v-model="search" placeholder="股票代码 / 名称 / 行业" /></div>
        <div class="table-wrap"><table class="data-table">
          <thead><tr><th>股票</th><th>基准日连板</th><th>行业</th><th>目标日涨停池</th><th>报价</th><th>涨跌幅</th><th>报价时间</th><th>时效</th></tr></thead>
          <tbody><tr v-for="r in filtered" :key="r.code">
            <td><button class="btn btn-sm" @click="loadHistory(r)">{{ r.code }} {{ r.name }}</button></td><td>{{ r.consecutive ?? '—' }}</td><td>{{ r.industry || '—' }}</td>
            <td>{{ r.in_today_limit_up ? '已入池' : '未匹配 / 待核实' }}</td><td>{{ r.price ?? '—' }}</td>
            <td :class="r.pct_chg > 0 ? 'up' : r.pct_chg < 0 ? 'down' : ''">{{ r.pct_chg == null ? '—' : r.pct_chg.toFixed(2) + '%' }}</td>
            <td>{{ r.source_at?.replace('T',' ') || '—' }}</td><td>{{ r.quote_status.label }}</td>
          </tr></tbody>
        </table></div>
        <p v-if="!filtered.length" class="muted">没有匹配的观察记录。先选择已有数据日期，或补齐更早日期的涨停池。</p>
      </div>
      <div class="grid-2" style="margin-top:16px">
        <div class="card"><div class="card-title">目标日行业线索</div><p class="muted">来自已入库涨停池的行业分布，不代表全市场板块强度。</p>
          <p v-for="i in payload.review.limit_up_analysis.top_industries || []" :key="i.industry">{{ i.industry }} <strong>{{ i.count }}只</strong></p>
        </div>
        <div class="card"><div class="card-title">行情证据</div>
          <p>本批快照 {{ payload.snapshot.rows }} 条；源时间缺失 {{ payload.snapshot.unknown_time }} 条</p>
          <p>采集时间：{{ payload.snapshot.collected_at || '未采集' }}</p>
          <p>源时间范围：{{ payload.snapshot.oldest_source_at || '未知' }} ～ {{ payload.snapshot.newest_source_at || '未知' }}</p>
          <p class="muted">盘后数据用于复盘，盘中是否及时按源时间判定；未接入券商执行。</p>
        </div>
      </div>
    </template>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())
const day=ref(today)
const fetching=ref(false), fetchMessage=ref('')
async function fetchQuotes(){
  fetching.value=true; fetchMessage.value=''
  try { const {data}=await axios.post('/api/snapshot/fetch',null,{timeout:30000}); fetchMessage.value=data.ok ? `已入库 ${data.count} 条行情` : data.msg; await load() }
  catch { fetchMessage.value='采集请求失败，已有数据保留，请查看数据源状态。' }
  finally { fetching.value=false }
}
const loading=ref(false), error=ref(''), payload=ref(null), search=ref('')
const selected=ref(null), historyData=ref(null), historyLoading=ref(false), historyError=ref(''), historyEnd=ref('')
let historyRequest=0
async function loadHistory(row){
  const id=++historyRequest; selected.value=row; historyData.value=null; historyLoading.value=true; historyError.value=''; historyEnd.value=payload.value.date
  try { const {data}=await axios.get(`/api/cockpit/history/${row.code}`,{params:{day:historyEnd.value},timeout:5000}); if(id===historyRequest) historyData.value=data }
  catch { if(id===historyRequest) historyError.value='历史查询失败，请稍后重试。' }
  finally { if(id===historyRequest) historyLoading.value=false }
}
const points=computed(()=>{
  const bars=historyData.value?.items || [], values=bars.map(r=>r.close), low=Math.min(...values), span=Math.max(...values)-low || 1
  return values.map((v,i)=>`${10+i*680/Math.max(values.length-1,1)},${120-(v-low)/span*110}`).join(' ')
})
let request=0
async function load(){
  selected.value=null; historyRequest++; const id=++request; loading.value=true; error.value=''; payload.value=null
  try { const {data}=await axios.get('/api/cockpit/summary',{params:{day:day.value},timeout:15000}); if(id===request) payload.value=data }
  catch { if(id===request) error.value='读取失败，请检查本地服务和数据库后重试。' }
  finally { if(id===request) loading.value=false }
}
const filtered=computed(()=> (payload.value?.watchlist.items || []).filter(r=>`${r.code} ${r.name} ${r.industry}`.includes(search.value.trim())))
const kpis=computed(()=>{
  const r=payload.value?.review || {}, w=payload.value?.watchlist || {}
  return [{label:'涨停记录',value:r.limit_up_analysis?.available ? r.limit_up_analysis.count : null},
    {label:'跌停记录',value:r.limit_down_analysis?.available ? r.limit_down_analysis.count : null},
    {label:'炸板记录',value:r.broken_board_analysis?.available ? r.broken_board_analysis.count : null},
    {label:'基准观察池',value:w.total},{label:'目标日已在涨停池',value:w.in_today_pool}]
})
onMounted(load)
</script>
<style scoped>
.evidence-banner{border-left:4px solid var(--color-orange);margin-bottom:16px}
p{font-size:13px;line-height:1.7;margin:8px 0}.muted{color:var(--text-secondary)}
</style>
