<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { Alert, Badge, Button, Card, Skeleton, State, Table } from '@/lib'
import type { TableColumn } from '@/lib'
import UserManagementLayout from '@/layouts/UserManagementLayout.vue'
import { listUsersEndpointApiUsersGet } from '@/api/sdk.gen'
import type { UserResponseFull } from '@/api/types.gen'
import { useAuthStore } from '@/stores/auth'

defineOptions({ name: 'UserManagementView' })

const router = useRouter()
const auth = useAuthStore()

const isAdmin = computed(() => auth.user?.role_name === 'admin')

const users = ref<UserResponseFull[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const columns: TableColumn[] = [
  { key: 'username', label: 'Username' },
  { key: 'full_name', label: 'Full Name' },
  { key: 'email', label: 'Email', hideBelow: 'md' },
  { key: 'role', label: 'Role' },
  { key: 'active', label: 'Active' },
  { key: 'created', label: 'Created', hideBelow: 'md' },
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

function newUser() {
  void router.push({ name: 'user-management-new' })
}

onMounted(loadUsers)
</script>

<template>
  <UserManagementLayout>
    <template #actions>
      <Button v-if="isAdmin" variant="primary" size="sm" @click="newUser">+ New user</Button>
    </template>

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
  </UserManagementLayout>
</template>
