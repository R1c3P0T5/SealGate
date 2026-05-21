<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { Alert, Button, Card, RadioGroup, Skeleton, useToast } from '@/lib'
import {
  getUserApiUsersUserIdGet,
  listPermissionsApiPermissionsGet,
  listRolesApiRolesGet,
  rolePermissionsApiRolesRoleIdPermissionsGet,
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

const rolePermissions = ref<string[]>([])
const initialRoleId = ref<string | null>(null)
const draftRoleId = ref<string | null>(null)
const initialOverrides = ref<PermissionOverride[]>([])
const draftOverrides = ref<PermissionOverride[]>([])

const roleOptions = computed(() =>
  roles.value.map((r) => ({
    value: r.id,
    label: r.name,
    description: r.description ?? undefined,
  })),
)

const groupedPermissions = computed(() => {
  const groups = new Map<string, PermissionResponse[]>()
  for (const perm of permissions.value) {
    const scope = perm.name.split(':')[0] ?? 'other'
    const list = groups.get(scope) ?? []
    list.push(perm)
    groups.set(scope, list)
  }
  return Array.from(groups.entries()).map(([scope, items]) => ({ scope, items }))
})

function actionOf(perm: string): string {
  const idx = perm.indexOf(':')
  return idx === -1 ? perm : perm.slice(idx + 1)
}

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
    rolePermissions.value = permsForUserRes.data.role_permissions
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

const rolePermsCache = new Map<string, string[]>()

async function fetchRolePermissions(roleId: string): Promise<string[]> {
  const cached = rolePermsCache.get(roleId)
  if (cached) return cached
  const res = await rolePermissionsApiRolesRoleIdPermissionsGet({
    path: { role_id: roleId },
    throwOnError: true,
  })
  const names = res.data.permissions.map((p) => p.name)
  rolePermsCache.set(roleId, names)
  return names
}

watch(draftRoleId, async (newId, oldId) => {
  if (!newId || newId === oldId) return
  try {
    rolePermissions.value = await fetchRolePermissions(newId)
  } catch (err) {
    toast.show({ title: errorMessage(err, 'Could not load role permissions.') })
  }
})

function isEffective(perm: string): boolean {
  const o = draftOverrides.value.find((x) => x.permission === perm)
  if (o) return o.granted
  return rolePermissions.value.includes(perm)
}

function setEffective(perm: string, value: boolean) {
  const roleHas = rolePermissions.value.includes(perm)
  const next = draftOverrides.value.filter((x) => x.permission !== perm)
  if (value !== roleHas) {
    next.push({ permission: perm, granted: value })
  }
  draftOverrides.value = next
}

const hasDraftOverrides = computed(() => draftOverrides.value.length > 0)

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

function restoreDefaults() {
  draftOverrides.value = []
}

onMounted(loadAll)
</script>

<template>
  <div class="grid gap-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <RouterLink to="/user-management">
          <Button variant="ghost" size="sm">← Back</Button>
        </RouterLink>
        <h1 class="font-mono text-sm text-text-hi">
          {{ user?.username ?? '—' }}
        </h1>
      </div>
      <div v-if="user" class="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          :disabled="!hasDraftOverrides || saving"
          @click="restoreDefaults"
        >
          Restore defaults
        </Button>
        <Button variant="ghost" size="sm" :disabled="!dirty || saving" @click="reset">
          Reset
        </Button>
        <Button variant="primary" size="sm" :loading="saving" :disabled="!dirty" @click="save">
          Save
        </Button>
      </div>
    </div>

    <Alert v-if="loadError" variant="err">{{ loadError }}</Alert>

    <Card v-if="loading" class="self-start">
      <div class="grid gap-3">
        <Skeleton :height="32" />
        <Skeleton :height="180" />
      </div>
    </Card>

    <Card v-else-if="user" class="self-start">
      <div class="grid gap-5">
        <section class="grid gap-2">
          <h2 class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
            Role
          </h2>
          <RadioGroup
            v-if="draftRoleId !== null"
            v-model="draftRoleId"
            :options="roleOptions"
            orientation="horizontal"
          />
        </section>

        <section class="grid gap-4">
          <h2 class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
            Permissions
          </h2>

          <div v-for="group in groupedPermissions" :key="group.scope" class="grid gap-2">
            <span class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
              {{ group.scope }}
            </span>
            <div class="grid gap-1 overflow-hidden rounded-[2px] border border-border">
              <div
                v-for="perm in group.items"
                :key="perm.name"
                class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b border-border-soft px-3 py-2 last:border-b-0"
              >
                <div class="min-w-0">
                  <p class="truncate font-mono text-sm text-text-hi">{{ actionOf(perm.name) }}</p>
                  <p v-if="perm.description" class="truncate text-xs text-text-placeholder">
                    {{ perm.description }}
                  </p>
                </div>
                <div
                  class="flex items-center justify-self-end overflow-hidden rounded-[2px] border border-border"
                >
                  <button
                    type="button"
                    class="min-w-9 px-2 py-1 font-mono text-xs transition-colors"
                    :class="
                      isEffective(perm.name)
                        ? 'bg-ok/20 text-ok'
                        : 'bg-bg text-text-placeholder hover:text-ok'
                    "
                    @click="setEffective(perm.name, true)"
                  >
                    ✓
                  </button>
                  <button
                    type="button"
                    class="min-w-9 border-l border-border px-2 py-1 font-mono text-xs transition-colors"
                    :class="
                      !isEffective(perm.name)
                        ? 'bg-err/20 text-err'
                        : 'bg-bg text-text-placeholder hover:text-err'
                    "
                    @click="setEffective(perm.name, false)"
                  >
                    ✗
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </Card>
  </div>
</template>
