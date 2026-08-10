<template>
  <div class="review-table-wrap" :style="{ maxHeight: height }">
    <table class="data-table">
      <thead>
        <tr><th v-for="col in columns" :key="col.key" :class="{ num: col.num }">{{ col.label }}</th></tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in data" :key="i">
          <td v-for="col in columns" :key="col.key" :class="{ num: col.num, up: col.colorField && row[col.colorField] > 0, down: col.colorField && row[col.colorField] < 0 }">
            <slot :name="col.key" :row="row" :value="row[col.key]">
              {{ col.format ? col.format(row[col.key]) : row[col.key] }}
            </slot>
          </td>
        </tr>
        <tr v-if="data.length === 0">
          <td :colspan="columns.length" style="text-align:center;padding:30px;color:var(--text-muted)">
            {{ emptyText }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({
  columns: { type: Array, required: true },
  data: { type: Array, default: () => [] },
  height: { type: String, default: 'auto' },
  emptyText: { type: String, default: '暂无数据' },
})
</script>

<style scoped>
.review-table-wrap {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: auto;
}
</style>
