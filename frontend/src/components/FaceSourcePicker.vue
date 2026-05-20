<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'

import { Alert } from '@/lib'

defineOptions({ name: 'FaceSourcePicker' })

const emit = defineEmits<{
  ready: []
  'camera-error': [message: string]
}>()

const videoEl = ref<HTMLVideoElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const stream = ref<MediaStream | null>(null)
const startingCamera = ref(false)
const cameraError = ref<string | null>(null)

let readyEmitted = false

async function startCamera() {
  if (stream.value || startingCamera.value) return

  readyEmitted = false
  startingCamera.value = true
  cameraError.value = null
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera unavailable')
    stream.value = await navigator.mediaDevices.getUserMedia({ video: true })
    await nextTick()
    if (videoEl.value) {
      videoEl.value.srcObject = stream.value
      void videoEl.value.play().catch(() => undefined)
      emitReady()
    }
  } catch {
    cameraError.value = 'Camera permission denied'
    emit('camera-error', cameraError.value)
  } finally {
    startingCamera.value = false
  }
}

function stopCamera() {
  stream.value?.getTracks().forEach((track) => track.stop())
  stream.value = null
  readyEmitted = false
  if (videoEl.value) videoEl.value.srcObject = null
}

function emitReady() {
  if (readyEmitted || !videoEl.value?.videoWidth || !videoEl.value?.videoHeight) return

  readyEmitted = true
  emit('ready')
}

async function captureFrame(index: number) {
  const video = videoEl.value
  const canvas = canvasEl.value
  if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
    throw new Error('Camera is not ready.')
  }

  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Could not capture camera frame.')

  context.drawImage(video, 0, 0, canvas.width, canvas.height)
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (value) => {
        if (value) resolve(value)
        else reject(new Error('Could not capture camera frame.'))
      },
      'image/jpeg',
      0.9,
    )
  })

  return new File([blob], `face-capture-${String(index).padStart(2, '0')}.jpg`, {
    type: 'image/jpeg',
  })
}

defineExpose({ startCamera, stopCamera, captureFrame })

onMounted(() => {
  void startCamera()
})

onUnmounted(() => {
  stopCamera()
})
</script>

<template>
  <div class="grid gap-3">
    <Alert v-if="cameraError" variant="err">{{ cameraError }}</Alert>
    <div class="relative overflow-hidden rounded-[2px] border border-border bg-bg">
      <video
        ref="videoEl"
        autoplay
        playsinline
        muted
        class="aspect-video w-full bg-element object-cover"
        @loadedmetadata="emitReady"
        @playing="emitReady"
      />
      <canvas ref="canvasEl" class="hidden" aria-hidden="true" />
      <slot name="overlay" />
    </div>
  </div>
</template>
