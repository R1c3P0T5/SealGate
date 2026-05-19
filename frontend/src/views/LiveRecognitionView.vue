<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { Alert, Avatar, Badge, Button, Card, Placeholder, Select, useToast } from '@/lib'
import type { SelectOption } from '@/lib'
import LiveRecognitionLayout from '@/layouts/LiveRecognitionLayout.vue'
import { listDoorsEndpointApiDoorsGet } from '@/api/sdk.gen'
import type { DoorResponse, RecognizeResponse } from '@/api/types.gen'

defineOptions({ name: 'LiveRecognitionView' })

// TODO: Wire to backend pub/sub once available.
// Backend needs:
//   1. /ws/camera/preview for the admin live view
//   2. /ws/events/access for recognition and door events
//   3. POST /api/doors/{id}/unlock endpoint

const MOCK_RESULTS: RecognizeResponse[] = [
  { matched: true, user_id: 'mock-1', username: 'jerry', confidence: 0.8743 },
  { matched: false, user_id: null, username: null, confidence: 0.1205 },
  { matched: true, user_id: 'mock-2', username: 'alice', confidence: 0.9412 },
  { matched: false, user_id: null, username: null, confidence: 0.0 },
]
const MOCK_INTERVAL_MS = 3000

const toast = useToast()

const lastResult = ref<RecognizeResponse | null>(null)
const error = ref<string | null>(null)
const doors = ref<DoorResponse[]>([])
const selectedDoorId = ref('')
const loadingDoors = ref(false)
const unlocking = ref(false)

let mockTimer: number | null = null
let mockIndex = 0

const doorOptions = computed<SelectOption[]>(() =>
  doors.value
    .filter((door) => door.is_active)
    .map((door) => ({ value: door.id, label: door.name })),
)
const selectedDoor = computed(
  () => doors.value.find((door) => door.id === selectedDoorId.value) ?? null,
)

function formatConfidence(value: number) {
  return `${(value * 100).toFixed(2)}%`
}

function initials(value?: string | null) {
  if (!value) return '--'
  return value.slice(0, 2).toUpperCase()
}

async function loadDoors() {
  loadingDoors.value = true
  try {
    const response = await listDoorsEndpointApiDoorsGet({ throwOnError: true })
    doors.value = response.data.doors
    const firstActive = doorOptions.value[0]?.value
    if (firstActive) selectedDoorId.value = firstActive
  } catch {
    error.value = 'Could not load doors.'
  } finally {
    loadingDoors.value = false
  }
}

function startMockFeed() {
  // MOCK: cycle through fake recognition results to simulate door camera events.
  mockTimer = window.setInterval(() => {
    lastResult.value = MOCK_RESULTS[mockIndex] ?? null
    mockIndex = (mockIndex + 1) % MOCK_RESULTS.length
  }, MOCK_INTERVAL_MS)
}

function stopMockFeed() {
  if (mockTimer !== null) window.clearInterval(mockTimer)
  mockTimer = null
}

function unlockDoor() {
  if (!selectedDoor.value) return

  // TODO: wire to POST /api/doors/{door_id}/unlock once backend endpoint exists.
  unlocking.value = true
  try {
    toast.show({
      title: `Unlock requested: ${selectedDoor.value.name}`,
      message: 'Mock action — backend endpoint not yet implemented.',
      duration: 2600,
    })
  } finally {
    unlocking.value = false
  }
}

onMounted(() => {
  void loadDoors()
  startMockFeed()
})

onUnmounted(() => {
  stopMockFeed()
})
</script>

<template>
  <LiveRecognitionLayout>
    <Alert v-if="error" variant="err">{{ error }}</Alert>

    <div class="grid gap-4 md:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
      <Card title="Door Camera">
        <div
          class="grid aspect-video place-items-center rounded-[2px] border border-border bg-element"
        >
          <div class="text-center">
            <p class="font-mono text-xs uppercase tracking-[0.08em] text-text-placeholder">
              Mock door camera feed
            </p>
            <p class="mt-1 font-mono text-[10px] uppercase tracking-[0.06em] text-text-placeholder">
              Waiting for backend pub/sub
            </p>
          </div>
        </div>
      </Card>

      <div class="grid content-start gap-4">
        <Card title="Last Result" fit>
          <div v-if="lastResult" class="grid gap-3">
            <div class="flex items-center gap-3">
              <Avatar
                :initials="initials(lastResult.username)"
                size="lg"
                :class="{ 'opacity-60': !lastResult.matched }"
              />
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-text-hi">
                  {{ lastResult.username ?? 'Unknown face' }}
                </p>
                <p class="font-mono text-xs text-text-placeholder">
                  {{ formatConfidence(lastResult.confidence) }}
                </p>
              </div>
            </div>
            <Badge :variant="lastResult.matched ? 'ok' : 'warn'">
              {{ lastResult.matched ? 'Matched' : 'No match' }}
            </Badge>
          </div>
          <Placeholder v-else label="Waiting for face…" :height="160" />
        </Card>

        <Card title="Door Control" fit>
          <div class="grid gap-3">
            <Select
              v-if="doorOptions.length > 1"
              v-model="selectedDoorId"
              :options="doorOptions"
              :disabled="loadingDoors || unlocking"
              placeholder="Select door"
            />
            <p
              v-if="selectedDoor"
              class="font-mono text-xs uppercase tracking-[0.06em] text-text-lo"
            >
              {{ selectedDoor.name }}
            </p>
            <p v-else class="font-mono text-xs uppercase tracking-[0.06em] text-text-placeholder">
              {{ loadingDoors ? 'Loading doors…' : 'No active door' }}
            </p>
            <Button
              variant="primary"
              :disabled="!selectedDoor || unlocking"
              :loading="unlocking"
              @click="unlockDoor"
            >
              Unlock
            </Button>
          </div>
        </Card>
      </div>
    </div>
  </LiveRecognitionLayout>
</template>
