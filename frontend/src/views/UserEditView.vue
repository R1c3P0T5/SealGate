<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { Alert, Button, Skeleton, useToast } from '@/lib'
import UserEditLayout from '@/layouts/UserEditLayout.vue'
import PermissionsEditor from '@/components/PermissionsEditor.vue'
import {
  getUserApiUsersUserIdGet,
  listPermissionsApiPermissionsGet,
  listRolesApiRolesGet,
  setPermissionsApiUsersUserIdPermissionsPut,
  setRoleApiUsersUserIdRolePut,
  userPermissionsApiUsersUserIdPermissionsGet,
} from '@/api/sdk.gen'
import type {
  PermissionOverride,
  PermissionResponse,
  RoleResponse,
  UserResponseFull,
} from '@/api/types.gen'

defineOptions({ name: 'UserEditView' })

const route = useRoute()
const toast = useToast()

const userId = computed(() => String(route.params.userId))

const user = ref<UserResponseFull | null>(null)
const roles = ref<RoleResponse[]>([])
const permissions = ref<PermissionResponse[]>([])

const loading = ref(false)
const loadError = ref<string | null>(null)
const saving = ref(false)

const initialRoleId = ref<string | null>(null)
const draftRoleId = ref<string | null>(null)
const initialOverrides = ref<PermissionOverride[]>([])
const draftOverrides = ref<PermissionOverride[]>([])

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  return fallback
}

async function loadAll() {
  loading.value = true
  loadError.value = null
  try {
    const [userRes, rolesRes, permsRes, permsForUserRes] = await Promise.all([
      getUserApiUsersUserIdGet({ path: { user_id: userId.value }, throwOnError: true }),
      listRolesApiRolesGet({ query: { limit: 50 }, throwOnError: true }),
      listPermissionsApiPermissionsGet({ throwOnError: true }),
      userPermissionsApiUsersUserIdPermissionsGet({
        path: { user_id: userId.value },
        throwOnError: true,
      }),
    ])
    user.value = userRes.data as UserResponseFull
    roles.value = rolesRes.data.roles
    permissions.value = permsRes.data.permissions
    initialOverrides.value = permsForUserRes.data.overrides.map((o) => ({ ...o }))
    draftOverrides.value = permsForUserRes.data.overrides.map((o) => ({ ...o }))

    const role = roles.value.find((r) => r.name === user.value?.role_name) ?? null
    initialRoleId.value = role?.id ?? null
    draftRoleId.value = role?.id ?? null
  } catch (err) {
    loadError.value = errorMessage(err, 'Could not load user.')
  } finally {
    loading.value = false
  }
}

const roleChanged = computed(() => draftRoleId.value !== initialRoleId.value)
const overridesChanged = computed(() => {
  const norm = (list: PermissionOverride[]) =>
    [...list]
      .map((o) => `${o.permission}:${o.granted ? '1' : '0'}`)
      .sort()
      .join('|')
  return norm(draftOverrides.value) !== norm(initialOverrides.value)
})
const dirty = computed(() => roleChanged.value || overridesChanged.value)

async function save() {
  if (!user.value || !dirty.value) return
  saving.value = true
  try {
    if (roleChanged.value && draftRoleId.value) {
      await setRoleApiUsersUserIdRolePut({
        path: { user_id: user.value.id },
        body: { role_id: draftRoleId.value },
        throwOnError: true,
      })
      const role = roles.value.find((r) => r.id === draftRoleId.value)
      if (role) user.value.role_name = role.name
    }
    if (overridesChanged.value) {
      await setPermissionsApiUsersUserIdPermissionsPut({
        path: { user_id: user.value.id },
        body: { overrides: draftOverrides.value },
        throwOnError: true,
      })
    }
    initialRoleId.value = draftRoleId.value
    initialOverrides.value = draftOverrides.value.map((o) => ({ ...o }))
    toast.show({ title: 'Saved' })
  } catch (err) {
    toast.show({ title: errorMessage(err, 'Save failed.') })
  } finally {
    saving.value = false
  }
}

function reset() {
  draftRoleId.value = initialRoleId.value
  draftOverrides.value = initialOverrides.value.map((o) => ({ ...o }))
}

onMounted(loadAll)
</script>

<template>
  <UserEditLayout>
    <template #title>{{ user?.username ?? '—' }}</template>
    <template #actions>
      <template v-if="user">
        <Button variant="ghost" size="sm" :disabled="!dirty || saving" @click="reset">
          Reset
        </Button>
        <Button variant="primary" size="sm" :loading="saving" :disabled="!dirty" @click="save">
          Save
        </Button>
      </template>
    </template>

    <Alert v-if="loadError" variant="err">{{ loadError }}</Alert>

    <div v-if="loading" class="grid gap-3">
      <Skeleton :height="32" />
      <Skeleton :height="180" />
    </div>

    <PermissionsEditor
      v-else-if="user"
      v-model:role-id="draftRoleId"
      v-model:overrides="draftOverrides"
      :roles="roles"
      :permissions="permissions"
      :disabled="saving"
    />
  </UserEditLayout>
</template>
