<template>
  <div class="review-card" :style="borderStyle">
    <div class="review-card-header">
      <span class="review-card-title">{{ title }}</span>
      <slot name="badge" />
    </div>
    <div class="review-card-body">
      <slot />
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  title: { type: String, required: true },
  accent: { type: String, default: '' },
})

const borderStyle = props.accent ? { borderLeft: `3px solid ${props.accent}` } : {}
</script>

<style scoped>
.review-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s;
}
.review-card:hover { box-shadow: var(--shadow-hover); }
.review-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light);
}
.review-card-title { font-size: 13px; font-weight: 600; }
</style>
