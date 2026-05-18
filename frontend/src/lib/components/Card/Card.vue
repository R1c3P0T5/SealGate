<script setup lang="ts">
defineOptions({ name: 'UiCard' })

defineProps<{
  kicker?: string
  title?: string
  fit?: boolean
}>()
</script>

<template>
  <div class="min-w-0 rounded-[2px] border border-border bg-subtle" :class="{ 'self-start': fit }">
    <div
      v-if="kicker || title || $slots.action"
      data-card-header
      class="flex items-center justify-between gap-2.5 border-b border-border-soft px-3.5 py-2"
    >
      <div v-if="kicker || title" class="min-w-0">
        <p
          v-if="kicker"
          class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder"
        >
          {{ kicker }}
        </p>
        <h3
          v-if="title"
          class="font-mono text-sm uppercase tracking-[0.05em] text-text-hi"
          :class="{ 'mt-0.5': kicker }"
        >
          {{ title }}
        </h3>
      </div>
      <slot name="action" />
    </div>
    <div class="p-3.5">
      <slot />
    </div>
  </div>
</template>
