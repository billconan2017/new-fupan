import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMarketStore = defineStore('market', () => {
  const emotion = ref(null)
  const reviewReport = ref(null)
  const lastFetch = ref(null)

  function setEmotion(data) {
    emotion.value = data
    lastFetch.value = Date.now()
  }
  function setReviewReport(data) {
    reviewReport.value = data
    lastFetch.value = Date.now()
  }
  function isStale(maxAgeMs = 300000) {
    return !lastFetch.value || Date.now() - lastFetch.value > maxAgeMs
  }

  return { emotion, reviewReport, lastFetch, setEmotion, setReviewReport, isStale }
})
