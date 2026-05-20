<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  addFaceFromImageApiUsersUserIdFacesFromImagePost,
  deleteUserFaceVectorApiUsersUserIdFacesFaceIdDelete,
  listUsersEndpointApiUsersGet,
} from '@/api/sdk.gen'
import type { UserResponseFull } from '@/api/types.gen'
import FaceSourcePicker from '@/components/FaceSourcePicker.vue'
import AddFaceLayout from '@/layouts/AddFaceLayout.vue'
import { Alert, Button, Progress, Select, useToast } from '@/lib'
import type { SelectOption } from '@/lib'
import { useAuthStore } from '@/stores/auth'

defineOptions({ name: 'AddFaceView' })

const CAPTURE_COUNT = 10
const CAPTURE_INTERVAL_MS = 700
const EXPOSURE_SETTLE_MS = 1000
const COUNTDOWN_SECONDS = 3
const MAX_ATTEMPTS = 30

type CapturePhase =
  | 'waiting'
  | 'settling'
  | 'countdown'
  | 'capturing'
  | 'cancelling'
  | 'complete'
  | 'error'

type FaceSourcePickerPublic = {
  startCamera: () => Promise<void>
  stopCamera: () => void
  captureFrame: (index: number) => Promise<File>
}

type FailureBucket = {
  reason: string
  count: number
}

type CaptureSummary = {
  succeeded: number
  failed: number
  failures: FailureBucket[]
}

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()

const sourcePicker = ref<FaceSourcePickerPublic | null>(null)
const users = ref<UserResponseFull[]>([])
const selectedUserId = ref(auth.user?.id ?? '')
const loadingUsers = ref(false)
const usersLoaded = ref(false)
const cameraReady = ref(false)
const autoStarted = ref(false)
const phase = ref<CapturePhase>('waiting')
const countdown = ref<number | null>(null)
const successCount = ref(0)
const attemptCount = ref(0)
const lastFailure = ref<string | null>(null)
const error = ref<string | null>(null)
const summary = ref<CaptureSummary | null>(null)
const createdFaceIds = ref<string[]>([])

let activeRunId = 0
let unmounted = false
let captureBatchPromise: Promise<void> | null = null

const isAdmin = computed(() => auth.user?.role_name === 'admin')
const userOptions = computed<SelectOption[]>(() =>
  users.value.map((user) => ({
    value: user.id,
    label: `${user.username} (${user.role_name})`,
  })),
)
const isRunning = computed(() =>
  ['settling', 'countdown', 'capturing', 'cancelling'].includes(phase.value),
)
const canCancel = computed(
  () => ['complete', 'error'].includes(phase.value) && createdFaceIds.value.length > 0,
)
const progressValue = computed(() => successCount.value)
const showProgress = computed(() => phase.value === 'capturing')
const showActions = computed(() => phase.value === 'complete' || phase.value === 'error')
const showCamera = computed(() =>
  ['waiting', 'settling', 'countdown', 'capturing'].includes(phase.value),
)
const statusText = computed(() => {
  if (loadingUsers.value) return 'Loading users...'

  switch (phase.value) {
    case 'settling':
      return 'Camera ready. Adjusting exposure...'
    case 'countdown':
      return `Capture starts in ${countdown.value ?? COUNTDOWN_SECONDS}`
    case 'capturing':
      return `Captured ${successCount.value}/${CAPTURE_COUNT}`
    case 'cancelling':
      return createdFaceIds.value.length
        ? 'Cancelling... Removing uploaded photos.'
        : 'Cancelling...'
    case 'complete':
      return 'Capture complete'
    case 'error':
      return error.value ? 'Capture stopped' : 'Camera unavailable'
    default:
      return cameraReady.value ? 'Preparing capture...' : 'Opening camera...'
  }
})

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  if (value instanceof Error) return value.message
  return fallback
}

function isLimitReached(value: unknown) {
  if (!value || typeof value !== 'object' || !('detail' in value)) return false
  const detail = (value as { detail?: unknown }).detail
  return typeof detail === 'string' && detail.toLowerCase().includes('limit reached')
}

function delay(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function isActiveRun(runId: number) {
  return !unmounted && activeRunId === runId
}

function resetBatchState() {
  autoStarted.value = false
  cameraReady.value = false
  phase.value = 'waiting'
  countdown.value = null
  successCount.value = 0
  attemptCount.value = 0
  lastFailure.value = null
  error.value = null
  summary.value = null
  createdFaceIds.value = []
}

function bucketFailures(reasons: string[]) {
  const counts = new Map<string, number>()
  for (const reason of reasons) counts.set(reason, (counts.get(reason) ?? 0) + 1)

  return Array.from(counts.entries())
    .map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason))
}

function stopWithError(message: string) {
  error.value = message
  phase.value = 'error'
  autoStarted.value = true
  sourcePicker.value?.stopCamera()
}

async function loadUsers() {
  if (!isAdmin.value) {
    usersLoaded.value = true
    if (!selectedUserId.value) error.value = 'No signed-in user found.'
    void maybeStartCapture()
    return
  }

  loadingUsers.value = true
  error.value = null
  try {
    const response = await listUsersEndpointApiUsersGet({
      query: { limit: 100 },
      throwOnError: true,
    })
    users.value = response.data.users
    if (!selectedUserId.value) selectedUserId.value = auth.user?.id ?? users.value[0]?.id ?? ''
    if (!users.value.length) error.value = 'No users available to register faces.'
  } catch (err) {
    error.value = errorMessage(err, 'Could not load users.')
  } finally {
    loadingUsers.value = false
    usersLoaded.value = true
    void maybeStartCapture()
  }
}

async function maybeStartCapture() {
  if (autoStarted.value || !cameraReady.value || loadingUsers.value || !usersLoaded.value) return
  if (error.value) {
    stopWithError(error.value)
    return
  }
  if (isAdmin.value && userOptions.value.length === 0) {
    stopWithError('No users available to register faces.')
    return
  }
  if (!selectedUserId.value) {
    stopWithError('No user selected for face registration.')
    return
  }

  autoStarted.value = true
  captureBatchPromise = runCaptureBatch(selectedUserId.value)
  try {
    await captureBatchPromise
  } finally {
    captureBatchPromise = null
  }
}

async function deleteUploadedFaces() {
  const userId = selectedUserId.value
  const idsToDelete = [...createdFaceIds.value]
  createdFaceIds.value = []

  if (idsToDelete.length === 0 || !userId) return 0

  await Promise.allSettled(
    idsToDelete.map((faceId) =>
      deleteUserFaceVectorApiUsersUserIdFacesFaceIdDelete({
        path: { user_id: userId, face_id: faceId },
        throwOnError: true,
      }),
    ),
  )
  return idsToDelete.length
}

async function cancel() {
  if (!canCancel.value) return

  phase.value = 'cancelling'
  sourcePicker.value?.stopCamera()
  activeRunId += 1

  const pending = captureBatchPromise
  if (pending) await pending.catch(() => undefined)

  const deletedCount = await deleteUploadedFaces()

  successCount.value = 0
  attemptCount.value = 0
  lastFailure.value = null
  summary.value = null
  error.value = deletedCount
    ? `Capture cancelled. Removed ${deletedCount} uploaded photo(s).`
    : 'Capture cancelled.'
  phase.value = 'error'

  toast.show({ title: 'Capture cancelled', duration: 2300 })
}

async function runCaptureBatch(userId: string) {
  const runId = ++activeRunId

  try {
    phase.value = 'settling'
    await delay(EXPOSURE_SETTLE_MS)
    if (!isActiveRun(runId)) return

    phase.value = 'countdown'
    for (let remaining = COUNTDOWN_SECONDS; remaining > 0; remaining -= 1) {
      countdown.value = remaining
      await delay(1000)
      if (!isActiveRun(runId)) return
    }
    countdown.value = null

    phase.value = 'capturing'
    const failureReasons: string[] = []
    let limitReached = false
    while (successCount.value < CAPTURE_COUNT && attemptCount.value < MAX_ATTEMPTS) {
      const picker = sourcePicker.value
      if (!picker) throw new Error('Camera is not ready.')

      attemptCount.value += 1
      let file: File
      try {
        file = await picker.captureFrame(attemptCount.value)
      } catch (err) {
        const reason = errorMessage(err, 'Frame capture failed.')
        failureReasons.push(reason)
        lastFailure.value = reason
        await delay(CAPTURE_INTERVAL_MS)
        if (!isActiveRun(runId)) return
        continue
      }

      try {
        const response = await addFaceFromImageApiUsersUserIdFacesFromImagePost({
          path: { user_id: userId },
          body: { image: file },
          throwOnError: true,
        })
        if (response.data?.id) createdFaceIds.value.push(response.data.id)
        if (isActiveRun(runId)) {
          successCount.value += 1
          lastFailure.value = null
        }
      } catch (err) {
        const reason = errorMessage(err, 'Upload failed.')
        failureReasons.push(reason)
        lastFailure.value = reason
        if (isLimitReached(err)) {
          limitReached = true
          break
        }
      }

      if (!isActiveRun(runId)) return
      if (successCount.value < CAPTURE_COUNT && attemptCount.value < MAX_ATTEMPTS) {
        await delay(CAPTURE_INTERVAL_MS)
        if (!isActiveRun(runId)) return
      }
    }

    sourcePicker.value?.stopCamera()

    const failedCount = attemptCount.value - successCount.value
    const nextSummary = {
      succeeded: successCount.value,
      failed: failedCount,
      failures: bucketFailures(failureReasons),
    }
    summary.value = nextSummary

    if (limitReached) {
      error.value = `${lastFailure.value ?? 'Face vector limit reached.'} Captured ${successCount.value}/${CAPTURE_COUNT}.`
      phase.value = 'error'
      toast.show({
        title: 'Face limit reached',
        message: error.value,
        duration: 3200,
      })
    } else if (successCount.value < CAPTURE_COUNT) {
      error.value = `Captured ${successCount.value}/${CAPTURE_COUNT} after ${MAX_ATTEMPTS} attempts. Try again.`
      phase.value = 'error'
      toast.show({
        title: 'Face capture stopped',
        message: error.value,
        duration: 3200,
      })
    } else {
      phase.value = 'complete'
      toast.show({
        title: 'Faces registered',
        message: failedCount
          ? `${CAPTURE_COUNT} succeeded, ${failedCount} retries.`
          : `${CAPTURE_COUNT} succeeded.`,
        duration: 3200,
      })
    }
  } catch (err) {
    if (!isActiveRun(runId)) return
    error.value = errorMessage(err, 'Could not register faces.')
    phase.value = 'error'
    toast.show({
      title: 'Face capture failed',
      message: error.value,
      duration: 3200,
    })
  } finally {
    if (isActiveRun(runId)) sourcePicker.value?.stopCamera()
  }
}

function handleCameraReady() {
  cameraReady.value = true
  void maybeStartCapture()
}

function handleCameraError(message: string) {
  error.value = message
  phase.value = 'error'
  autoStarted.value = true
}

function changeUser(userId: string) {
  if (isRunning.value) return
  selectedUserId.value = userId
}

async function captureAgain() {
  if (isRunning.value) return

  if (createdFaceIds.value.length > 0) {
    phase.value = 'cancelling'
    await deleteUploadedFaces()
  }

  activeRunId += 1
  resetBatchState()
  if (isAdmin.value && users.value.length === 0) {
    usersLoaded.value = false
    void loadUsers()
  }
}

function done() {
  void router.push('/faces')
}

onMounted(() => {
  void loadUsers()
})

onUnmounted(() => {
  unmounted = true
  activeRunId += 1
  sourcePicker.value?.stopCamera()
})
</script>

<template>
  <AddFaceLayout>
    <div class="grid gap-4">
      <div v-if="isAdmin" class="flex justify-end">
        <Select
          :model-value="selectedUserId"
          :options="userOptions"
          :disabled="loadingUsers || isRunning"
          placeholder="Register user"
          class="w-full md:w-72"
          @update:model-value="changeUser"
        />
      </div>

      <Alert v-if="error" variant="err">{{ error }}</Alert>

      <div class="grid gap-2">
        <p class="font-mono text-xs uppercase tracking-[0.06em] text-text-hi">
          {{ statusText }}
        </p>

        <Progress
          v-if="showProgress"
          :value="progressValue"
          :max="CAPTURE_COUNT"
          :label="statusText"
        />
      </div>

      <FaceSourcePicker
        v-if="showCamera"
        ref="sourcePicker"
        @ready="handleCameraReady"
        @camera-error="handleCameraError"
      >
        <template #overlay>
          <div
            v-if="phase === 'countdown'"
            class="pointer-events-none absolute inset-0 grid place-items-center bg-black/40"
          >
            <span
              class="font-mono text-6xl text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.8)] md:text-8xl"
            >
              {{ countdown }}
            </span>
          </div>
          <div
            v-if="phase === 'capturing' && lastFailure"
            class="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/40 px-6 text-center"
          >
            <p class="font-mono text-base font-bold text-red-200 md:text-xl">{{ lastFailure }}</p>
          </div>
        </template>
      </FaceSourcePicker>

      <div
        v-if="summary || showActions"
        class="grid gap-3 rounded-[2px] border border-border bg-bg p-3"
      >
        <div v-if="summary" class="grid gap-2">
          <Alert :variant="summary.failed ? 'warn' : 'ok'">
            {{ summary.succeeded }} succeeded, {{ summary.failed }} failed.
          </Alert>
          <ul v-if="summary.failures.length" class="grid gap-1 font-mono text-xs text-text-lo">
            <li v-for="failure in summary.failures" :key="failure.reason">
              {{ failure.count }} {{ failure.reason }}
            </li>
          </ul>
        </div>

        <div v-if="showActions" class="flex flex-wrap gap-2">
          <Button class="w-20" size="sm" variant="primary" @click="done">Done</Button>
          <Button
            class="w-20"
            size="sm"
            variant="secondary"
            :disabled="loadingUsers || isRunning"
            @click="captureAgain"
          >
            Again
          </Button>
          <Button v-if="canCancel" class="w-20" size="sm" variant="err" @click="cancel">
            Cancel
          </Button>
        </div>
      </div>
    </div>
  </AddFaceLayout>
</template>
