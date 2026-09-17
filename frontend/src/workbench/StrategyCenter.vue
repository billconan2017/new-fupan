<template><section class="wb-panel"><div class="wb-panel-title"><h3>当前选股规则</h3><span>实际运行与历史研究分开标记</span></div><div class="wb-plan-grid"><article v-for="r in rules" :key="r.name" class="wb-plan"><div class="wb-tags"><span>{{r.state}}</span><span>{{r.time}}</span></div><h3>{{r.name}}</h3><p>{{r.logic}}</p><small>{{r.limit}}</small></article></div></section><LegacyResearch :day="day"/></template>
<script setup>
import LegacyResearch from './LegacyResearch.vue'
defineProps({day:String})
const rules=[{name:'竞价抢筹排序',state:'新版正在使用',time:'约09:26后',logic:'抢筹成交额40分 + 抢筹涨幅30分 + 抢筹委托额30分。重点最多5只，同一行业最多2只。',limit:'缺字段不评分；不是9:25前信号，分数不是胜率。'},{name:'盘中活跃强势',state:'新版正在使用',time:'09:30—10:00观察',logic:'成交额30分 + 量比25分 + 涨幅25分 + 站上开盘价20分。',limit:'超过10点转持仓跟踪；尚未完整接入旧系统的承接与修复确认。'},{name:'盘后热点 → 次日竞价',state:'自动纸面观察',time:'盘后冻结 / 次晨确认',logic:'涨停、强势、龙虎榜交集，冻结前日候选；次晨按固定规则生成观察，随后检查T+1/2/3模拟结果。',limit:'首次建立需真实盘后冻结；不补造历史推荐，不产生订单。'},{name:'旧承接 / 修复规则',state:'本次已做历史重建',time:'09:31 / 09:40',logic:'按旧代码阈值检验开盘承接、均价线、下探幅度及冲高回落；修复型允许重新确认。',limit:'缺均价不以最新价替代。历史种子与成交条件仍未完整核验，暂不自动替换实时评分。'}]
</script>
