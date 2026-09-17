<template>
 <section class="wb-ops-heading"><div><span class="wb-eyebrow">MARKET DESK / {{ day }}</span><h2>标的、走势、采集状态，一屏核对。</h2><p>沿用旧系统已经沉淀的数据，区分旧策略记录与新版筛选。</p></div><a class="wb-button" href="/review/#/live/cockpit">打开旧版总控 ↗</a></section>
 <p v-if="error" class="wb-notice error">{{ error }} <button @click="load">重试</button></p>
 <div v-if="loading" class="wb-skeleton">正在核对旧任务与数据仓库…</div>
 <template v-if="report">
 <section class="wb-ops-stats"><article><span>启用的采集任务</span><strong>{{ report.enabled }}</strong><small>{{ report.scheduler }}</small></article><article :class="{alert:report.errors}"><span>上次运行异常</span><strong>{{ report.errors }}</strong><small>执行结果与入库量分别检查</small></article><article><span>旧策略重点记录</span><strong>{{ report.legacy_candidates.length }}</strong><small>最多5只；不是新发出的买入建议</small></article></section>
 <section class="wb-ops-desk"><div class="wb-panel wb-ops-list"><div class="wb-panel-title"><h3>旧系统留下的观察对象</h3><button class="wb-text-button" @click="$emit('open','screen','live')">新版筛选 ↗</button></div><p class="wb-footnote">优先读取旧确认阶段，再按原排名去重。记录不代表成交，分数不与新版混算。</p><button v-for="r in report.legacy_candidates" :key="r.code" :class="['wb-ops-stock',{active:selected?.code===r.code}]" @click="select(r)"><span><strong>{{ r.stock_name }}</strong><small>{{ r.code }} · {{ r.industry || '方向待补' }}</small></span><span>{{ status(r.status) }}<small>{{ stage(r.stage) }}</small></span></button><p v-if="!report.legacy_candidates.length" class="wb-empty">该日旧库暂无记录。可进入新版备选查看。</p><button class="wb-button primary full" @click="$emit('open','research','review')">查看收敛后的次日备选 →</button></div>
 <div class="wb-panel wb-ops-chart"><div class="wb-panel-title"><div><h3>{{ selected?.stock_name || '选择观察对象' }}</h3><p>{{ selected?.selected_time || '所选日期没有记录' }} · 旧策略记录时点</p></div><button v-if="selected" class="wb-button small" :disabled="busy" @click="$emit('collect','intraday',[selected.code])">补采此股分时</button></div><IntradayChart :chart="chart" :loading="chartLoading"/><p v-if="selected" class="wb-ops-reason">{{ selected.reason_text || '原记录未给出理由，不能自动补写。' }}</p></div></section>
 <section class="wb-panel"><div class="wb-panel-title"><div><h3>数据到底存在哪里？</h3><p>所选日期 {{ day }} · “最新日期”与“当日条数”分开显示</p></div><button class="wb-button small" @click="load">重新核对</button></div><div class="wb-storage-grid"><article v-for="(r,i) in report.coverage" :key="i"><span>{{ r.store }}</span><h4>{{ r.name }}</h4><strong>{{ r.day_rows ?? '未读到' }}<small v-if="r.day_rows!=null"> 条 / 所选日</small></strong><p>最新日期 {{ r.latest || '未知' }}</p></article></div><p class="wb-footnote">{{ report.note }}</p></section>
 <details class="wb-panel wb-ops-jobs"><summary>采集任务明细 · {{ report.errors }}项上次异常</summary><p class="wb-notice">{{ report.dependency_repair }}</p><div class="wb-table-scroll"><table class="wb-table"><thead><tr><th>任务 / 调度</th><th>上次执行</th><th>状态</th><th>下次计划</th></tr></thead><tbody><tr v-for="(r,i) in report.tasks" :key="i"><td>{{ r.name }}<small>{{ r.schedule }}</small></td><td>{{ time(r.last_run) }}</td><td :class="r.status==='error'?'status-error':''">{{ !r.enabled?'未启用':r.status==='ok'?'执行成功':r.status==='error'?'执行失败':'未确认' }}<small>{{ r.reason }}</small></td><td>{{ time(r.next_run) }}</td></tr></tbody></table></div></details>
 </template>
</template>
<script setup>
import {ref,watch} from 'vue'
import axios from 'axios'
import IntradayChart from './IntradayChart.vue'
const props=defineProps({day:String,busy:Boolean});defineEmits(['open','collect'])
const report=ref(null),loading=ref(false),error=ref(''),selected=ref(null),chart=ref(null),chartLoading=ref(false);let seq=0,chartSeq=0
const status=s=>({confirmed:'旧规则通过',accepted:'旧承接通过',watch:'观察',rejected:'未通过'})[s]||s
const stage=s=>({confirm1000:'旧确认阶段',accept945:'旧承接阶段',accept931:'旧早确认阶段'})[s]||s
const time=s=>s?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(s)):'未记录'
async function select(r){selected.value=r;chart.value=null;chartLoading.value=true;const id=++chartSeq;try{const res=await axios.get('/api/workbench/intraday/'+r.code,{params:{day:props.day}});if(id===chartSeq)chart.value=res.data}catch{if(id===chartSeq)error.value='分时数据暂不可读'}finally{if(id===chartSeq)chartLoading.value=false}}
async function load(){const id=++seq;loading.value=true;error.value='';try{const r=await axios.get('/api/workbench/integration-status',{params:{day:props.day},timeout:15000});if(id!==seq)return;report.value=r.data;const item=r.data.legacy_candidates.find(x=>x.code===selected.value?.code)||r.data.legacy_candidates[0];if(item)await select(item)}catch{if(id===seq)error.value='运行状态读取失败，请重试。'}finally{if(id===seq)loading.value=false}}
watch(()=>props.day,()=>{report.value=null;selected.value=null;chart.value=null;++chartSeq;load()},{immediate:true})
watch(()=>props.busy,(v,old)=>{if(old&&!v)load()})
</script>
