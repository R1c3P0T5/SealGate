<script setup lang="ts">
import { Card } from '@/lib'

defineOptions({ name: 'SettingsLayout' })
</script>

<template>
  <div class="grid gap-3">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="font-mono text-sm text-text-hi">Settings</h1>
      <div class="flex items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <Card>
      <slot />
    </Card>
  </div>
</template>
