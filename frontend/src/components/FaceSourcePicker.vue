<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'

import { Alert } from '@/lib'

defineOptions({ name: 'FaceSourcePicker' })

const videoEl = ref<HTMLVideoElement | null>(null)
const stream = ref<MediaStream | null>(null)
const cameraError = ref<string | null>(null)

async function startCamera() {
  if (stream.value) return

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
    <div class="overflow-hidden rounded-[2px] border border-border bg-bg">
      <video
        ref="videoEl"
        autoplay
        playsinline
        muted
        class="aspect-video w-full bg-element object-cover"
      />
    </div>
  </div>
</template>
