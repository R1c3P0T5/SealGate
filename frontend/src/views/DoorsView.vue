<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { Alert, Badge, Button, Card, Skeleton, State, Table } from '@/lib'
import type { TableColumn } from '@/lib'
import DoorsLayout from '@/layouts/DoorsLayout.vue'
import { listDoorsEndpointApiDoorsGet } from '@/api/sdk.gen'
import type { DoorResponse } from '@/api/types.gen'

defineOptions({ name: 'DoorsView' })

const router = useRouter()

const doors = ref<DoorResponse[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const columns: TableColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'mqtt_id', label: 'MQTT ID' },
  { key: 'location', label: 'Location' },
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
  doors.value.map((d) => ({
    id: d.id,
    name: d.name,
    mqtt_id: d.mqtt_id ?? '—',
    location: d.location ?? '—',
    active: d.is_active,
    created: formatDate(d.created_at),
  })),
)

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await listDoorsEndpointApiDoorsGet({
      query: { limit: 100 },
      throwOnError: true,
    })
    doors.value = res.data.doors
  } catch (err) {
    error.value = errorMessage(err, 'Could not load doors.')
  } finally {
    loading.value = false
  }
}

function open(doorId: string) {
  void router.push({ name: 'doors-edit', params: { doorId } })
}

function newDoor() {
  void router.push({ name: 'doors-new' })
}

onMounted(load)
</script>

<template>
  <DoorsLayout>
    <template #actions>
      <Button variant="primary" size="sm" @click="newDoor">+ New door</Button>
    </template>

    <Alert v-if="error" variant="err">{{ error }}</Alert>

    <Card>
      <div v-if="loading" class="grid gap-2">
        <Skeleton :height="36" />
        <Skeleton :height="36" />
        <Skeleton :height="36" />
      </div>
      <State v-else-if="doors.length === 0" variant="empty" title="No doors yet" :center="true" />
      <Table
        v-else
        :columns="columns"
        :rows="rows"
        clickable-rows
        @row-click="(row) => open(String(row.id))"
      >
        <template #cell-name="{ row }">
          <span class="font-mono text-sm text-text-hi">{{ row.name }}</span>
        </template>
        <template #cell-mqtt_id="{ row }">
          <span class="font-mono text-xs text-text-lo">{{ row.mqtt_id }}</span>
        </template>
        <template #cell-active="{ row }">
          <Badge :variant="row.active ? 'ok' : 'err'" class="min-w-12 justify-center">
            {{ row.active ? 'yes' : 'no' }}
          </Badge>
        </template>
      </Table>
    </Card>
  </DoorsLayout>
</template>
