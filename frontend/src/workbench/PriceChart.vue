<template>
  <div class="price-chart">
    <svg v-if="bars.length" viewBox="0 0 720 210" role="img" aria-label="前复权日K线">
      <g v-for="i in 4" :key="i"><line x1="12" :y1="i*40" x2="660" :y2="i*40" stroke="#263144" stroke-dasharray="3 5"/><text x="666" :y="i*40+4" fill="#8793aa" font-size="10">{{ (hi-i*40/180*span).toFixed(2) }}</text></g>
      <g v-for="(b,i) in bars" :key="b.t" :stroke="b.c>=b.o ? '#f07879' : '#50c7a6'" :fill="b.c>=b.o ? '#f07879' : '#50c7a6'">
        <title>{{ b.t }} 开 {{ b.o }} 高 {{ b.h }} 低 {{ b.l }} 收 {{ b.c }}</title>
        <line :x1="x(i)" :x2="x(i)" :y1="y(b.h)" :y2="y(b.l)" />
        <rect :x="x(i)-width/2" :y="Math.min(y(b.o),y(b.c))" :width="width" :height="Math.max(1,Math.abs(y(b.o)-y(b.c)))" stroke="none"/>
      </g>
      <text x="12" y="205" fill="#8793aa" font-size="10">{{ bars[0]?.t }}</text><text x="570" y="205" fill="#8793aa" font-size="10">{{ bars.at(-1)?.t }}</text>
    </svg>
    <div v-else class="wb-empty">日线尚未准备。点击“补齐日线”后查看。</div>
  </div>
</template>
<script setup>
import {computed} from 'vue'
const props=defineProps({items:{type:Array,default:()=>[]}})
const bars=computed(()=>props.items.filter(b=>['o','h','l','c'].every(k=>Number.isFinite(Number(b[k])) && b[k]!=null)).slice(-60).map(b=>({...b,o:Number(b.o),h:Number(b.h),l:Number(b.l),c:Number(b.c)})))
const hi=computed(()=>Math.max(...bars.value.map(b=>Number(b.h)))*1.015)
const lo=computed(()=>Math.min(...bars.value.map(b=>Number(b.l)))*.985)
const span=computed(()=>hi.value-lo.value || 1)
const width=computed(()=>Math.max(2,Math.min(8,640/Math.max(bars.value.length,1)*.65)))
const x=i=>12+(i+.5)*640/Math.max(bars.value.length,1)
const y=v=>(hi.value-v)/span.value*180
</script>
