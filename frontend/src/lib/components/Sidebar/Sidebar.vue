<script setup lang="ts">
defineOptions({ name: 'UiSidebar' })

defineProps<{
  brand: string
}>()
</script>

<template>
  <aside
    class="sticky top-0 flex h-dvh w-[260px] shrink-0 flex-col gap-3 overflow-y-auto border-r border-border bg-subtle px-3.5 pt-4.5 pb-[max(1.125rem,env(safe-area-inset-bottom))]"
  >
    <!-- Brand row -->
    <div class="flex items-center justify-between gap-2 border-b border-border-soft pb-2.5">
      <div class="flex items-center gap-2.5">
        <!-- Brand mark: nested squares -->
        <span class="relative inline-flex h-4 w-4 shrink-0" aria-hidden="true">
          <span class="absolute inset-0 rounded-[1px] border border-ok/50 bg-ok/10" />
          <span class="absolute inset-[4px] rounded-[1px] border border-ok/60" />
        </span>
        <strong class="font-mono text-[11px] uppercase tracking-[0.08em] text-text-hi">
          {{ brand }}
        </strong>
      </div>
      <slot name="brand-action" />
    </div>

    <!-- Optional header area (meta text, chips, etc.) -->
    <div v-if="$slots.header" class="grid gap-2">
      <slot name="header" />
    </div>

    <!-- Nav area — grows to fill remaining space -->
    <div class="flex-1 overflow-y-auto">
      <slot />
    </div>

    <!-- Footer area -->
    <div v-if="$slots.footer" class="border-t border-border-soft pt-2.5">
      <slot name="footer" />
    </div>
  </aside>
</template>
