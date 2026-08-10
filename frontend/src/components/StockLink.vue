<template>
  <span class="stock-link" @click="open" :title="`${code} ${name}`">
    <span class="stock-code">{{ code }}</span>
    <span v-if="showName" class="stock-name">{{ name }}</span>
  </span>
</template>

<script setup>
const props = defineProps({
  code: { type: String, required: true },
  name: { type: String, default: '' },
  showName: { type: Boolean, default: true },
})

function open() {
  // TODO: 打开个股详情弹窗
  console.log('Stock click:', props.code)
}
</script>

<style scoped>
.stock-link {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.stock-link:hover .stock-code { color: var(--color-main); text-decoration: underline; }
.stock-code { color: var(--color-main); font-weight: 500; font-variant-numeric: tabular-nums; }
.stock-name { color: var(--text-primary); font-size: 12px; }
</style>
