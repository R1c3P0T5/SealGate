<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Button, Card } from '@/lib'

defineOptions({ name: 'AddFaceLayout' })
</script>

<template>
  <div class="grid max-w-3xl gap-3">
    <RouterLink to="/faces" class="justify-self-start">
      <Button variant="ghost" size="xs">Back</Button>
    </RouterLink>
    <Card title="Add Face">
      <slot />
    </Card>
  </div>
</template>
