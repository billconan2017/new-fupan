import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useFilterStore = defineStore('filter', () => {
  const tradeDate = ref(new Date().toISOString().slice(0, 10))
  const mainline = ref('')
  const riskLevel = ref('')

  function setDate(d) { tradeDate.value = d }
  function setMainline(m) { mainline.value = m }
  function setRiskLevel(r) { riskLevel.value = r }
  function reset() {
    mainline.value = ''
    riskLevel.value = ''
  }

  return { tradeDate, mainline, riskLevel, setDate, setMainline, setRiskLevel, reset }
})
