<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { Alert } from '@/lib'
import AccessLogsLayout from '@/layouts/AccessLogsLayout.vue'
import AccessLogsTable from '@/components/AccessLogsTable.vue'
import { listAccessLogsEndpointApiAccessLogsGet, listDoorsEndpointApiDoorsGet } from '@/api/sdk.gen'
import type { AccessLogResponse } from '@/api/types.gen'

defineOptions({ name: 'AccessLogsView' })

const PAGE_SIZE = 20

const logs = ref<AccessLogResponse[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref<string | null>(null)
const doorNameById = ref<Record<string, string>>({})

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  return fallback
}

async function loadDoors() {
  try {
    const response = await listDoorsEndpointApiDoorsGet({
      query: { limit: 100 },
      throwOnError: true,
    })
    doorNameById.value = Object.fromEntries(response.data.doors.map((door) => [door.id, door.name]))
  } catch {
    // Door lookup is best-effort; the table falls back to a truncated id.
  }
}

async function loadLogs() {
  loading.value = true
  error.value = null
  try {
    const response = await listAccessLogsEndpointApiAccessLogsGet({
      query: { skip: (page.value - 1) * PAGE_SIZE, limit: PAGE_SIZE },
      throwOnError: true,
    })
    logs.value = response.data.logs
    total.value = response.data.total
  } catch (err) {
    logs.value = []
    total.value = 0
    error.value = errorMessage(err, 'Could not load access logs.')
  } finally {
    loading.value = false
  }
}

function changePage(nextPage: number) {
  page.value = nextPage
  void loadLogs()
}

onMounted(async () => {
  await loadDoors()
  await loadLogs()
})
</script>

<template>
  <AccessLogsLayout>
    <Alert v-if="error" variant="err">{{ error }}</Alert>
    <AccessLogsTable
      :logs="logs"
      :door-name-by-id="doorNameById"
      :total="total"
      :page="page"
      :page-size="PAGE_SIZE"
      :loading="loading"
      @update:page="changePage"
    />
  </AccessLogsLayout>
</template>
