<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { Alert, Button, Input, Skeleton, useToast } from '@/lib'
import UserCreateLayout from '@/layouts/UserCreateLayout.vue'
import PermissionsEditor from '@/components/PermissionsEditor.vue'
import {
  listPermissionsApiPermissionsGet,
  listRolesApiRolesGet,
  registerApiAuthRegisterPost,
  setPermissionsApiUsersUserIdPermissionsPut,
  setRoleApiUsersUserIdRolePut,
} from '@/api/sdk.gen'
import type { PermissionOverride, PermissionResponse, RoleResponse } from '@/api/types.gen'

defineOptions({ name: 'UserCreateView' })

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

const router = useRouter()
const toast = useToast()

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

const roles = ref<RoleResponse[]>([])
const permissions = ref<PermissionResponse[]>([])
const loading = ref(false)
const loadError = ref<string | null>(null)

const defaultRoleId = ref<string | null>(null)
const draftRoleId = ref<string | null>(null)
const draftOverrides = ref<PermissionOverride[]>([])
const showAccess = ref(false)

const defaultRoleName = computed(
  () => roles.value.find((r) => r.id === defaultRoleId.value)?.name ?? 'user',
)

function toggleAccess() {
  showAccess.value = !showAccess.value
  if (!showAccess.value) {
    draftRoleId.value = defaultRoleId.value
    draftOverrides.value = []
  }
}

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  return fallback
}

async function loadMeta() {
  loading.value = true
  loadError.value = null
  try {
    const [rolesRes, permsRes] = await Promise.all([
      listRolesApiRolesGet({ query: { limit: 50 }, throwOnError: true }),
      listPermissionsApiPermissionsGet({ throwOnError: true }),
    ])
    roles.value = rolesRes.data.roles
    permissions.value = permsRes.data.permissions
    const defaultRole = roles.value.find((r) => r.name === 'user') ?? roles.value[0] ?? null
    defaultRoleId.value = defaultRole?.id ?? null
    draftRoleId.value = defaultRoleId.value
  } catch (err) {
    loadError.value = errorMessage(err, 'Could not load roles and permissions.')
  } finally {
    loading.value = false
  }
}

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
  if (!draftRoleId.value) return

  submitting.value = true
  let newUserId: string | null = null
  try {
    const res = await registerApiAuthRegisterPost({
      body: {
        username: form.value.username,
        password: form.value.password,
        full_name: form.value.full_name.trim(),
        email: form.value.email.trim(),
      },
      throwOnError: true,
    })
    newUserId = res.data.id
    const selectedRole = roles.value.find((r) => r.id === draftRoleId.value)
    if (selectedRole && selectedRole.name !== res.data.role_name) {
      await setRoleApiUsersUserIdRolePut({
        path: { user_id: newUserId },
        body: { role_id: draftRoleId.value },
        throwOnError: true,
      })
    }
    if (draftOverrides.value.length > 0) {
      await setPermissionsApiUsersUserIdPermissionsPut({
        path: { user_id: newUserId },
        body: { overrides: draftOverrides.value },
        throwOnError: true,
      })
    }
    toast.show({ title: 'User created' })
    void router.push({ name: 'user-management' })
  } catch (err) {
    if (newUserId) {
      toast.show({
        title: 'User created but access settings failed; finish on the user detail page.',
      })
      void router.push({ name: 'user-management-edit', params: { userId: newUserId } })
    } else {
      generalError.value = errorMessage(err, 'Could not create user.')
    }
  } finally {
    submitting.value = false
  }
}

function cancel() {
  void router.push({ name: 'user-management' })
}

onMounted(loadMeta)
</script>

<template>
  <UserCreateLayout>
    <Alert v-if="loadError" variant="err">{{ loadError }}</Alert>

    <div v-if="loading" class="grid gap-3">
      <Skeleton :height="32" />
      <Skeleton :height="180" />
    </div>

    <div v-else class="grid gap-5">
      <Alert v-if="generalError" variant="err">{{ generalError }}</Alert>

      <section class="grid gap-3">
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
      </section>

      <div class="flex flex-wrap items-center gap-2 border-t border-border-soft pt-3">
        <Button variant="ghost" size="xs" :disabled="submitting" @click="toggleAccess">
          {{ showAccess ? '− Hide access settings' : '+ Configure access' }}
        </Button>
        <span v-if="!showAccess" class="text-xs text-text-placeholder">
          Will be created with default <code class="text-text-lo">{{ defaultRoleName }}</code> role.
        </span>
      </div>

      <PermissionsEditor
        v-if="showAccess"
        v-model:role-id="draftRoleId"
        v-model:overrides="draftOverrides"
        :roles="roles"
        :permissions="permissions"
        :disabled="submitting"
      />

      <div class="flex justify-end gap-2 pt-2" :class="{ '-mt-3': !showAccess }">
        <Button variant="ghost" size="sm" :disabled="submitting" @click="cancel">Cancel</Button>
        <Button
          variant="primary"
          size="sm"
          :loading="submitting"
          :disabled="submitting"
          @click="submit"
        >
          Create
        </Button>
      </div>
    </div>
  </UserCreateLayout>
</template>
