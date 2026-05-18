<script setup lang="ts">
defineOptions({ name: 'FacesLayout' })
</script>

<template>
  <div class="grid gap-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <h1 class="font-mono text-sm uppercase tracking-[0.08em] text-text-hi">Face Management</h1>
      <div class="flex w-full flex-wrap items-center gap-2 md:ml-auto md:w-auto md:justify-end">
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </div>
</template>
