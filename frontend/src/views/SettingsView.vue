<script setup lang="ts">
import { computed, ref } from 'vue'

import { Alert, Button, Input, useToast } from '@/lib'
import SettingsLayout from '@/layouts/SettingsLayout.vue'
import {
  changeUserPasswordApiUsersUserIdPasswordPut,
  updateUserProfileApiUsersUserIdPut,
} from '@/api/sdk.gen'
import { useAuthStore } from '@/stores/auth'

defineOptions({ name: 'SettingsView' })

type FormErrors = Partial<Record<'full_name' | 'email', string>>
type PasswordErrors = Partial<Record<'current' | 'next' | 'confirm', string>>

const FULL_NAME_MAX = 255
const PASSWORD_MIN = 12

const auth = useAuthStore()
const toast = useToast()

const initial = computed(() => ({
  full_name: auth.user?.full_name ?? '',
  email: auth.user?.email ?? '',
}))

const form = ref({
  full_name: initial.value.full_name,
  email: initial.value.email,
})
const errors = ref<FormErrors>({})
const saving = ref(false)
const generalError = ref<string | null>(null)

const dirty = computed(
  () =>
    form.value.full_name !== initial.value.full_name || form.value.email !== initial.value.email,
)

const passwordForm = ref({
  current: '',
  next: '',
  confirm: '',
})
const passwordErrors = ref<PasswordErrors>({})
const changingPassword = ref(false)
const passwordError = ref<string | null>(null)

const passwordDirty = computed(
  () => !!passwordForm.value.current || !!passwordForm.value.next || !!passwordForm.value.confirm,
)

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  return fallback
}

function validate(): FormErrors {
  const e: FormErrors = {}
  const fullName = form.value.full_name.trim()
  const email = form.value.email.trim()
  if (!fullName) e.full_name = 'Required.'
  else if (fullName.length > FULL_NAME_MAX) e.full_name = `At most ${FULL_NAME_MAX} characters.`
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = 'Enter a valid email.'
  return e
}

async function save() {
  if (!auth.user || !dirty.value) return
  generalError.value = null
  errors.value = validate()
  if (Object.keys(errors.value).length) return

  saving.value = true
  try {
    const res = await updateUserProfileApiUsersUserIdPut({
      path: { user_id: auth.user.id },
      body: {
        full_name: form.value.full_name.trim(),
        email: form.value.email.trim(),
      },
      throwOnError: true,
    })
    auth.setUser(res.data)
    form.value.full_name = res.data.full_name
    form.value.email = res.data.email ?? ''
    toast.show({ title: 'Saved' })
  } catch (err) {
    generalError.value = errorMessage(err, 'Save failed.')
  } finally {
    saving.value = false
  }
}

function reset() {
  form.value.full_name = initial.value.full_name
  form.value.email = initial.value.email
  errors.value = {}
  generalError.value = null
}

function validatePassword(): PasswordErrors {
  const e: PasswordErrors = {}
  const { current, next, confirm } = passwordForm.value
  if (!current) e.current = 'Required.'
  if (!next || next.length < PASSWORD_MIN) e.next = `Minimum ${PASSWORD_MIN} characters.`
  else if (next === current) e.next = 'New password must differ from current.'
  if (confirm !== next) e.confirm = 'Passwords do not match.'
  return e
}

async function changePassword() {
  if (!auth.user || !passwordDirty.value) return
  passwordError.value = null
  passwordErrors.value = validatePassword()
  if (Object.keys(passwordErrors.value).length) return

  changingPassword.value = true
  try {
    await changeUserPasswordApiUsersUserIdPasswordPut({
      path: { user_id: auth.user.id },
      body: {
        current_password: passwordForm.value.current,
        new_password: passwordForm.value.next,
      },
      throwOnError: true,
    })
    passwordForm.value = { current: '', next: '', confirm: '' }
    passwordErrors.value = {}
    toast.show({ title: 'Password updated' })
  } catch (err) {
    passwordError.value = errorMessage(err, 'Could not update password.')
  } finally {
    changingPassword.value = false
  }
}
</script>

<template>
  <SettingsLayout>
    <template #actions>
      <Button variant="ghost" size="sm" :disabled="!dirty || saving" @click="reset"> Reset </Button>
      <Button variant="primary" size="sm" :loading="saving" :disabled="!dirty" @click="save">
        Save
      </Button>
    </template>

    <div class="grid gap-6">
      <div class="grid gap-4">
        <Alert v-if="generalError" variant="err">{{ generalError }}</Alert>

        <div class="grid gap-1.5">
          <label class="font-mono text-xs text-text-placeholder">Username</label>
          <Input
            :model-value="auth.user?.username ?? ''"
            autocomplete="username"
            disabled
            hint="Username cannot be changed."
          />
        </div>
        <div class="grid gap-1.5">
          <label class="font-mono text-xs text-text-placeholder">Full name</label>
          <Input
            v-model="form.full_name"
            autocomplete="name"
            :invalid="!!errors.full_name"
            :error="errors.full_name"
            :disabled="saving"
          />
        </div>
        <div class="grid gap-1.5">
          <label class="font-mono text-xs text-text-placeholder">Email</label>
          <Input
            v-model="form.email"
            type="email"
            autocomplete="email"
            :invalid="!!errors.email"
            :error="errors.email"
            :disabled="saving"
          />
        </div>
      </div>

      <form class="grid gap-4 border-t border-border pt-6" @submit.prevent="changePassword">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="grid gap-0.5">
            <h2 class="font-mono text-sm text-text-hi">Password</h2>
            <p class="text-xs text-text-lo">Update the password for your account.</p>
          </div>
          <Button
            type="submit"
            variant="primary"
            size="sm"
            :loading="changingPassword"
            :disabled="!passwordDirty"
          >
            Update password
          </Button>
        </div>

        <Alert v-if="passwordError" variant="err">{{ passwordError }}</Alert>

        <div class="grid gap-1.5">
          <label class="font-mono text-xs text-text-placeholder">Current password</label>
          <Input
            v-model="passwordForm.current"
            type="password"
            autocomplete="current-password"
            :invalid="!!passwordErrors.current"
            :error="passwordErrors.current"
            :disabled="changingPassword"
          />
        </div>
        <div class="grid gap-1.5">
          <label class="font-mono text-xs text-text-placeholder">New password</label>
          <Input
            v-model="passwordForm.next"
            type="password"
            autocomplete="new-password"
            :invalid="!!passwordErrors.next"
            :error="passwordErrors.next"
            :hint="`Minimum ${PASSWORD_MIN} characters`"
            :disabled="changingPassword"
          />
        </div>
        <div class="grid gap-1.5">
          <label class="font-mono text-xs text-text-placeholder">Confirm new password</label>
          <Input
            v-model="passwordForm.confirm"
            type="password"
            autocomplete="new-password"
            :invalid="!!passwordErrors.confirm"
            :error="passwordErrors.confirm"
            :disabled="changingPassword"
          />
        </div>
      </form>
    </div>
  </SettingsLayout>
</template>
