<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { VueDraggable, type DraggableEvent } from 'vue-draggable-plus'
import type { Options } from 'sortablejs'

import { Alert, Button, Input, useToast } from '@/lib'
import GestureCreateLayout from '@/layouts/GestureCreateLayout.vue'
import { createJutsuEndpointApiJutsuPost } from '@/api/sdk.gen'
import { gestureImageUrl, useGesturesStore } from '@/stores/gestures'

defineOptions({ name: 'GestureCreateView' })

type Seal = { uid: string; jstsu: string }

const NAME_MAX = 128

const router = useRouter()
const store = useGesturesStore()
const toast = useToast()

const name = ref('')
const nameError = ref<string | null>(null)
const generalError = ref<string | null>(null)
const submitting = ref(false)

const libraryItems = ref<Seal[]>(
  store.library.map((g) => ({ uid: `lib-${g.jstsu}`, jstsu: g.jstsu })),
)
const localSteps = ref<Seal[]>([])
const pipelineEl = ref<HTMLElement | null>(null)

// Last order known to satisfy the no-consecutive rule; reconcile() reverts here.
let lastValid: Seal[] = []

const libraryGroup: Options['group'] = { name: 'seals', pull: 'clone', put: false }
const pipelineGroup: Options['group'] = { name: 'seals', pull: true, put: true }

function newUid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `seal-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

// Dragged out of the library: insert a fresh step (new uid), keep the palette intact.
function cloneSeal(item: Seal): Seal {
  return { uid: newUid(), jstsu: item.jstsu }
}

function hasConsecutive(steps: Seal[]): boolean {
  for (let i = 1; i < steps.length; i++) {
    if (steps[i]!.jstsu === steps[i - 1]!.jstsu) return true
  }
  return false
}

// Sortable has already mutated localSteps (add from library, or internal reorder).
// Accept it if legal, otherwise snap back to the last legal order.
function reconcile() {
  if (hasConsecutive(localSteps.value)) {
    toast.show({ title: 'Cannot place two of the same seal in a row.' })
    localSteps.value = lastValid.map((s) => ({ ...s }))
  } else {
    lastValid = localSteps.value.map((s) => ({ ...s }))
  }
}

// SortableEvent doesn't expose the drop coordinates, so track the pointer
// ourselves for the duration of a pipeline drag (forceFallback fires mouse/touch).
let lastPointer: { x: number; y: number } | null = null

function trackPointer(ev: Event) {
  const touch = (ev as TouchEvent).changedTouches?.[0] ?? (ev as TouchEvent).touches?.[0]
  if (touch) {
    lastPointer = { x: touch.clientX, y: touch.clientY }
    return
  }
  const mouse = ev as MouseEvent
  lastPointer = { x: mouse.clientX, y: mouse.clientY }
}

function onStart() {
  lastPointer = null
  document.addEventListener('mousemove', trackPointer, true)
  document.addEventListener('touchmove', trackPointer, true)
}

// Dropped outside the pipeline frame → delete that step, unless removing it would
// leave two identical seals adjacent (then keep it and warn).
function onEnd(evt: DraggableEvent<Seal>) {
  document.removeEventListener('mousemove', trackPointer, true)
  document.removeEventListener('touchmove', trackPointer, true)

  const el = pipelineEl.value
  if (!el || !lastPointer || typeof evt.oldIndex !== 'number') return
  const r = el.getBoundingClientRect()
  const { x, y } = lastPointer
  const inside = x >= r.left && x <= r.right && y >= r.top && y <= r.bottom
  if (inside) return

  const next = [...localSteps.value]
  next.splice(evt.oldIndex, 1)
  if (hasConsecutive(next)) {
    toast.show({ title: 'Removing this would place two of the same seal in a row.' })
    return
  }
  localSteps.value = next
  lastValid = next.map((s) => ({ ...s }))
}

function errorMessage(value: unknown, fallback: string) {
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(String).join(', ')
  }
  return fallback
}

async function save() {
  generalError.value = null
  nameError.value = null
  const trimmed = name.value.trim()
  if (!trimmed) {
    nameError.value = 'Required.'
    return
  }
  if (trimmed.length > NAME_MAX) {
    nameError.value = `At most ${NAME_MAX} characters.`
    return
  }
  if (localSteps.value.length === 0) {
    generalError.value = 'Add at least one seal.'
    return
  }
  submitting.value = true
  try {
    await createJutsuEndpointApiJutsuPost({
      body: { name: trimmed, signs: localSteps.value.map((s) => s.jstsu) },
      throwOnError: true,
    })
    toast.show({ title: 'Seal saved' })
    void router.push({ name: 'gestures' })
  } catch (err) {
    generalError.value = errorMessage(err, 'Could not create seal.')
  } finally {
    submitting.value = false
  }
}

function cancel() {
  void router.push({ name: 'gestures' })
}
</script>

<template>
  <GestureCreateLayout>
    <div class="grid gap-4">
      <Alert v-if="generalError" variant="err">{{ generalError }}</Alert>

      <Input
        v-model="name"
        placeholder="Name"
        :maxlength="NAME_MAX"
        :invalid="!!nameError"
        :error="nameError ?? undefined"
      />

      <section class="grid gap-2">
        <div class="flex items-baseline justify-between gap-2">
          <h2 class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
            Pipeline
          </h2>
          <span class="font-mono text-[11px] text-text-lo">{{ localSteps.length }} steps</span>
        </div>

        <div
          ref="pipelineEl"
          class="relative min-h-32 rounded-[2px] border border-dashed border-border bg-element p-3"
        >
          <VueDraggable
            v-model="localSteps"
            :group="pipelineGroup"
            :animation="300"
            easing="cubic-bezier(0.34, 1.4, 0.64, 1)"
            :force-fallback="true"
            ghost-class="seal-ghost"
            class="flex min-h-24 flex-wrap items-stretch gap-2"
            @start="onStart"
            @add="reconcile"
            @update="reconcile"
            @end="onEnd"
          >
            <div
              v-for="step in localSteps"
              :key="step.uid"
              :data-jstsu="step.jstsu"
              class="relative flex h-20 w-16 md:h-28 md:w-[88px] cursor-grab select-none flex-col items-center gap-1 rounded-md border border-border bg-bg pt-2 md:pt-3 active:cursor-grabbing"
            >
              <img
                :src="gestureImageUrl(step.jstsu)"
                :alt="step.jstsu"
                draggable="false"
                class="pointer-events-none h-12 w-12 rounded-md md:h-20 md:w-20 border border-border-soft object-cover"
              />
              <span class="font-mono text-[9px] text-text-hi md:text-[11px]">{{ step.jstsu }}</span>
            </div>
          </VueDraggable>

          <p
            v-if="localSteps.length === 0"
            class="pointer-events-none absolute inset-0 grid place-items-center font-mono text-[11px] uppercase tracking-[0.08em] text-text-placeholder"
          >
            Drag seals here
          </p>
        </div>
      </section>

      <section class="grid gap-2">
        <h2 class="font-mono text-[11px] uppercase tracking-[0.1em] text-text-placeholder">
          Seals
        </h2>
        <VueDraggable
          v-model="libraryItems"
          :group="libraryGroup"
          :sort="false"
          :clone="cloneSeal"
          :animation="300"
          easing="cubic-bezier(0.34, 1.4, 0.64, 1)"
          :force-fallback="true"
          ghost-class="seal-ghost"
          class="flex flex-wrap gap-2 rounded-[2px] border border-border bg-subtle p-3"
        >
          <div
            v-for="g in libraryItems"
            :key="g.uid"
            :data-jstsu="g.jstsu"
            class="relative flex h-20 w-16 md:h-28 md:w-[88px] cursor-grab select-none flex-col items-center gap-1 rounded-md border border-border bg-bg pt-2 md:pt-3 transition-shadow hover:shadow-sm active:cursor-grabbing"
          >
            <img
              :src="gestureImageUrl(g.jstsu)"
              :alt="g.jstsu"
              draggable="false"
              class="pointer-events-none h-12 w-12 rounded-md md:h-20 md:w-20 border border-border-soft object-cover"
            />
            <span class="font-mono text-[9px] text-text-hi md:text-[11px]">{{ g.jstsu }}</span>
          </div>
        </VueDraggable>
      </section>

      <div class="flex justify-end gap-2 pt-2">
        <Button variant="ghost" size="sm" :disabled="submitting" @click="cancel">Cancel</Button>
        <Button
          variant="primary"
          size="sm"
          :loading="submitting"
          :disabled="submitting"
          @click="save"
        >
          Create
        </Button>
      </div>
    </div>
  </GestureCreateLayout>
</template>

<style scoped>
/* Sortable's ghostClass: keep the slot's gap but show no leftover card. */
.seal-ghost {
  opacity: 0;
}
</style>
