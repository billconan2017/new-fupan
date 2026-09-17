<template>
 <div class="wb-intraday">
  <div class="wb-panel-title"><div><h3>当日走势 <small>5分钟采样</small></h3><span>蓝线：价格 · 虚线：昨收 · 下方：成交量</span></div><div class="wb-mode"><button :class="{active:early}" @click="early=true">10点前</button><button :class="{active:!early}" @click="early=false">全天</button></div></div>
  <div v-if="loading" class="wb-empty" role="status">正在读取分时数据…</div>
  <template v-else-if="points.length">
   <div class="wb-intraday-readout"><strong>{{ active.time }} · {{ active.c.toFixed(2) }}</strong><span :class="change>=0?'wb-up':'wb-down'">{{ change==null?'昨收缺失':(change>0?'+':'')+change.toFixed(2)+'%' }}</span><small>高 {{ active.h.toFixed(2) }} / 低 {{ active.l.toFixed(2) }} · {{ points.length }}个实际采样点</small></div>
   <div class="wb-intraday-canvas"><svg viewBox="0 0 720 355" role="img" aria-label="当日五分钟价格走势与成交量">
    <rect x="55" y="22" :width="x(30)-55" height="232" fill="#d7b5740a"/>
    <g v-for="i in 5" :key="i"><line x1="55" :y1="y(hi-(i-1)*span/4)" x2="652" :y2="y(hi-(i-1)*span/4)" stroke="#334055" stroke-dasharray="3 5"/><text x="5" :y="y(hi-(i-1)*span/4)+4" fill="#c2cddd" font-size="12">{{ (hi-(i-1)*span/4).toFixed(2) }}</text><text v-if="prior" x="660" :y="y(hi-(i-1)*span/4)+4" fill="#9faec3" font-size="11">{{ ((hi-(i-1)*span/4)/prior*100-100).toFixed(1) }}%</text></g>
    <line v-if="prior" x1="55" :y1="y(prior)" x2="652" :y2="y(prior)" stroke="#e5bd72" stroke-dasharray="6 4"/>
    <line :x1="x(10)" :x2="x(10)" y1="22" y2="254" stroke="#a7977355" stroke-dasharray="3 4"/><text :x="x(10)+3" y="18" fill="#d3b575" font-size="11">09:40</text>
    <line :x1="x(30)" :x2="x(30)" y1="22" y2="254" stroke="#a7977355" stroke-dasharray="3 4"/><text :x="x(30)-34" y="18" fill="#d3b575" font-size="11">10:00</text>
    <path :d="path" fill="none" stroke="#69c9ff" stroke-width="2.8" stroke-linejoin="round"/>
    <g v-for="p in points" :key="p.time"><circle :cx="x(p.minute)" :cy="y(p.c)" r="2.5" fill="#a6e2ff"/><rect v-if="p.v!=null && p.v>=0" :x="x(p.minute)-3" :y="310-p.v/maxVolume*40" width="6" :height="p.v/maxVolume*40" :fill="p.c>=p.o?'#e98185':'#59c9aa'"/><rect :x="x(p.minute)-5" y="22" width="10" height="290" fill="transparent" tabindex="0" :aria-label="p.time+' 价格 '+p.c" @mouseenter="hover=p.time" @focus="hover=p.time" @click="hover=p.time"/></g>
    <line :x1="x(active.minute)" :x2="x(active.minute)" y1="22" y2="313" stroke="#a0b2c0" stroke-dasharray="3 3"/><circle :cx="x(active.minute)" :cy="y(active.c)" r="4" fill="#ecfaff"/>
    <text x="55" y="340" fill="#a1b0c6" font-size="12">09:30</text><text v-if="!early" :x="x(120)-32" y="340" fill="#a1b0c6" font-size="12">11:30 / 13:00</text><text x="620" y="340" fill="#a1b0c6" font-size="12">{{ early?'10:00':'15:00' }}</text>
   </svg></div>
  </template>
  <div v-else class="wb-empty">暂无{{ early?'10点前':'当日' }}有效分时。点击下方“采集当日分时”，缺失时不生成模拟曲线。</div>
  <p class="wb-footnote">{{ chart?.note }} {{ chart?.scope==='early'?'当前仅有早盘缓存，可补采全天。':'' }}</p>
 </div>
</template>
<script setup>
import {ref,computed,watch} from 'vue'
const props=defineProps({chart:Object,loading:Boolean});const early=ref(true),hover=ref(null)
const minute=t=>{const [h,m]=t.split(':').map(Number);return h<12?h*60+m-570:h*60+m-780+120}
const points=computed(()=>(props.chart?.items||[]).map(p=>({...p,minute:minute(p.time)})).filter(p=>!early.value||p.minute<=30))
const prior=computed(()=>props.chart?.previous_close>0?props.chart.previous_close:null)
const active=computed(()=>points.value.find(p=>p.time===hover.value)||points.value.at(-1))
const change=computed(()=>prior.value&&active.value?(active.value.c/prior.value-1)*100:null)
const range=computed(()=>{const values=points.value.map(p=>p.c);if(prior.value)values.push(prior.value);const max=Math.max(...values),min=Math.min(...values),padding=Math.max((max-min)*.12,max*.001);return [min-padding,max+padding]})
const hi=computed(()=>range.value[1]),span=computed(()=>range.value[1]-range.value[0]||1)
const x=m=>55+m/(early.value?30:240)*597,y=p=>22+(hi.value-p)/span.value*232
const path=computed(()=>points.value.map((p,i)=>`${i && p.minute-points.value[i-1].minute===5?'L':'M'}${x(p.minute)},${y(p.c)}`).join(' '))
const maxVolume=computed(()=>Math.max(1,...points.value.map(p=>p.v||0)))
watch(()=>props.chart,()=>hover.value=null)
</script>
