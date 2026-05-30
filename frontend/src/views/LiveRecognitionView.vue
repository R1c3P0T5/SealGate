<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Alert, Avatar, Badge, Button, Card, Placeholder, Select, useToast } from '@/lib'
import type { SelectOption } from '@/lib'
import LiveRecognitionLayout from '@/layouts/LiveRecognitionLayout.vue'
import {
  createCameraPreviewTicketApiWsTicketsCameraPreviewPost,
  getCurrentUserInfoApiAuthMeGet,
  listDoorsEndpointApiDoorsGet,
  unlockDoorEndpointApiDoorsDoorIdUnlockPost,
} from '@/api/sdk.gen'
import type { AccessLogResponse, DoorResponse } from '@/api/types.gen'
import { useAuthStore } from '@/stores/auth'
import { gestureImageUrl } from '@/stores/gestures'

defineOptions({ name: 'LiveRecognitionView' })

type ConnectionStatus = 'connecting' | 'live' | 'offline'
type CameraStatus = 'idle' | 'connecting' | 'live' | 'offline'
type FaceBox = { x: number; y: number; width: number; height: number; score?: number }
type HandBox = FaceBox & { sign?: string }

const MAX_EVENTS = 20
const VISIBLE_EVENTS = 3
const RECONNECT_DELAY_MS = 3000
const MATCH_HIGHLIGHT_MS = 2000
const FACE_BOX_MATCH_COLOR = '#a4d5b5'
const FACE_BOX_DEFAULT_COLOR = '#e0a8a8'
const HAND_BOX_COLOR = '#d96b6b'
const HAND_BOX_MATCH_COLOR = '#a4d5b5'

const toast = useToast()
const auth = useAuthStore()

const status = ref<ConnectionStatus>('offline')
const events = ref<AccessLogResponse[]>([])
const doors = ref<DoorResponse[]>([])
const selectedDoorId = ref('')
const loadingDoors = ref(false)
const unlocking = ref(false)
const error = ref<string | null>(null)

const cameraStatus = ref<CameraStatus>('idle')
const cameraFrameUrl = ref<string | null>(null)
const faceBoxes = ref<FaceBox[]>([])
const handBoxes = ref<HandBox[]>([])
const matchActive = ref(false)

let socket: WebSocket | null = null
let reconnectTimer: number | null = null
let manuallyClosed = false
let matchHighlightTimer: number | null = null

let cameraSocket: WebSocket | null = null
let cameraReconnectTimer: number | null = null
let cameraManuallyClosed = false
let activeCameraDoorId: string | null = null

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

const cameraBadge = computed(() => {
  switch (cameraStatus.value) {
    case 'live':
      return { variant: 'ok' as const, label: 'Live' }
    case 'connecting':
      return { variant: 'warn' as const, label: 'Connecting…' }
    case 'offline':
      return { variant: 'err' as const, label: 'Offline' }
    case 'idle':
    default:
      return { variant: 'dim' as const, label: 'Idle' }
  }
})

const cameraPlaceholderLabel = computed(() => {
  switch (cameraStatus.value) {
    case 'connecting':
      return 'Connecting to camera…'
    case 'offline':
      return 'Camera offline'
    case 'live':
      return ''
    case 'idle':
    default:
      return loadingDoors.value ? 'Loading doors…' : 'Select a door to preview'
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
      if (data.door_id === selectedDoorId.value && data.confidence != null) flashMatch()
    } catch {
      // ignore malformed payload
    }
  }
  socket.onclose = (event) => {
    status.value = 'offline'
    if (event.code === 1008 && auth.isAuthenticated) {
      void getCurrentUserInfoApiAuthMeGet().catch(() => {})
      return
    }
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

function flashMatch() {
  matchActive.value = true
  if (matchHighlightTimer !== null) window.clearTimeout(matchHighlightTimer)
  matchHighlightTimer = window.setTimeout(() => {
    matchActive.value = false
    matchHighlightTimer = null
  }, MATCH_HIGHLIGHT_MS)
}

function clearMatchHighlight() {
  if (matchHighlightTimer !== null) window.clearTimeout(matchHighlightTimer)
  matchHighlightTimer = null
  matchActive.value = false
}

function releaseFrame() {
  if (cameraFrameUrl.value) {
    URL.revokeObjectURL(cameraFrameUrl.value)
    cameraFrameUrl.value = null
  }
}

function disconnectCamera() {
  cameraManuallyClosed = true
  if (cameraReconnectTimer !== null) window.clearTimeout(cameraReconnectTimer)
  cameraReconnectTimer = null
  cameraSocket?.close()
  cameraSocket = null
  activeCameraDoorId = null
  releaseFrame()
  faceBoxes.value = []
  handBoxes.value = []
  clearMatchHighlight()
  cameraStatus.value = 'idle'
}

function scheduleCameraReconnect(doorId: string) {
  if (cameraReconnectTimer !== null) return
  cameraReconnectTimer = window.setTimeout(() => {
    cameraReconnectTimer = null
    void connectCamera(doorId)
  }, RECONNECT_DELAY_MS)
}

async function connectCamera(doorId: string) {
  if (!auth.token) {
    cameraStatus.value = 'idle'
    return
  }
  cameraSocket?.close()
  cameraSocket = null
  cameraManuallyClosed = false
  activeCameraDoorId = doorId
  cameraStatus.value = 'connecting'

  let ticket: string
  try {
    const response = await createCameraPreviewTicketApiWsTicketsCameraPreviewPost({
      body: { door_id: doorId },
      throwOnError: true,
    })
    ticket = response.data.ticket
  } catch {
    if (activeCameraDoorId === doorId) {
      cameraStatus.value = 'offline'
      if (!cameraManuallyClosed) scheduleCameraReconnect(doorId)
    }
    return
  }
  if (activeCameraDoorId !== doorId) return

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/ws/camera/${doorId}/preview?ticket=${encodeURIComponent(ticket)}`
  const ws = new WebSocket(url)
  ws.binaryType = 'blob'
  cameraSocket = ws
  ws.onmessage = (ev) => {
    if (cameraSocket !== ws) return
    if (typeof ev.data === 'string') {
      try {
        const payload = JSON.parse(ev.data) as {
          type?: string
          faces?: FaceBox[]
          hands?: HandBox[]
        }
        if (payload.type === 'face_boxes' && Array.isArray(payload.faces)) {
          faceBoxes.value = payload.faces
        } else if (payload.type === 'hand_boxes' && Array.isArray(payload.hands)) {
          handBoxes.value = payload.hands
        }
      } catch {
        // ignore malformed metadata
      }
      return
    }
    if (!(ev.data instanceof Blob)) return
    const previous = cameraFrameUrl.value
    cameraFrameUrl.value = URL.createObjectURL(ev.data)
    if (previous) URL.revokeObjectURL(previous)
    if (cameraStatus.value !== 'live') cameraStatus.value = 'live'
  }
  ws.onclose = () => {
    if (cameraSocket !== ws) return
    cameraSocket = null
    cameraStatus.value = 'offline'
    if (!cameraManuallyClosed && activeCameraDoorId === doorId) {
      scheduleCameraReconnect(doorId)
    }
  }
  ws.onerror = () => {
    if (cameraSocket !== ws) return
    cameraStatus.value = 'offline'
  }
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

async function unlockDoor() {
  const door = selectedDoor.value
  if (!door) return
  unlocking.value = true
  try {
    await unlockDoorEndpointApiDoorsDoorIdUnlockPost({
      path: { door_id: door.id },
      throwOnError: true,
    })
    toast.show({
      title: `Unlocked ${door.name}`,
      duration: 2600,
    })
  } catch {
    toast.show({
      title: `Failed to unlock ${door.name}`,
      message: 'Please try again or check device status.',
      duration: 3200,
    })
  } finally {
    unlocking.value = false
  }
}

watch(
  () => auth.token,
  () => {
    disconnect()
    disconnectCamera()
    connect()
    if (selectedDoorId.value) void connectCamera(selectedDoorId.value)
  },
)

watch(selectedDoorId, (id) => {
  disconnectCamera()
  if (id) void connectCamera(id)
})

onMounted(() => {
  void loadDoors()
  connect()
})

onBeforeUnmount(() => {
  disconnect()
  disconnectCamera()
})
</script>

<template>
  <LiveRecognitionLayout>
    <Alert v-if="error" variant="err">{{ error }}</Alert>

    <div class="grid gap-4 md:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
      <Card title="Door Camera" fit>
        <template #action>
          <Badge :variant="cameraBadge.variant">{{ cameraBadge.label }}</Badge>
        </template>
        <div
          class="relative grid aspect-video place-items-center overflow-hidden rounded-[2px] border border-border bg-element"
        >
          <img
            v-if="cameraFrameUrl"
            :src="cameraFrameUrl"
            alt="Door camera feed"
            class="absolute inset-0 h-full w-full object-cover"
          />
          <svg
            v-if="cameraFrameUrl && faceBoxes.length"
            class="pointer-events-none absolute inset-0 h-full w-full opacity-50"
            :style="{ color: matchActive ? FACE_BOX_MATCH_COLOR : FACE_BOX_DEFAULT_COLOR }"
            viewBox="0 0 1 1"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <rect
              v-for="(box, index) in faceBoxes"
              :key="index"
              :x="box.x"
              :y="box.y"
              :width="box.width"
              :height="box.height"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              vector-effect="non-scaling-stroke"
            />
          </svg>
          <div
            v-if="cameraFrameUrl && handBoxes.length"
            class="pointer-events-none absolute inset-0"
            aria-hidden="true"
          >
            <div
              v-for="(box, index) in handBoxes"
              :key="index"
              class="absolute border-2"
              :style="{
                left: `${box.x * 100}%`,
                top: `${box.y * 100}%`,
                width: `${box.width * 100}%`,
                height: `${box.height * 100}%`,
                borderColor: box.sign ? HAND_BOX_MATCH_COLOR : HAND_BOX_COLOR,
              }"
            >
              <img
                v-if="box.sign"
                :src="gestureImageUrl(box.sign)"
                :alt="box.sign"
                class="absolute left-0 top-0 h-7 w-7 -translate-y-full rounded-[2px] border-2 object-cover md:h-9 md:w-9"
                :style="{ borderColor: HAND_BOX_MATCH_COLOR }"
              />
            </div>
          </div>
          <p
            v-if="!cameraFrameUrl"
            class="font-mono text-xs uppercase tracking-[0.08em] text-text-placeholder"
          >
            {{ cameraPlaceholderLabel }}
          </p>
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
              class="event-row grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 rounded-[2px] border-b border-border-soft px-1 pb-2 last:border-b-0 last:pb-0"
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

<style scoped>
.event-row {
  animation: event-flash 2s ease-out;
}
@keyframes event-flash {
  from {
    background-color: rgba(99, 174, 128, 0.35);
  }
  to {
    background-color: transparent;
  }
}
@media (prefers-reduced-motion: reduce) {
  .event-row {
    animation: none;
  }
}
</style>
