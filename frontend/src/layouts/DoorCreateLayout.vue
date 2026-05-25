<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Button, Card } from '@/lib'

defineOptions({ name: 'DoorCreateLayout' })
</script>

<template>
  <div class="grid gap-3">
    <RouterLink to="/doors" class="justify-self-start">
      <Button variant="ghost" size="xs">Back</Button>
    </RouterLink>
    <Card title="New door">
      <slot />
    </Card>
  </div>
</template>
