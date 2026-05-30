<script setup lang="ts">
import { computed } from 'vue'

export type ButtonVariant =
  | 'primary'
  | 'secondary'
  | 'outline'
  | 'ghost'
  | 'ok'
  | 'info'
  | 'warn'
  | 'err'
  | 'link'
export type ButtonSize = 'xs' | 'sm' | 'default' | 'lg'
export type ButtonColor =
  | string
  | {
      text?: string
      bg: string
      border?: string
      hoverBg?: string
      hoverBorder?: string
    }

defineOptions({
  name: 'UiButton',
})

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariant
    size?: ButtonSize
    color?: ButtonColor
    loading?: boolean
    disabled?: boolean
  }>(),
  {
    variant: 'secondary',
    size: 'default',
    color: undefined,
    loading: false,
    disabled: false,
  },
)

const base =
  'inline-flex items-center justify-center gap-1.5 rounded-[2px] border font-mono text-xs uppercase tracking-[0.06em] whitespace-nowrap transition-all duration-[120ms] cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-1 focus-visible:outline-ac focus-visible:outline-offset-2'

const sizeClasses: Record<ButtonSize, string> = {
  xs: 'min-h-7 px-2 py-1 text-xs',
  sm: 'min-h-8 min-w-20 px-2.5 py-1.5 text-xs',
  default: 'min-h-9 px-3 py-2',
  lg: 'min-h-10.5 px-3.5 py-2.5 text-[0.8125rem]',
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-ac border-ac text-bg hover:bg-text-hi hover:border-text-hi',
  secondary: 'bg-element border-border text-text-hi hover:border-text-placeholder',
  outline:
    'border-text-placeholder text-text-hi bg-transparent hover:bg-overlay hover:border-text-lo',
  ghost:
    'border-transparent text-text-lo bg-transparent hover:bg-overlay hover:border-border hover:text-text-hi',
  ok: 'text-ok border-ok/50 bg-ok/10 hover:bg-ok/20 hover:border-ok',
  info: 'text-info border-info/50 bg-info/10 hover:bg-info/20 hover:border-info',
  warn: 'text-warn border-warn/50 bg-warn/10 hover:bg-warn/20 hover:border-warn',
  err: 'text-err border-err/50 bg-err/10 hover:bg-err/20 hover:border-err',
  link: 'border-transparent bg-transparent text-ac underline p-0 min-h-0 hover:opacity-75',
}

const colorClasses =
  'text-[var(--button-text)] border-[var(--button-border)] bg-[var(--button-bg)] hover:bg-[var(--button-hover-bg)] hover:border-[var(--button-hover-border)]'

const classes = computed(() => [
  base,
  sizeClasses[props.size],
  props.color ? colorClasses : variantClasses[props.variant],
])

const colorStyle = computed(() => {
  if (!props.color) return undefined

  const bg = typeof props.color === 'string' ? props.color : props.color.bg
  const text =
    typeof props.color === 'string' ? 'var(--color-bg)' : (props.color.text ?? 'var(--color-bg)')
  const border =
    typeof props.color === 'string' ? props.color : (props.color.border ?? props.color.bg)
  const hoverBg =
    typeof props.color === 'string' ? props.color : (props.color.hoverBg ?? props.color.bg)
  const hoverBorder =
    typeof props.color === 'string' ? props.color : (props.color.hoverBorder ?? hoverBg)

  return {
    '--button-text': text,
    '--button-bg': bg,
    '--button-border': border,
    '--button-hover-bg': hoverBg,
    '--button-hover-border': hoverBorder,
  }
})
</script>

<template>
  <button
    v-bind="$attrs"
    :class="classes"
    :style="colorStyle"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
  >
    <slot />
    <span v-if="loading" class="loading-spinner" aria-hidden="true" />
  </button>
</template>

<style scoped>
.loading-spinner {
  width: 10px;
  height: 10px;
  border: 1px solid color-mix(in srgb, currentColor 45%, transparent);
  border-top-color: currentColor;
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(1turn);
  }
}
</style>
