<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Alert, Avatar, Badge, Button, Card, Placeholder, Select, useToast } from '@/lib'
import type { SelectOption } from '@/lib'
import LiveRecognitionLayout from '@/layouts/LiveRecognitionLayout.vue'
import { listDoorsEndpointApiDoorsGet } from '@/api/sdk.gen'
import type { AccessLogResponse, DoorResponse } from '@/api/types.gen'
import { useAuthStore } from '@/stores/auth'

defineOptions({ name: 'LiveRecognitionView' })

// TODO: Door Camera and Door Control are still mock; backend needs
//   1. /ws/camera/preview for the admin live view
//   2. POST /api/doors/{id}/unlock endpoint

type ConnectionStatus = 'connecting' | 'live' | 'offline'

const MAX_EVENTS = 20
const VISIBLE_EVENTS = 3
const RECONNECT_DELAY_MS = 3000

const toast = useToast()
const auth = useAuthStore()

const status = ref<ConnectionStatus>('offline')
const events = ref<AccessLogResponse[]>([])
const doors = ref<DoorResponse[]>([])
const selectedDoorId = ref('')
const loadingDoors = ref(false)
const unlocking = ref(false)
const error = ref<string | null>(null)

let socket: WebSocket | null = null
let reconnectTimer: number | null = null
let manuallyClosed = false

const doorOptions = computed<SelectOption[]>(() =>
  doors.value
    .filter((door) => door.is_active)
    .map((door) => ({ value: door.id, label: door.name })),
)
const selectedDoor = computed(
  () => doors.value.find((door) => door.id === selectedDoorId.value) ?? null,
)
const visibleEvents = computed(() =>
  selectedDoorId.value
    ? events.value.filter((e) => e.door_id === selectedDoorId.value).slice(0, VISIBLE_EVENTS)
    : [],
)

const statusBadge = computed(() => {
  switch (status.value) {
    case 'live':
      return { variant: 'ok' as const, label: 'Live' }
    case 'connecting':
      return { variant: 'warn' as const, label: 'Connecting…' }
    case 'offline':
    default:
      return { variant: 'err' as const, label: 'Offline' }
  }
})

function pad(n: number) {
  return String(n).padStart(2, '0')
}
function formatTime(iso: string) {
  const d = new Date(iso)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
function formatConfidence(value: number) {
  return `${(value * 100).toFixed(2)}%`
}
function initials(value?: string | null) {
  if (!value) return '--'
  return value.slice(0, 2).toUpperCase()
}

function connect() {
  if (!auth.token) {
    status.value = 'offline'
    return
  }
  manuallyClosed = false
  status.value = 'connecting'
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/ws/events/access?access_token=${encodeURIComponent(auth.token)}`
  socket = new WebSocket(url)
  socket.onopen = () => {
    status.value = 'live'
  }
  socket.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data) as AccessLogResponse
      events.value = [data, ...events.value].slice(0, MAX_EVENTS)
    } catch {
      // ignore malformed payload
    }
  }
  socket.onclose = () => {
    status.value = 'offline'
    if (!manuallyClosed) scheduleReconnect()
  }
  socket.onerror = () => {
    status.value = 'offline'
  }
}

function scheduleReconnect() {
  if (reconnectTimer !== null) return
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    connect()
  }, RECONNECT_DELAY_MS)
}

function disconnect() {
  manuallyClosed = true
  if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
  reconnectTimer = null
  socket?.close()
  socket = null
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

watch(
  () => auth.token,
  () => {
    disconnect()
    connect()
  },
)

onMounted(() => {
  void loadDoors()
  connect()
})

onBeforeUnmount(disconnect)
</script>

<template>
  <LiveRecognitionLayout>
    <Alert v-if="error" variant="err">{{ error }}</Alert>

    <div class="grid gap-4 md:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
      <Card title="Door Camera" fit>
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
        <Card title="Live Events">
          <template #action>
            <Badge :variant="statusBadge.variant">{{ statusBadge.label }}</Badge>
          </template>
          <Placeholder v-if="visibleEvents.length === 0" label="Waiting for events…" :height="60" />
          <ul v-else class="grid max-h-64 gap-2 overflow-y-auto">
            <li
              v-for="event in visibleEvents"
              :key="event.id"
              class="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 border-b border-border-soft pb-2 last:border-b-0 last:pb-0"
            >
              <Avatar
                :initials="initials(event.username)"
                size="sm"
                :class="{ 'opacity-60': !event.username }"
              />
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-text-hi">
                  {{ event.username ?? 'Unknown' }}
                </p>
                <p class="font-mono text-[10px] uppercase tracking-[0.04em] text-text-placeholder">
                  {{ formatTime(event.timestamp)
                  }}<template v-if="event.confidence != null">
                    · {{ formatConfidence(event.confidence) }}</template
                  >
                </p>
              </div>
              <Badge :variant="event.door_opened ? 'ok' : 'err'">
                {{ event.door_opened ? 'Opened' : 'Denied' }}
              </Badge>
            </li>
          </ul>
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
              v-if="selectedDoor && doorOptions.length <= 1"
              class="font-mono text-xs uppercase tracking-[0.06em] text-text-lo"
            >
              {{ selectedDoor.name }}
            </p>
            <p
              v-else-if="!selectedDoor"
              class="font-mono text-xs uppercase tracking-[0.06em] text-text-placeholder"
            >
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
