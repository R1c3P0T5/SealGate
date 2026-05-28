import './lib/theme.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { client } from './api/client.gen'
import { getCurrentUserInfoApiAuthMeGet } from './api/sdk.gen'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

const auth = useAuthStore()
auth.restore()

client.interceptors.response.use((response) => {
  if (response.status === 401 && auth.isAuthenticated) {
    auth.logout()
    router.push({ name: 'login' })
  }
  return response
})

app.mount('#app')

if (auth.isAuthenticated) {
  void getCurrentUserInfoApiAuthMeGet().catch(() => {})
}
