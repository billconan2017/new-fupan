<template><div class="wb-panel-title"><div class="wb-mode"><button :class="{active:tab==='old'}" @click="tab='old'">旧策略历史重建</button><button :class="{active:tab==='recent'}" @click="tab='recent'">新版近五日模拟</button><button :class="{active:tab==='paper'}" @click="tab='paper'">每日前瞻观察</button></div></div><LegacyReplay v-if="tab==='old'"/><RecentReplay v-else-if="tab==='recent'"/><PaperObserver v-else/></template>
<script setup>
import {ref} from 'vue'
import LegacyReplay from './LegacyReplay.vue'
import RecentReplay from './RecentReplay.vue'
import PaperObserver from './PaperObserver.vue'
const tab=ref('old')
</script>
