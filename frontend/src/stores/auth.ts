import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { loginApiAuthLoginPost } from '../api/sdk.gen'
import { client } from '../api/client.gen'
import type { UserResponse } from '../api/types.gen'

const STORAGE_KEY = 'faceguard-auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(null)
  const user = ref<UserResponse | null>(null)

  const isAuthenticated = computed(() => token.value !== null)

  function _persist() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: token.value, user: user.value }))
  }

  function _syncClient() {
    client.setConfig({
      headers: token.value ? { Authorization: `Bearer ${token.value}` } : {},
    })
  }

  async function login(username: string, password: string) {
    const res = await loginApiAuthLoginPost({
      body: { username, password },
      throwOnError: true,
    })
    token.value = res.data.access_token
    user.value = res.data.user
    _persist()
    _syncClient()
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(STORAGE_KEY)
    _syncClient()
  }

  function setUser(updated: UserResponse) {
    user.value = updated
    _persist()
  }

  function restore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const saved = JSON.parse(raw) as { token?: string; user?: UserResponse }
      if (!saved?.token) return
      token.value = saved.token
      user.value = saved.user ?? null
      _syncClient()
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  return { token, user, isAuthenticated, login, logout, setUser, restore }
})
