<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Alert, Button, Card, Input } from '@/lib'
import { registerApiAuthRegisterPost } from '@/api/sdk.gen'

defineOptions({ name: 'RegisterView' })

const router = useRouter()

type FormState = {
  username: string
  full_name: string
  email: string
  password: string
  confirm: string
}
type FormErrors = Partial<Record<keyof FormState, string>>

const PASSWORD_MIN = 12
const USERNAME_MIN = 3
const USERNAME_MAX = 32

const form = ref<FormState>({
  username: '',
  full_name: '',
  email: '',
  password: '',
  confirm: '',
})
const errors = ref<FormErrors>({})
const submitting = ref(false)
const generalError = ref<string | null>(null)

function validate(): FormErrors {
  const e: FormErrors = {}
  const { username, full_name, email, password, confirm } = form.value
  if (!username || username.length < USERNAME_MIN)
    e.username = `At least ${USERNAME_MIN} characters.`
  else if (username.length > USERNAME_MAX) e.username = `At most ${USERNAME_MAX} characters.`
  else if (!/^[a-zA-Z0-9._-]+$/.test(username)) e.username = 'Letters, digits, . _ - only.'
  if (!full_name.trim()) e.full_name = 'Required.'
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = 'Enter a valid email.'
  if (!password || password.length < PASSWORD_MIN)
    e.password = `Minimum ${PASSWORD_MIN} characters.`
  if (password && confirm !== password) e.confirm = 'Passwords do not match.'
  return e
}

async function submit() {
  generalError.value = null
  errors.value = validate()
  if (Object.keys(errors.value).length) return

  submitting.value = true
  try {
    await registerApiAuthRegisterPost({
      body: {
        username: form.value.username,
        password: form.value.password,
        full_name: form.value.full_name.trim(),
        email: form.value.email.trim(),
      },
      throwOnError: true,
    })
    await router.push({
      name: 'login',
      state: {
        prefillUsername: form.value.username,
        prefillPassword: form.value.password,
      },
    })
  } catch {
    generalError.value = 'Registration failed. Please check your details and try again.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Card class="w-full max-w-[440px]">
    <div class="flex flex-col gap-5 p-6">
      <div class="flex flex-col gap-0.5">
        <h1 class="font-mono text-sm uppercase tracking-[0.08em] text-text-hi">FaceGuard</h1>
        <p class="text-[12px] text-text-lo">Access Control System</p>
      </div>

      <Alert v-if="generalError" variant="err">{{ generalError }}</Alert>

      <form class="flex flex-col gap-3" @submit.prevent="submit">
        <Input
          v-model="form.username"
          placeholder="Username"
          autocomplete="username"
          :invalid="!!errors.username"
          :error="errors.username"
          :disabled="submitting"
        />
        <Input
          v-model="form.full_name"
          placeholder="Full name"
          autocomplete="name"
          :invalid="!!errors.full_name"
          :error="errors.full_name"
          :disabled="submitting"
        />
        <Input
          v-model="form.email"
          type="email"
          placeholder="Email"
          autocomplete="email"
          :invalid="!!errors.email"
          :error="errors.email"
          :disabled="submitting"
        />
        <Input
          v-model="form.password"
          type="password"
          placeholder="Password"
          autocomplete="new-password"
          :invalid="!!errors.password"
          :error="errors.password"
          :hint="`Minimum ${PASSWORD_MIN} characters`"
          :disabled="submitting"
        />
        <Input
          v-model="form.confirm"
          type="password"
          placeholder="Confirm password"
          autocomplete="new-password"
          :invalid="!!errors.confirm"
          :error="errors.confirm"
          :disabled="submitting"
        />
        <Button
          type="submit"
          variant="primary"
          class="w-full"
          :loading="submitting"
          :disabled="submitting"
        >
          {{ submitting ? 'Submitting…' : 'Submit request' }}
        </Button>
      </form>

      <p
        class="text-center font-mono text-[11px] uppercase tracking-[0.06em] text-text-placeholder"
      >
        Already have an account?
        <RouterLink to="/login" class="text-ac underline underline-offset-2">Sign in</RouterLink>
      </p>
    </div>
  </Card>
</template>
