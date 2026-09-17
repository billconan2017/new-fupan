<template><MarketChart :items="items" :identity="identity"/></template>
<script setup>
import MarketChart from './MarketChart.vue'
defineProps({items:{type:Array,default:()=>[]},identity:String})
</script>
