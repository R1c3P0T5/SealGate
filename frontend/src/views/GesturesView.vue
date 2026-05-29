<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { Button, Card, State, Table } from '@/lib'
import type { TableColumn } from '@/lib'
import GesturesLayout from '@/layouts/GesturesLayout.vue'
import { useGesturesStore } from '@/stores/gestures'

defineOptions({ name: 'GesturesView' })

const router = useRouter()
const store = useGesturesStore()

const columns: TableColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'steps', label: 'Steps' },
  { key: 'updated', label: 'Updated' },
]

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const rows = computed(() =>
  store.sequences.map((s) => ({
    id: s.id,
    name: s.name,
    steps: s.steps.length,
    updated: formatDate(s.updatedAt),
  })),
)

function open(id: string) {
  void router.push({ name: 'gestures-edit', params: { id } })
}

function newSequence() {
  void router.push({ name: 'gestures-new' })
}
</script>

<template>
  <GesturesLayout>
    <template #actions>
      <Button variant="primary" size="sm" @click="newSequence">+ New seal</Button>
    </template>

    <Card>
      <State
        v-if="store.sequences.length === 0"
        variant="empty"
        title="No seals yet"
        :center="true"
      />
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
