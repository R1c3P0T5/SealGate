<script setup lang="ts">
defineOptions({ name: 'FacesLayout' })
</script>

<template>
  <div class="grid gap-4">
    <div class="grid gap-3 md:flex md:flex-wrap md:items-start md:justify-between">
      <h1 class="font-mono text-sm uppercase tracking-[0.08em] text-text-hi">Face Management</h1>
      <div
        class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 md:ml-auto md:flex md:w-auto md:flex-wrap md:justify-end"
      >
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </div>
</template>
