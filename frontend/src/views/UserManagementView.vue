<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { Alert, Badge, Card, Skeleton, State, Table } from '@/lib'
import type { TableColumn } from '@/lib'
import { listUsersEndpointApiUsersGet } from '@/api/sdk.gen'
import type { UserResponseFull } from '@/api/types.gen'

defineOptions({ name: 'UserManagementView' })

const router = useRouter()

const users = ref<UserResponseFull[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const columns: TableColumn[] = [
  { key: 'username', label: 'Username' },
  { key: 'full_name', label: 'Full Name' },
  { key: 'email', label: 'Email' },
  { key: 'role', label: 'Role' },
  { key: 'active', label: 'Active' },
  { key: 'created', label: 'Created' },
]

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  return fallback
}

const rows = computed(() =>
  users.value.map((u) => ({
    id: u.id,
    username: u.username,
    full_name: u.full_name,
    email: u.email ?? '—',
    role: u.role_name,
    active: u.is_active,
    created: formatDate(u.created_at),
  })),
)

async function loadUsers() {
  loading.value = true
  error.value = null
  try {
    const res = await listUsersEndpointApiUsersGet({
      query: { limit: 100 },
      throwOnError: true,
    })
    users.value = res.data.users
  } catch (err) {
    error.value = errorMessage(err, 'Could not load users.')
  } finally {
    loading.value = false
  }
}

function open(userId: string) {
  void router.push({ name: 'user-management-edit', params: { userId } })
}

onMounted(loadUsers)
</script>

<template>
  <div class="grid gap-4">
    <h1 class="font-mono text-sm uppercase tracking-[0.08em] text-text-hi">User Management</h1>

    <Alert v-if="error" variant="err">{{ error }}</Alert>

    <Card>
      <div v-if="loading" class="grid gap-2">
        <Skeleton :height="36" />
        <Skeleton :height="36" />
        <Skeleton :height="36" />
      </div>
      <State v-else-if="users.length === 0" variant="empty" title="No users yet" :center="true" />
      <Table
        v-else
        :columns="columns"
        :rows="rows"
        clickable-rows
        @row-click="(row) => open(String(row.id))"
      >
        <template #cell-username="{ row }">
          <span class="font-mono text-sm text-text-hi">{{ row.username }}</span>
        </template>
        <template #cell-role="{ row }">
          <Badge :variant="row.role === 'admin' ? 'info' : 'dim'" class="min-w-16 justify-center">
            {{ row.role }}
          </Badge>
        </template>
        <template #cell-active="{ row }">
          <Badge :variant="row.active ? 'ok' : 'err'" class="min-w-12 justify-center">
            {{ row.active ? 'yes' : 'no' }}
          </Badge>
        </template>
      </Table>
    </Card>
  </div>
</template>
