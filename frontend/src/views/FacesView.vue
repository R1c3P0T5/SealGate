<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { Alert, Button, Dialog, Select, useToast } from '@/lib'
import type { SelectOption } from '@/lib'
import FacesLayout from '@/layouts/FacesLayout.vue'
import FacesTable from '@/components/FacesTable.vue'
import {
  deleteUserFaceVectorApiUsersUserIdFacesFaceIdDelete,
  listUserFaceVectorsApiUsersUserIdFacesGet,
  listUsersEndpointApiUsersGet,
} from '@/api/sdk.gen'
import type { FaceVectorMetadata, UserResponseFull } from '@/api/types.gen'
import { useAuthStore } from '@/stores/auth'

defineOptions({ name: 'FacesView' })

const FACE_LIMIT = 20

const auth = useAuthStore()
const toast = useToast()

const users = ref<UserResponseFull[]>([])
const selectedUserId = ref(auth.user?.id ?? '')
const faces = ref<FaceVectorMetadata[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const loadingUsers = ref(false)
const error = ref<string | null>(null)
const deleteDialogOpen = ref(false)
const deleteTarget = ref<FaceVectorMetadata | null>(null)
const deleting = ref(false)

const isAdmin = computed(() => auth.user?.role === 'admin')
const userOptions = computed<SelectOption[]>(() =>
  users.value.map((user) => ({
    value: user.id,
    label: `${user.username} (${user.role})`,
  })),
)

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  return fallback
}

async function loadUsers() {
  if (!isAdmin.value) return

  loadingUsers.value = true
  try {
    const response = await listUsersEndpointApiUsersGet({
      query: { limit: 100 },
      throwOnError: true,
    })
    users.value = response.data.users
    if (!selectedUserId.value) selectedUserId.value = auth.user?.id ?? users.value[0]?.id ?? ''
  } catch (err) {
    error.value = errorMessage(err, 'Could not load users.')
  } finally {
    loadingUsers.value = false
  }
}

async function loadFaces() {
  if (!selectedUserId.value) return

  loading.value = true
  error.value = null
  try {
    const response = await listUserFaceVectorsApiUsersUserIdFacesGet({
      path: { user_id: selectedUserId.value },
      query: { skip: (page.value - 1) * FACE_LIMIT, limit: FACE_LIMIT },
      throwOnError: true,
    })
    faces.value = response.data.faces
    total.value = response.data.total
  } catch (err) {
    faces.value = []
    total.value = 0
    error.value = errorMessage(err, 'Could not load faces.')
  } finally {
    loading.value = false
  }
}

function changeUser(userId: string) {
  selectedUserId.value = userId
  page.value = 1
  void loadFaces()
}

function changePage(nextPage: number) {
  page.value = nextPage
  void loadFaces()
}

function openDelete(faceId: string) {
  deleteTarget.value = faces.value.find((face) => face.id === faceId) ?? null
  deleteDialogOpen.value = deleteTarget.value !== null
}

async function confirmDelete() {
  if (!selectedUserId.value || !deleteTarget.value) return

  deleting.value = true
  error.value = null
  try {
    await deleteUserFaceVectorApiUsersUserIdFacesFaceIdDelete({
      path: { user_id: selectedUserId.value, face_id: deleteTarget.value.id },
      throwOnError: true,
    })
    toast.show({ title: 'Face deleted', duration: 2300 })
    deleteDialogOpen.value = false
    deleteTarget.value = null
    if (faces.value.length === 1 && page.value > 1) page.value -= 1
    await loadFaces()
  } catch (err) {
    error.value = errorMessage(err, 'Could not delete face.')
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await loadUsers()
  await loadFaces()
})
</script>

<template>
  <FacesLayout>
    <template #actions>
      <Select
        v-if="isAdmin"
        :model-value="selectedUserId"
        :options="userOptions"
        :disabled="loadingUsers || loading"
        placeholder="Manage user"
        class="min-w-52"
        @update:model-value="changeUser"
      />
      <RouterLink to="/faces/new">
        <Button variant="primary">Add Face</Button>
      </RouterLink>
    </template>

    <Alert v-if="error" variant="err">{{ error }}</Alert>

    <FacesTable
      :faces="faces"
      :total="total"
      :page="page"
      :page-size="FACE_LIMIT"
      :loading="loading"
      @delete="openDelete"
      @update:page="changePage"
    />

    <Dialog v-model:open="deleteDialogOpen" title="Delete face?">
      <p>
        This removes the selected face vector permanently. Recognition quality may change
        immediately.
      </p>
      <template #footer>
        <Button variant="ghost" size="sm" :disabled="deleting" @click="deleteDialogOpen = false">
          Cancel
        </Button>
        <Button variant="err" size="sm" :loading="deleting" @click="confirmDelete">Delete</Button>
      </template>
    </Dialog>
  </FacesLayout>
</template>
