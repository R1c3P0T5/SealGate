<script setup lang="ts">
import { computed } from 'vue'

import { Button, Card, Pagination, Skeleton, State, Table } from '@/lib'
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
  delete: [faceId: string]
  'update:page': [page: number]
}>()

const columns: TableColumn[] = [
  { key: 'id', label: 'ID' },
  { key: 'label', label: 'Label' },
  { key: 'size', label: 'Size' },
  { key: 'created', label: 'Created' },
  { key: 'actions', label: 'Actions' },
]

const rows = computed<Record<string, unknown>[]>(() =>
  props.faces.map((face) => ({
    id: face.id.slice(0, 8),
    label: face.label ?? '—',
    size: `${face.embedding_size} B`,
    created: new Date(face.created_at).toLocaleString(),
    faceId: face.id,
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
    <State v-else-if="faces.length === 0" variant="empty" title="No faces yet" :center="true" />
    <div v-else class="grid gap-3">
      <Table :columns="columns" :rows="rows">
        <template #cell-actions="{ row }">
          <Button variant="ghost" size="xs" @click="emit('delete', String(row.faceId))">
            Delete
          </Button>
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
