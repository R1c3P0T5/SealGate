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
const bulkDeleteDialogOpen = ref(false)
const bulkDeleteTarget = ref<string[]>([])
const bulkDeleting = ref(false)

const isAdmin = computed(() => auth.user?.role_name === 'admin')
const userOptions = computed<SelectOption[]>(() =>
  users.value.map((user) => ({
    value: user.id,
    label: `${user.username} (${user.role_name})`,
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

function openBulkDelete(faceIds: string[]) {
  if (faceIds.length === 0) return
  bulkDeleteTarget.value = faceIds
  bulkDeleteDialogOpen.value = true
}

async function confirmBulkDelete() {
  if (!selectedUserId.value || bulkDeleteTarget.value.length === 0) return

  const userId = selectedUserId.value
  const ids = bulkDeleteTarget.value
  bulkDeleting.value = true
  error.value = null
  try {
    const results = await Promise.allSettled(
      ids.map((faceId) =>
        deleteUserFaceVectorApiUsersUserIdFacesFaceIdDelete({
          path: { user_id: userId, face_id: faceId },
          throwOnError: true,
        }),
      ),
    )
    const failed = results.filter((r) => r.status === 'rejected').length
    const succeeded = ids.length - failed

    toast.show({
      title: failed
        ? `Deleted ${succeeded}, ${failed} failed`
        : `Deleted ${succeeded} face${succeeded === 1 ? '' : 's'}`,
      duration: 2600,
    })

    bulkDeleteDialogOpen.value = false
    bulkDeleteTarget.value = []
    if (faces.value.length === succeeded && page.value > 1) page.value -= 1
    await loadFaces()
  } catch (err) {
    error.value = errorMessage(err, 'Could not delete faces.')
  } finally {
    bulkDeleting.value = false
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
        class="w-full md:w-auto md:min-w-52"
        @update:model-value="changeUser"
      />
      <RouterLink to="/faces/new" class="col-start-2 md:col-start-auto">
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
      @bulk-delete="openBulkDelete"
      @update:page="changePage"
    />

    <Dialog v-model:open="bulkDeleteDialogOpen" title="Delete selected faces?">
      <p>
        This removes {{ bulkDeleteTarget.length }} face vector(s) permanently. Recognition quality
        may change immediately.
      </p>
      <template #footer>
        <Button
          variant="ghost"
          size="sm"
          :disabled="bulkDeleting"
          @click="bulkDeleteDialogOpen = false"
        >
          Cancel
        </Button>
        <Button variant="err" size="sm" :loading="bulkDeleting" @click="confirmBulkDelete">
          Delete
        </Button>
      </template>
    </Dialog>
  </FacesLayout>
</template>
