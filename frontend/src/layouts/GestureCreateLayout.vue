<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Button, Card } from '@/lib'

defineOptions({ name: 'GestureCreateLayout' })
</script>

<template>
  <div class="grid gap-3">
    <RouterLink to="/gestures" class="justify-self-start">
      <Button variant="ghost" size="xs">Back</Button>
    </RouterLink>
    <Card title="New seal">
      <slot />
    </Card>
  </div>
</template>
