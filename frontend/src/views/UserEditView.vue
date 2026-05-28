<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { Alert, Button, Skeleton, Switch, useToast } from '@/lib'
import UserEditLayout from '@/layouts/UserEditLayout.vue'
import PermissionsEditor from '@/components/PermissionsEditor.vue'
import {
  getUserApiUsersUserIdGet,
  listPermissionsApiPermissionsGet,
  listRolesApiRolesGet,
  setActiveApiUsersUserIdActivePut,
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
const initialActive = ref(false)
const draftActive = ref(false)

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
    initialActive.value = user.value?.is_active ?? false
    draftActive.value = initialActive.value
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
const activeChanged = computed(() => draftActive.value !== initialActive.value)
const dirty = computed(() => roleChanged.value || overridesChanged.value || activeChanged.value)

async function save() {
  if (!user.value || !dirty.value) return
  saving.value = true
  try {
    if (activeChanged.value) {
      await setActiveApiUsersUserIdActivePut({
        path: { user_id: user.value.id },
        body: { is_active: draftActive.value },
        throwOnError: true,
      })
      user.value.is_active = draftActive.value
    }
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
    initialActive.value = draftActive.value
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
  draftActive.value = initialActive.value
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

    <div v-else-if="user" class="grid gap-5">
      <section class="grid gap-2">
        <h2 class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
          Account
        </h2>
        <Switch
          v-model="draftActive"
          label="Active"
          description="Inactive accounts cannot log in."
          :disabled="saving"
        />
      </section>

      <PermissionsEditor
        v-model:role-id="draftRoleId"
        v-model:overrides="draftOverrides"
        :roles="roles"
        :permissions="permissions"
        :disabled="saving"
      />
    </div>
  </UserEditLayout>
</template>
