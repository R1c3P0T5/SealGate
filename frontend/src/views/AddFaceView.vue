<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { Alert, Button, Input, Select, useToast } from '@/lib'
import type { SelectOption } from '@/lib'
import AddFaceLayout from '@/layouts/AddFaceLayout.vue'
import FaceSourcePicker from '@/components/FaceSourcePicker.vue'
import {
  addFaceFromImageApiUsersUserIdFacesFromImagePost,
  listUsersEndpointApiUsersGet,
} from '@/api/sdk.gen'
import type { UserResponseFull } from '@/api/types.gen'
import { useAuthStore } from '@/stores/auth'

defineOptions({ name: 'AddFaceView' })

const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const capturedFile = ref<File | null>(null)
const label = ref('')
const selectedUserId = ref(auth.user?.id ?? '')
const users = ref<UserResponseFull[]>([])
const loadingUsers = ref(false)
const submitting = ref(false)
const formError = ref<string | null>(null)

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
    formError.value = errorMessage(err, 'Could not load users.')
  } finally {
    loadingUsers.value = false
  }
}

async function submit() {
  if (!capturedFile.value || !selectedUserId.value) return

  submitting.value = true
  formError.value = null
  try {
    await addFaceFromImageApiUsersUserIdFacesFromImagePost({
      path: { user_id: selectedUserId.value },
      body: { image: capturedFile.value, label: label.value.trim() || undefined },
      throwOnError: true,
    })
    toast.show({ title: 'Face added', duration: 2300 })
    await router.push({ name: 'faces' })
  } catch (err) {
    formError.value = errorMessage(err, 'Could not add face.')
  } finally {
    submitting.value = false
  }
}

onMounted(loadUsers)
</script>

<template>
  <AddFaceLayout>
    <Alert v-if="formError" variant="err">{{ formError }}</Alert>

    <form class="grid gap-4" @submit.prevent="submit">
      <FaceSourcePicker v-model="capturedFile" :disabled="submitting" />

      <div class="grid gap-1">
        <label class="font-mono text-[11px] uppercase tracking-[0.06em] text-text-placeholder">
          Label
        </label>
        <Input
          v-model="label"
          maxlength="64"
          placeholder="Label (optional)"
          :disabled="submitting"
        />
      </div>

      <div v-if="isAdmin" class="grid gap-1">
        <label class="font-mono text-[11px] uppercase tracking-[0.06em] text-text-placeholder">
          Assign to user
        </label>
        <Select
          v-model="selectedUserId"
          :options="userOptions"
          :disabled="loadingUsers || submitting"
          placeholder="Assign to user"
        />
      </div>

      <Button
        type="submit"
        variant="primary"
        class="justify-self-start"
        :loading="submitting"
        :disabled="!capturedFile || submitting"
      >
        {{ submitting ? 'Submitting…' : 'Add Face' }}
      </Button>
    </form>
  </AddFaceLayout>
</template>
