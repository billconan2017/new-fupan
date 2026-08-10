<template>
  <div class="empty-state">
    <div class="empty-icon">{{ icon }}</div>
    <div class="empty-title">{{ title }}</div>
    <div class="empty-desc">{{ desc }}</div>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: '📭' },
  title: { type: String, default: '暂无数据' },
  desc: { type: String, default: '' },
})
</script>

<style scoped>
.empty-state {
  text-align: center;
  padding: 50px 20px;
  color: var(--text-muted);
}
.empty-icon { font-size: 36px; margin-bottom: 10px; opacity: 0.5; }
.empty-title { font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; }
.empty-desc { font-size: 12px; }
</style>
