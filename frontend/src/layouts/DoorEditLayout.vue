<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Button, Card } from '@/lib'

defineOptions({ name: 'DoorEditLayout' })
</script>

<template>
  <div class="grid gap-3">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <RouterLink to="/doors">
          <Button variant="ghost" size="xs">Back</Button>
        </RouterLink>
        <h1 class="font-mono text-sm text-text-hi">
          <slot name="title" />
        </h1>
      </div>
      <div class="flex items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <Card>
      <slot />
    </Card>
  </div>
</template>
