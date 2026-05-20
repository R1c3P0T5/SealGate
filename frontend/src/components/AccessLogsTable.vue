<script setup lang="ts">
import { computed } from 'vue'

import { Badge, Card, Pagination, Skeleton, State, Table } from '@/lib'
import type { TableColumn } from '@/lib'
import type { AccessLogResponse } from '@/api/types.gen'

defineOptions({ name: 'AccessLogsTable' })

const props = defineProps<{
  logs: AccessLogResponse[]
  doorNameById: Record<string, string>
  total: number
  page: number
  pageSize: number
  loading: boolean
}>()

const emit = defineEmits<{
  'update:page': [page: number]
}>()

const columns: TableColumn[] = [
  { key: 'time', label: 'Time' },
  { key: 'door', label: 'Door' },
  { key: 'user', label: 'User' },
  { key: 'confidence', label: 'Confidence' },
  { key: 'status', label: 'Status' },
]

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function formatTimestamp(iso: string) {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function formatConfidence(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(2)}%`
}

function doorLabel(doorId: string) {
  return props.doorNameById[doorId] ?? doorId.slice(0, 8)
}

const rows = computed(() =>
  props.logs.map((log) => ({
    logId: log.id,
    time: formatTimestamp(log.timestamp),
    door: doorLabel(log.door_id),
    user: log.username ?? '—',
    confidence: formatConfidence(log.confidence),
    opened: log.door_opened,
  })),
)
</script>

<template>
  <Card>
    <div v-if="loading" class="grid gap-2">
      <Skeleton :height="36" />
      <Skeleton :height="36" />
      <Skeleton :height="36" />
    </div>
    <State
      v-else-if="logs.length === 0"
      variant="empty"
      title="No access logs yet"
      :center="true"
    />
    <div v-else class="grid gap-3">
      <Table :columns="columns" :rows="rows">
        <template #cell-time="{ row }">
          <span class="whitespace-nowrap">{{ row.time }}</span>
        </template>
        <template #cell-status="{ row }">
          <Badge :variant="row.opened ? 'ok' : 'err'">
            {{ row.opened ? 'Opened' : 'Denied' }}
          </Badge>
        </template>
      </Table>
      <Pagination
        v-if="total > pageSize"
        :page="page"
        :page-size="pageSize"
        :total="total"
        @update:page="(p) => emit('update:page', p)"
      />
    </div>
  </Card>
</template>
