<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { Alert, Button, Card, Skeleton, State, Table } from '@/lib'
import type { TableColumn } from '@/lib'
import GesturesLayout from '@/layouts/GesturesLayout.vue'
import { listJutsuEndpointApiJutsuGet } from '@/api/sdk.gen'
import type { JutsuResponse } from '@/api/types.gen'

defineOptions({ name: 'GesturesView' })

const router = useRouter()

const jutsu = ref<JutsuResponse[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const columns: TableColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'steps', label: 'Signs' },
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
  jutsu.value.map((j) => ({
    id: j.id,
    name: j.name,
    steps: j.signs.length,
    created: formatDate(j.created_at),
  })),
)

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await listJutsuEndpointApiJutsuGet({
      query: { limit: 100 },
      throwOnError: true,
    })
    jutsu.value = res.data.jutsu
  } catch (err) {
    error.value = errorMessage(err, 'Could not load seals.')
  } finally {
    loading.value = false
  }
}

function open(id: string) {
  void router.push({ name: 'gestures-edit', params: { id } })
}

function newSequence() {
  void router.push({ name: 'gestures-new' })
}

onMounted(load)
</script>

<template>
  <GesturesLayout>
    <template #actions>
      <Button variant="primary" size="sm" @click="newSequence">+ New seal</Button>
    </template>

    <Alert v-if="error" variant="err">{{ error }}</Alert>

    <Card>
      <div v-if="loading" class="grid gap-2">
        <Skeleton :height="36" />
        <Skeleton :height="36" />
        <Skeleton :height="36" />
      </div>
      <State v-else-if="jutsu.length === 0" variant="empty" title="No seals yet" :center="true" />
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
        <template #cell-steps="{ row }">
          <span class="font-mono text-xs text-text-lo">{{ row.steps }}</span>
        </template>
      </Table>
    </Card>
  </GesturesLayout>
</template>
