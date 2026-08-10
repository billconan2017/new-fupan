<template>
  <div class="kpi-card" :style="{ borderLeft: `3px solid ${color}` }">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value" :style="{ color }">{{ displayValue }}</div>
    <div v-if="suffix" class="kpi-suffix">{{ suffix }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { required: true },
  color: { type: String, default: 'var(--text-primary)' },
  suffix: { type: String, default: '' },
  format: { type: Function, default: null },
})

const displayValue = computed(() => {
  if (props.format) return props.format(props.value)
  if (props.value == null || props.value === '') return '-'
  return props.value
})
</script>

<style scoped>
.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  text-align: center;
  box-shadow: var(--shadow-card);
  transition: var(--transition);
}
.kpi-card:hover { box-shadow: var(--shadow-hover); transform: translateY(-1px); }
.kpi-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 4px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.kpi-value {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.3px;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.kpi-suffix {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
</style>
