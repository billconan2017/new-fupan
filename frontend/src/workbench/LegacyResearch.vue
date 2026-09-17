<template>
 <section class="wb-panel"><h3>旧策略与博主观点</h3><p>{{ data?.note }}</p><p v-if="error" class="wb-notice error">{{ error }}</p>
 <div class="wb-plan-grid"><article v-for="r in data?.rules || []" :key="r.name" class="wb-plan"><h3>{{ r.name }}</h3><p>{{ r.logic }}</p><small>{{ r.source }}</small></article></div>
 <h3>观点链路更新到了哪里？</h3><p v-if="data?.views">本地整理表截至 <b>{{ data.views.trade_date }}</b>，入库更新 {{ data.views.updated_at }}。发布时间未核验，不作为当时已知信号。</p>
 <p v-if="data?.public_source">公开主页采样 {{ data.public_source.checked_at }} · {{ data.public_source.count }}篇目录记录；只核查元数据，未自动把观点加入选股分数。</p>
 <div class="wb-tags"><a v-for="r in data?.public_source?.articles?.slice(0,5) || []" :key="r.url" :href="r.url" target="_blank" rel="noopener noreferrer">{{ r.published_date }} · 原文</a></div>
 <p v-for="issue in data?.issues || []" :key="issue" class="wb-footnote">{{ issue }}</p>
 <h3>{{ day }} · 旧库保存的选股记录</h3><div class="wb-tags"><span v-for="r in data?.stage_counts || []" :key="r.stage">{{ r.stage }} · {{ r.count }}条</span></div>
 <p class="wb-footnote">以下是数据库记录，不是已核验的当时推荐或成交。需继续核对创建时间、信号时点和版本，不能直接据此报盈利。</p>
 <div class="wb-table-scroll"><table class="wb-table"><thead><tr><th>股票</th><th>阶段 / 状态</th><th>旧分数</th><th>记录时间</th></tr></thead><tbody><tr v-for="(r,i) in data?.selections || []" :key="i"><td>{{ r.stock_name }}<small>{{ r.stock_code }}</small></td><td>{{ r.stage }}<small>{{ r.status }}</small></td><td>{{ r.score ?? '缺失' }}</td><td>{{ r.selected_time }}<small>创建 {{ r.created_at }}</small></td></tr></tbody></table></div>
 </section>
</template>
<script setup>
import {ref,watch} from 'vue'
import axios from 'axios'
const props=defineProps({day:String});const data=ref(null),error=ref('');let seq=0
watch(()=>props.day,async day=>{const id=++seq;data.value=null;error.value='';try{const r=await axios.get('/api/workbench/legacy-research',{params:{day}});if(id===seq){data.value=r.data;error.value=r.data.error||''}}catch{if(id===seq)error.value='旧库读取失败'}},{immediate:true})
</script>
