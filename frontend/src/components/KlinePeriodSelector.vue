<template>
  <div class="period-selector">
    <button
      v-for="p in periods"
      :key="p.value"
      :class="['period-btn', { active: modelValue === p.value }]"
      @click="$emit('update:modelValue', p.value)"
    >
      {{ p.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: 'day' },
  periods: {
    type: Array,
    default: () => [
      { value: 'day', label: '日K' },
      { value: '60', label: '60分' },
      { value: '30', label: '30分' },
      { value: '15', label: '15分' },
      { value: '10', label: '10分' },
      { value: '5', label: '5分' },
      { value: '1', label: '1分' },
    ],
  },
})

defineEmits(['update:modelValue'])
</script>

<style scoped>
.period-selector {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.period-btn {
  padding: 4px 12px;
  border: 1px solid #333;
  border-radius: 4px;
  background: transparent;
  color: #999;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}
.period-btn:hover {
  border-color: #448aff;
  color: #448aff;
}
.period-btn.active {
  background: #448aff;
  border-color: #448aff;
  color: #fff;
}
</style>
