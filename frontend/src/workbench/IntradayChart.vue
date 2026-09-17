<template><div class="wb-intraday"><div class="wb-panel-title"><h3>当日走势 <small>5分钟采样</small></h3><span>价格 · 昨收 · 成交量</span></div><div v-if="loading" class="wb-empty" role="status">正在读取分时数据…</div><MarketChart v-show="!loading" :items="chart?.items||[]" intraday :previous-close="chart?.previous_close" :identity="identity" :early="!compact"/><details class="wb-chart-note"><summary>数据口径</summary><p class="wb-footnote">{{chart?.note}} 缺失采样保留断点，5分钟K线不能替代逐笔分时。</p></details></div></template>
<script setup>
import MarketChart from './MarketChart.vue'
defineProps({chart:Object,loading:Boolean,compact:Boolean,identity:String})
</script>
