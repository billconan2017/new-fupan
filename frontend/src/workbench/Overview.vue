<template>
<OperationsDashboard :mode="mode" :day="day" :busy="busy" @open="(...args)=>emit('open',...args)" @collect="(...args)=>emit('collect',...args)"/><details class="wb-panel wb-ops-jobs"><summary>新版证据完整性 · {{ report?.ready ?? '—' }} / {{ report?.total || 7 }} 项</summary>
<div v-if="loading" class="wb-skeleton" role="status">正在核对所选日期的本地证据…</div><p v-if="error" class="wb-notice error" role="alert">{{ error }}<button @click="load">重试</button></p>
<template v-if="report && !loading">
<section class="wb-workflow-grid"><button v-for="(w,i) in steps" :key="w.title" class="wb-workflow-card" @click="$emit('open',w.page,w.phase)"><span>0{{ i+1 }} · {{ w.time }}</span><h3>{{ w.title }} <b>↗</b></h3><p>{{ w.detail }}</p></button></section>
<section class="wb-panel"><div class="wb-panel-title"><div><span class="wb-eyebrow">DATA READINESS</span><h3>{{ report.verdict }}</h3><p>检查日期 {{ day }} · 每项只评价当前已有证据；样本齐全不等于全市场齐全。</p></div><button class="wb-button" @click="load">重新检查</button></div>
<div class="wb-readiness-grid"><article v-for="item in report.items" :key="item.key" :class="['wb-readiness-card',item.status]"><div><h4>{{ item.name }}</h4><span :class="'status-'+item.status">{{ status(item.status) }}</span></div><strong>{{ item.value }}</strong><p>{{ item.detail }}</p><button v-if="item.action" class="wb-button small" :disabled="busy || ['history','execution'].includes(item.action)&&!report.sample_codes.length" @click="collect(item.action)">{{ ['history','execution'].includes(item.action)?'补采下方5只样本':'同步此项所需数据' }}</button><small v-else>历史全市场快照不可通过当前快照接口补回</small></article></div>
<div class="wb-sample-strip"><strong>本轮补采范围</strong><span>{{ report.sample_names.length?report.sample_names.join('、'):'当前没有盘后候选，请先同步盘后数据。' }}</span><small>最多5只，用于快速核验；可在标的详情按需补采其他股票。</small></div></section>
<section class="wb-bottom-grid"><article class="wb-panel"><h3>使用前仍需补足</h3><p v-for="s in report.limits" :key="s" class="wb-checkline"><span>○</span>{{ s }}</p></article><article class="wb-panel"><h3>采集运行方式</h3><p class="wb-muted">{{ report.automation }}</p><p class="wb-muted">页面刷新只读本地；定时器与补采按钮调用量脉。单次股票数有限制，任务互斥，错误与旧日期都会明确显示。</p><button class="wb-button small" @click="$emit('open','data')">查看接口采集证据 ↗</button></article></section>
</template>
</details>
</template>
<script setup>
import {ref,watch} from 'vue'
import axios from 'axios'
import OperationsDashboard from './OperationsDashboard.vue'
const props=defineProps({day:String,busy:Boolean,mode:{type:String,default:'short'}});const emit=defineEmits(['open','collect'])
const report=ref(null),loading=ref(false),error=ref('');let sequence=0
const steps=[{title:'盘后备选',time:'收盘后',detail:'热点池与龙虎榜交集，形成下一交易日观察范围。',page:'research',phase:'review'},{title:'竞价确认',time:'约09:26后',detail:'核对前日热点与抢筹字段，不冒充9:25前信号。',page:'screen',phase:'pre'},{title:'早盘观察',time:'09:30—10:00',detail:'核验行情时效、分钟结构与价格限制。',page:'screen',phase:'live'},{title:'计划与复核',time:'T+1及以后',detail:'冻结观察依据，区分模拟结果与真实成交。',page:'plans'}]
const status=s=>({ready:'已满足本项检查',partial:'部分可用',missing:'缺失 / 待补'})[s]||s
function collect(stage){emit('collect',stage,['execution','history'].includes(stage)?report.value.sample_codes:[])}
async function load(){const id=++sequence;loading.value=true;error.value='';try{const r=await axios.get('/api/workbench/readiness',{params:{day:props.day}});if(id===sequence)report.value=r.data}catch{if(id===sequence)error.value='数据检查暂时无法读取，请重试。'}finally{if(id===sequence)loading.value=false}}
watch(()=>props.day,load,{immediate:true});watch(()=>props.busy,(v,old)=>{if(old&&!v)load()})
</script>
