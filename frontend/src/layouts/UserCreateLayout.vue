<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Button, Card } from '@/lib'

defineOptions({ name: 'UserCreateLayout' })
</script>

<template>
  <div class="grid gap-3">
    <RouterLink to="/user-management" class="justify-self-start">
      <Button variant="ghost" size="xs">Back</Button>
    </RouterLink>
    <Card title="New user">
      <slot />
    </Card>
  </div>
</template>
