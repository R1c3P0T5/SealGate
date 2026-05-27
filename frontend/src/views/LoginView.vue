<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Alert, Button, Card, Input } from '@/lib'
import { useAuthStore } from '@/stores/auth'

defineOptions({ name: 'LoginView' })

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref<string | null>(null)

onMounted(() => {
  const state = window.history.state as {
    prefillUsername?: string
    prefillPassword?: string
  } | null
  if (state?.prefillUsername) username.value = String(state.prefillUsername)
  if (state?.prefillPassword) password.value = String(state.prefillPassword)
  if (state && ('prefillUsername' in state || 'prefillPassword' in state)) {
    const cleaned = { ...state } as Record<string, unknown>
    delete cleaned.prefillUsername
    delete cleaned.prefillPassword
    window.history.replaceState(cleaned, '')
  }
})

async function submit() {
  errorMsg.value = null
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push({ name: 'dashboard' })
  } catch {
    errorMsg.value = 'Invalid username or password.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Card class="w-full max-w-[380px]">
    <div class="flex flex-col gap-5 p-6">
      <div class="flex flex-col gap-0.5">
        <h1 class="font-mono text-sm uppercase tracking-[0.08em] text-text-hi">FaceGuard</h1>
        <p class="text-[12px] text-text-lo">Access Control System</p>
      </div>

      <Alert v-if="errorMsg" variant="err">{{ errorMsg }}</Alert>

      <form class="flex flex-col gap-3" @submit.prevent="submit">
        <Input
          v-model="username"
          placeholder="Username"
          autocomplete="username"
          :disabled="loading"
        />
        <Input
          v-model="password"
          type="password"
          placeholder="Password"
          autocomplete="current-password"
          :disabled="loading"
        />
        <Button type="submit" variant="primary" :disabled="loading" class="w-full">
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </Button>
      </form>

      <p
        class="text-center font-mono text-[11px] uppercase tracking-[0.06em] text-text-placeholder"
      >
        No account yet?
        <RouterLink to="/register" class="text-ac underline underline-offset-2">Sign up</RouterLink>
      </p>
    </div>
  </Card>
</template>
