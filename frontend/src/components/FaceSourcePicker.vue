<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { Alert, Button, Tabs } from '@/lib'
import type { Tab } from '@/lib'

defineOptions({ name: 'FaceSourcePicker' })

const props = defineProps<{
  modelValue: File | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [file: File | null]
}>()

const tabs: Tab[] = [
  { key: 'camera', label: 'Camera' },
  { key: 'upload', label: 'Upload' },
]

const activeTab = ref<string>('camera')
const videoEl = ref<HTMLVideoElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const stream = ref<MediaStream | null>(null)
const previewUrl = ref<string | null>(null)
const cameraError = ref<string | null>(null)

function revokePreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = null
}

function emitFile(file: File | null) {
  revokePreview()
  if (file) previewUrl.value = URL.createObjectURL(file)
  emit('update:modelValue', file)
}

async function startCamera() {
  if (stream.value || activeTab.value !== 'camera') return

  cameraError.value = null
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera unavailable')
    stream.value = await navigator.mediaDevices.getUserMedia({ video: true })
    await nextTick()
    if (videoEl.value) videoEl.value.srcObject = stream.value
  } catch {
    cameraError.value = 'Camera permission denied'
  }
}

function stopCamera() {
  stream.value?.getTracks().forEach((track) => track.stop())
  stream.value = null
  if (videoEl.value) videoEl.value.srcObject = null
}

function capture() {
  const video = videoEl.value
  const canvas = canvasEl.value
  if (!video || !canvas || video.videoWidth === 0 || video.videoHeight === 0) {
    cameraError.value = 'Camera not ready'
    return
  }

  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height)
  canvas.toBlob(
    (blob) => {
      if (!blob) {
        cameraError.value = 'Capture failed'
        return
      }
      emitFile(new File([blob], 'capture.jpg', { type: 'image/jpeg' }))
    },
    'image/jpeg',
    0.92,
  )
}

function openFilePicker() {
  fileInput.value?.click()
}

function chooseFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  emitFile(file)
}

function clearSelection() {
  if (fileInput.value) fileInput.value.value = ''
  emitFile(null)
}

watch(activeTab, (tab) => {
  if (tab === 'camera') void startCamera()
  else stopCamera()
})

watch(
  () => props.modelValue,
  (value) => {
    if (!value && previewUrl.value) revokePreview()
  },
)

onMounted(() => {
  void startCamera()
})

onUnmounted(() => {
  stopCamera()
  revokePreview()
})
</script>

<template>
  <div class="grid gap-4">
    <Tabs v-model="activeTab" :tabs="tabs">
      <template #camera>
        <div class="grid gap-3">
          <Alert v-if="cameraError" variant="err">{{ cameraError }}</Alert>
          <div class="overflow-hidden rounded-[2px] border border-border bg-bg">
            <video
              ref="videoEl"
              autoplay
              playsinline
              muted
              class="aspect-video w-full bg-element object-cover"
            />
          </div>
          <canvas ref="canvasEl" class="hidden" />
          <div class="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              :disabled="disabled || !!cameraError || !stream"
              @click="capture"
            >
              Capture
            </Button>
            <Button
              v-if="modelValue"
              type="button"
              variant="ghost"
              :disabled="disabled"
              @click="clearSelection"
            >
              Retake
            </Button>
          </div>
        </div>
      </template>

      <template #upload>
        <div class="grid gap-3">
          <input ref="fileInput" type="file" accept="image/*" class="hidden" @change="chooseFile" />
          <Button
            type="button"
            variant="secondary"
            class="justify-self-start"
            :disabled="disabled"
            @click="openFilePicker"
          >
            Choose image
          </Button>
        </div>
      </template>
    </Tabs>

    <div v-if="previewUrl" class="grid gap-2">
      <p class="font-mono text-[11px] uppercase tracking-[0.06em] text-text-placeholder">Preview</p>
      <img
        :src="previewUrl"
        alt="Selected face"
        class="max-h-64 w-full rounded-[2px] border border-border object-contain"
      />
    </div>
  </div>
</template>
