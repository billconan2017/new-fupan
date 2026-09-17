<template>
 <div class="wb-desk-toolbar"><span class="wb-source-pill">独立工作台 · {{ day }}</span><span class="wb-desk-health">量脉数据 · {{ data?.scored ?? '—' }}只可评分</span><button class="wb-text-button" @click="load">刷新</button><button class="wb-button small" :disabled="busy" @click="$emit('collect','review',[])">同步复盘</button></div>
 <p v-if="error" class="wb-notice error">{{ error }}</p>
 <div class="wb-market-strip" v-if="data"><div v-for="m in metrics" :key="m[0]"><small>{{ m[0] }}</small><strong>{{ m[1] ?? '—' }}</strong></div></div>
 <div v-if="loading" class="wb-skeleton">读取本地数据仓库…</div>
 <template v-if="data">
 <section class="wb-ops-desk"><div class="wb-panel wb-ops-list"><div class="wb-panel-title"><h3>{{ mode==='trend'?'趋势观察':'短线观察' }} <small>最多5只</small></h3><button class="wb-text-button" @click="$emit('open','screen','live')">筛选 ↗</button></div><small class="wb-desk-disclaimer">规则排序 · {{ data.entry_policy?.label || '入场需分时确认' }}</small><button v-for="r in candidates" :key="r.code" :class="['wb-ops-stock',{active:selected?.code===r.code}]" @click="select(r)"><span><strong>{{ r.name }}</strong><small>{{ r.code }} · {{ r.industry }}</small></span><span :class="r.pct_chg>=0?'wb-price-up':'wb-price-down'">{{ r.pct_chg?.toFixed(2) ?? '—' }}%<small>{{ r.score ?? '—' }}分 · {{ r.freshness?.state==='off_session'?'非盘中':r.freshness?.state==='history'?'历史':r.freshness?.label }}</small></span></button><p v-if="!candidates.length" class="wb-empty">当前没有足够证据的标的。等待采集，不填充旧池。</p><button class="wb-button primary full" @click="$emit('open','research','review')">次日备选 →</button></div>
 <div class="wb-panel wb-ops-chart"><div class="wb-panel-title"><div><h3>{{ selected?.name || '选择观察对象' }} <small>{{ selected?.code }}</small></h3><p>{{ selected?.source_at || '暂无有效行情时点' }}</p></div><button v-if="selected" class="wb-button small" :disabled="busy" @click="$emit('collect','intraday',[selected.code])">更新分时</button></div><IntradayChart :chart="chart" :loading="chartLoading" compact/><details v-if="selected" class="wb-desk-detail"><summary>评分依据与风险</summary><p v-for="f in selected.factors" :key="f.label">{{ f.label }} · {{ f.points ?? '缺失' }}/{{ f.max }} · {{ f.value }}</p><small>{{ selected.risks.join('；') || '规则条件需与分时共同核验' }}</small></details></div></section>
 <section class="wb-panel"><div class="wb-panel-title"><h3>涨停行业分布</h3><small>按涨停家数 · 非资金热力</small></div><div class="wb-sector-tiles"><button v-for="r in data.industries" :key="r.name" @click="$emit('open','research','review')" :style="{'--heat':Math.min(0.65,0.1+r.count/40)}"><strong>{{ r.name }}</strong><span>{{ r.count }} 家</span></button><p v-if="!data.industries.length" class="wb-empty">板块证据待采集</p></div></section>
 <details class="wb-panel wb-ops-jobs"><summary>自动采集与数据覆盖 <small>独立 systemd 调度 · PostgreSQL 记录</small></summary><p>{{ automation?.intraday }}</p><div class="wb-schedule-chips"><span v-for="s in automation?.schedule" :key="s.time">{{ s.time }} {{ s.name }}</span></div><p>{{ automation?.note }}</p><div class="wb-table-scroll"><table class="wb-table"><thead><tr><th>接口</th><th>状态</th><th>记录数</th></tr></thead><tbody><tr v-for="r in data.health" :key="r.api"><td>{{ r.name }}</td><td>{{ labels[r.status] || r.status }}</td><td>{{ r.rows }}</td></tr></tbody></table><table class="wb-table"><thead><tr><th>定时执行</th><th>阶段</th><th>结果</th></tr></thead><tbody><tr v-for="r in automation?.runs" :key="r.slot"><td>{{ r.slot }}</td><td>{{ r.stage }}</td><td>{{ labels[r.status] || r.status }} · {{ r.progress }}/{{ r.total }}</td></tr></tbody></table></div></details>
 </template>
</template>
<script setup>
import {ref,watch,computed,onUnmounted} from 'vue'
import axios from 'axios'
import IntradayChart from './IntradayChart.vue'
import {diversify} from './selection'
const props=defineProps({day:String,busy:Boolean,mode:{type:String,default:'short'}});defineEmits(['open','collect'])
const data=ref(null),automation=ref(null),loading=ref(false),error=ref(''),selected=ref(null),chart=ref(null),chartLoading=ref(false);let seq=0,chartSeq=0
const labels={ready:'可用',local:'本地证据',untested:'未采集',empty:'空数据',error:'异常',failed:'失败',partial:'部分缺失',done:'完成',running:'采集中',unavailable:'不可用'}
const candidates=computed(()=>diversify((data.value?.rows||[]).filter(r=>r.score!=null&&!/ST|退/i.test(r.name)&&!r.in_pool&&r.pct_chg>=0&&r.pct_chg<=7),5,2))
const metrics=computed(()=>{const m=data.value?.market||{};return [['样本上涨',m.up],['样本下跌',m.down],['涨停',m.limit_up],['跌停',m.limit_down],['炸板',m.broken],['龙虎榜记录',data.value?.health.find(x=>x.api==='lhb_daily')?.status==='ready'?m.dragon_count:null]]})
async function select(r){selected.value=r;chart.value=null;chartLoading.value=true;const id=++chartSeq;try{const res=await axios.get('/api/workbench/intraday/'+r.code,{params:{day:props.day}});if(id===chartSeq)chart.value=res.data}catch{if(id===chartSeq)error.value='分时暂不可读'}finally{if(id===chartSeq)chartLoading.value=false}}
async function load(){const id=++seq;loading.value=!data.value;error.value='';try{const [r,a]=await Promise.all([axios.get('/api/workbench/screen',{params:{day:props.day,phase:'live',mode:props.mode},timeout:15000}),axios.get('/api/workbench/automation')]);if(id!==seq)return;data.value=r.data;automation.value=a.data;const item=candidates.value.find(x=>x.code===selected.value?.code)||candidates.value[0];if(item)await select(item);else{selected.value=null;chart.value=null}}catch{if(id===seq)error.value='数据仓库暂不可读，请重试。'}finally{if(id===seq)loading.value=false}}
watch(()=>[props.day,props.mode],()=>{data.value=null;selected.value=null;chart.value=null;++chartSeq;load()},{immediate:true})
watch(()=>props.busy,(v,old)=>{if(old&&!v)load()})
const timer=setInterval(()=>{if(!document.hidden&&!props.busy)load()},60000)
onUnmounted(()=>{clearInterval(timer);++seq;++chartSeq})
</script>
