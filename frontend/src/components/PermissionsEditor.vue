<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Button, RadioGroup } from '@/lib'
import { rolePermissionsApiRolesRoleIdPermissionsGet } from '@/api/sdk.gen'
import type { PermissionOverride, PermissionResponse, RoleResponse } from '@/api/types.gen'

defineOptions({ name: 'PermissionsEditor' })

interface Props {
  roleId: string | null
  overrides: PermissionOverride[]
  roles: RoleResponse[]
  permissions: PermissionResponse[]
  disabled?: boolean
}
const props = defineProps<Props>()

const emit = defineEmits<{
  'update:roleId': [value: string]
  'update:overrides': [value: PermissionOverride[]]
}>()

const rolePermissions = ref<string[]>([])
const rolePermsCache = new Map<string, string[]>()

const roleOptions = computed(() =>
  props.roles.map((r) => ({
    value: r.id,
    label: r.name,
    description: r.description ?? undefined,
  })),
)

const groupedPermissions = computed(() => {
  const groups = new Map<string, PermissionResponse[]>()
  for (const perm of props.permissions) {
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

watch(
  () => props.roleId,
  async (newId) => {
    if (!newId) {
      rolePermissions.value = []
      return
    }
    try {
      rolePermissions.value = await fetchRolePermissions(newId)
    } catch {
      rolePermissions.value = []
    }
  },
  { immediate: true },
)

function isEffective(perm: string): boolean {
  const o = props.overrides.find((x) => x.permission === perm)
  if (o) return o.granted
  return rolePermissions.value.includes(perm)
}

function setEffective(perm: string, value: boolean) {
  const roleHas = rolePermissions.value.includes(perm)
  const next = props.overrides.filter((x) => x.permission !== perm)
  if (value !== roleHas) {
    next.push({ permission: perm, granted: value })
  }
  emit('update:overrides', next)
}

const hasOverrides = computed(() => props.overrides.length > 0)

function restoreDefaults() {
  emit('update:overrides', [])
}
</script>

<template>
  <div class="grid gap-5">
    <section class="grid gap-2">
      <h2 class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">Role</h2>
      <RadioGroup
        v-if="roleId !== null"
        :model-value="roleId"
        :options="roleOptions"
        orientation="horizontal"
        :disabled="disabled"
        @update:model-value="(v) => emit('update:roleId', String(v))"
      />
    </section>

    <section class="grid gap-4">
      <div class="flex items-center justify-between gap-2">
        <h2 class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
          Permissions
        </h2>
        <Button
          variant="ghost"
          size="xs"
          :disabled="!hasOverrides || disabled"
          @click="restoreDefaults"
        >
          Restore defaults
        </Button>
      </div>

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
                :disabled="disabled"
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
                :disabled="disabled"
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
</template>
