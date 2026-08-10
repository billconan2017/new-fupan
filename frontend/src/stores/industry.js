import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useIndustryStore = defineStore('industry', () => {
  const selectedIndustry = ref('')
  const industryList = ref([])

  function setIndustry(ind) { selectedIndustry.value = ind }
  function setList(list) { industryList.value = list }
  function clear() { selectedIndustry.value = '' }

  return { selectedIndustry, industryList, setIndustry, setList, clear }
})
