<script setup lang="ts">
import AddFaceLayout from '@/layouts/AddFaceLayout.vue'
import FaceSourcePicker from '@/components/FaceSourcePicker.vue'

defineOptions({ name: 'AddFaceView' })
</script>

<template>
  <AddFaceLayout>
    <FaceSourcePicker />
  </AddFaceLayout>
</template>
