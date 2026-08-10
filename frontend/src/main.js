import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './8899_design_tokens.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
