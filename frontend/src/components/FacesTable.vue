<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Button, Card, Checkbox, Pagination, Skeleton, State, Table } from '@/lib'
import type { TableColumn } from '@/lib'
import type { FaceVectorMetadata } from '@/api/types.gen'

defineOptions({ name: 'FacesTable' })

const props = defineProps<{
  faces: FaceVectorMetadata[]
  total: number
  page: number
  pageSize: number
  loading: boolean
}>()

const emit = defineEmits<{
  bulkDelete: [faceIds: string[]]
  'update:page': [page: number]
}>()

const selected = ref<Set<string>>(new Set())
const selectMode = ref(false)

watch(
  () => props.faces,
  () => {
    selected.value = new Set()
  },
)

const allSelected = computed(
  () => props.faces.length > 0 && props.faces.every((face) => selected.value.has(face.id)),
)

function toggleAll() {
  const next = new Set(selected.value)
  if (allSelected.value) {
    for (const face of props.faces) next.delete(face.id)
  } else {
    for (const face of props.faces) next.add(face.id)
  }
  selected.value = next
}

function toggleOne(id: string) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

function requestBulkDelete() {
  if (selected.value.size === 0) return
  emit('bulkDelete', Array.from(selected.value))
}

function exitSelectMode() {
  selectMode.value = false
  selected.value = new Set()
}

const columns: TableColumn[] = [
  { key: 'select', label: '', class: 'w-12' },
  { key: 'id', label: 'ID' },
  { key: 'size', label: 'Size' },
  { key: 'created', label: 'Created' },
]

const rows = computed<Record<string, unknown>[]>(() =>
  props.faces.map((face) => {
    const d = new Date(face.created_at)
    const pad = (n: number) => String(n).padStart(2, '0')
    return {
      id: face.id.slice(0, 8),
      size: `${face.embedding_size}B`,
      created: '',
      createdDate: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
      createdTime: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
      faceId: face.id,
    }
  }),
)
</script>

<template>
  <Card>
    <div v-if="loading" class="grid gap-2">
      <Skeleton :height="36" />
      <Skeleton :height="36" />
      <Skeleton :height="36" />
    </div>
    <State v-else-if="faces.length === 0" variant="empty" title="No faces yet" :center="true" />
    <div v-else class="grid gap-3">
      <div class="flex items-center justify-between gap-2">
        <template v-if="selectMode">
          <Button variant="ghost" size="xs" @click="toggleAll">
            {{ allSelected ? 'Deselect all' : 'Select all' }}
          </Button>
          <div class="flex items-center gap-2">
            <span class="font-mono text-xs text-text-lo">
              {{ selected.size }} / {{ faces.length }}
            </span>
            <Button
              :disabled="selected.size === 0"
              variant="err"
              size="sm"
              @click="requestBulkDelete"
            >
              Delete
            </Button>
            <Button variant="ghost" size="sm" @click="exitSelectMode">Done</Button>
          </div>
        </template>
        <Button v-else variant="outline" size="sm" @click="selectMode = true">Select</Button>
      </div>
      <Table :columns="columns" :rows="rows" equal-cols>
        <template #cell-select="{ row }">
          <span :class="!selectMode && 'invisible'" :aria-hidden="!selectMode || undefined">
            <Checkbox
              :model-value="selected.has(String(row.faceId))"
              :tabindex="selectMode ? undefined : -1"
              @update:model-value="toggleOne(String(row.faceId))"
            />
          </span>
        </template>
        <template #cell-size="{ row }">
          <span class="whitespace-nowrap">{{ row.size }}</span>
        </template>
        <template #cell-created="{ row }">
          <span class="whitespace-nowrap">{{ row.createdDate }} {{ row.createdTime }}</span>
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
