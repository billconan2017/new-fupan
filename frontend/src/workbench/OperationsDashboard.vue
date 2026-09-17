<template>
 <div class="wb-desk-toolbar"><span class="wb-source-pill">旧确认池 · {{ day }}</span><span v-if="report" class="wb-desk-health">采集 {{ report.enabled }} <b :class="{'status-error':report.errors}">异常 {{ report.errors }}</b></span><button class="wb-text-button" @click="load">刷新</button><a class="wb-text-button" href="/review/#/live/cockpit">旧版 ↗</a></div>
 <p v-if="error" class="wb-notice error">{{ error }} <button @click="load">重试</button></p>
 <div v-if="loading" class="wb-skeleton">正在核对旧任务与数据仓库…</div>
 <template v-if="report">
 <section class="wb-ops-desk"><div class="wb-panel wb-ops-list"><div class="wb-panel-title"><h3>观察池 <small>最多5只</small></h3><button class="wb-text-button" @click="$emit('open','screen','live')">新版筛选 ↗</button></div><small class="wb-desk-disclaimer">旧策略记录 · 非实时买入指令</small><button v-for="r in report.legacy_candidates" :key="r.code" :class="['wb-ops-stock',{active:selected?.code===r.code}]" @click="select(r)"><span><strong>{{ r.stock_name }}</strong><small>{{ r.code }}</small></span><span>{{ status(r.status) }}</span></button><p v-if="!report.legacy_candidates.length" class="wb-empty">该日旧库暂无记录。可进入新版备选查看。</p><button class="wb-button primary full" @click="$emit('open','research','review')">次日备选 →</button></div>
 <div class="wb-panel wb-ops-chart"><div class="wb-panel-title"><div><h3>{{ selected?.stock_name || '选择观察对象' }}</h3><p>{{ selected?.code }} · 记录 {{ selected?.selected_time?.slice(11,16) || '—' }}</p></div><button v-if="selected" class="wb-button small" :disabled="busy" @click="$emit('collect','intraday',[selected.code])">补采此股分时</button></div><IntradayChart :chart="chart" :loading="chartLoading" compact/><details v-if="selected" class="wb-desk-detail"><summary>入选记录与依据</summary><p>{{ selected.reason_text || '原记录未给出理由' }}</p><small>{{ stage(selected.stage) }} · 原排名去重，分数不与新版混算。</small></details></div></section>
 <details class="wb-panel wb-ops-jobs"><summary>数据库继承范围 <small>部分接入，非全量迁移</small></summary><div class="wb-table-scroll"><table class="wb-table"><thead><tr><th>旧数据</th><th>接入程度</th><th>新版实际用途</th></tr></thead><tbody><tr v-for="r in inheritance" :key="r[0]"><td>{{ r[0] }}</td><td>{{ r[1] }}</td><td>{{ r[2] }}</td></tr></tbody></table></div></details>
 <details class="wb-panel wb-ops-jobs"><summary>数据库日期与条数</summary><div class="wb-panel-title"><div><h3>存储覆盖</h3><p>所选日期 {{ day }} · “最新日期”与“当日条数”分开显示</p></div><button class="wb-button small" @click="load">重新核对</button></div><div class="wb-storage-grid"><article v-for="(r,i) in report.coverage" :key="i"><span>{{ r.store }}</span><h4>{{ r.name }}</h4><strong>{{ r.day_rows ?? '未读到' }}<small v-if="r.day_rows!=null"> 条 / 所选日</small></strong><p>最新日期 {{ r.latest || '未知' }}</p></article></div><p class="wb-footnote">{{ report.note }}</p></details>
 <details class="wb-panel wb-ops-jobs"><summary>采集任务明细 · {{ report.errors }}项上次异常</summary><p class="wb-notice">{{ report.dependency_repair }}</p><div class="wb-table-scroll"><table class="wb-table"><thead><tr><th>任务 / 调度</th><th>上次执行</th><th>状态</th><th>下次计划</th></tr></thead><tbody><tr v-for="(r,i) in report.tasks" :key="i"><td>{{ r.name }}<small>{{ r.schedule }}</small></td><td>{{ time(r.last_run) }}</td><td :class="r.status==='error'?'status-error':''">{{ !r.enabled?'未启用':r.status==='ok'?'执行成功':r.status==='error'?'执行失败':'未确认' }}<small>{{ r.reason }}</small></td><td>{{ time(r.next_run) }}</td></tr></tbody></table></div></details>
 </template>
</template>
<script setup>
import {ref,watch} from 'vue'
import axios from 'axios'
import IntradayChart from './IntradayChart.vue'
const props=defineProps({day:String,busy:Boolean});defineEmits(['open','collect'])
const report=ref(null),loading=ref(false),error=ref(''),selected=ref(null),chart=ref(null),chartLoading=ref(false);let seq=0,chartSeq=0
const inheritance=[
 ['旧SQLite选股记录','已接入展示','首页最多5只，保留原时点和阶段'],
 ['旧博主观点表','只核查状态','读取更新日期，正文观点尚未进入新版评分'],
 ['旧PostgreSQL','只读核查','核对日期和条数；已向旧库补回9月17日选股记录'],
 ['旧日线、分钟线','尚未继承','新版图表使用量脉新采集的证据'],
 ['旧实时缓存、资金流、龙虎榜历史','未整体接入','新版对应模块主要重新采集；未全量迁移或合并评分'],
 ['Hermes / OpenClaw旧任务','沿用，读取状态','原任务继续写原库，不自动等于写入新版证据库']
]
const status=s=>({confirmed:'旧规则通过',accepted:'旧承接通过',watch:'观察',rejected:'未通过'})[s]||s
const stage=s=>({confirm1000:'旧确认阶段',accept945:'旧承接阶段',accept931:'旧早确认阶段'})[s]||s
const time=s=>s?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(s)):'未记录'
async function select(r){selected.value=r;chart.value=null;chartLoading.value=true;const id=++chartSeq;try{const res=await axios.get('/api/workbench/intraday/'+r.code,{params:{day:props.day}});if(id===chartSeq)chart.value=res.data}catch{if(id===chartSeq)error.value='分时数据暂不可读'}finally{if(id===chartSeq)chartLoading.value=false}}
async function load(){const id=++seq;loading.value=true;error.value='';try{const r=await axios.get('/api/workbench/integration-status',{params:{day:props.day},timeout:15000});if(id!==seq)return;report.value=r.data;const item=r.data.legacy_candidates.find(x=>x.code===selected.value?.code)||r.data.legacy_candidates[0];if(item)await select(item)}catch{if(id===seq)error.value='运行状态读取失败，请重试。'}finally{if(id===seq)loading.value=false}}
watch(()=>props.day,()=>{report.value=null;selected.value=null;chart.value=null;++chartSeq;load()},{immediate:true})
watch(()=>props.busy,(v,old)=>{if(old&&!v)load()})
</script>
