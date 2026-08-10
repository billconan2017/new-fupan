<template>
  <div>
    <div class="page-header">
      <div class="page-title">{{ icon }} {{ title }}</div>
      <div class="page-subtitle">{{ desc }}</div>
    </div>
    <div class="disabled-notice">
      <div class="icon">🚧</div>
      <div class="title">页面建设中</div>
      <div class="desc">{{ apiNeeded ? `等待后端接口: ${apiNeeded}` : '功能开发中，敬请期待' }}</div>
    </div>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
const icon = route.meta?.icon || '📄'
const title = route.meta?.title || '未命名'
const desc = route.meta?.desc || ''
const apiNeeded = route.meta?.api || ''
</script>
