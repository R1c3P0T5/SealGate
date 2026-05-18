<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Button, Card } from '@/lib'

defineOptions({ name: 'AddFaceLayout' })
</script>

<template>
  <Card class="max-w-3xl">
    <div class="grid gap-5">
      <div class="grid gap-1">
        <RouterLink to="/faces" class="justify-self-start">
          <Button variant="ghost" size="xs">Back</Button>
        </RouterLink>
        <h1 class="font-mono text-sm uppercase tracking-[0.08em] text-text-hi">Add Face</h1>
      </div>
      <slot />
    </div>
  </Card>
</template>
