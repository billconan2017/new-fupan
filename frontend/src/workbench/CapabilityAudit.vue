<template>
 <section class="wb-panel"><h3>交易用途定向实测</h3><p>{{ audit?.scope || '尚未实测' }}</p><p class="wb-footnote">采样时间 {{ audit?.as_of }}。响应日期匹配仍不代表分钟连续、字段完整或可以成交。盘后未公布、空数据、参数错误与权限失败分别查看。</p>
 <div class="wb-inline"><select v-model="category" aria-label="筛选实测用途"><option value="">全部用途</option><option v-for="c in categories" :key="c">{{ c }}</option></select><select v-model="state" aria-label="筛选实测结果"><option value="">全部结果</option><option value="ready">返回数据</option><option value="empty">空数据</option><option value="error">请求失败</option></select></div>
 <div class="wb-table-scroll"><table class="wb-table"><thead><tr><th>用途 / 接口</th><th>日期 / 参数</th><th>结果</th><th>日期与实时性</th><th>字段</th></tr></thead><tbody><tr v-for="(r,i) in rows" :key="i"><td>{{ r.category }}<small>{{ r.api }}</small></td><td>{{ r.sample_date }}<small>{{ JSON.stringify(r.params) }}</small></td><td>{{ ({ready:'返回数据',empty:'空数据',error:'失败'})[r.status] }} · {{ r.rows_or_keys }}<small>{{ r.code }} / {{ r.elapsed_ms }}ms</small><small v-if="r.status==='error'">{{ r.reason }}</small></td><td>{{ ({contains_requested:'包含请求日期',other_dates:'只有其他日期',unverified:'源日期未确认'})[r.date_check] }}<small>{{ r.first_date }} — {{ r.last_date }}</small><small v-if="Object.keys(r.quote_states||{}).length">{{ JSON.stringify(r.quote_states) }}</small></td><td><details><summary>{{ r.fields.length }}字段</summary>{{ r.fields.join(', ') }}</details></td></tr></tbody></table></div>
 </section>
</template>
<script setup>
import {ref,computed} from 'vue'
const props=defineProps({audit:Object});const category=ref(''),state=ref('')
const categories=computed(()=>[...new Set((props.audit?.items||[]).map(r=>r.category))])
const rows=computed(()=>(props.audit?.items||[]).filter(r=>(!category.value||r.category===category.value)&&(!state.value||r.status===state.value)))
</script>
