import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Gesture = {
  id: string
  jstsu: string
}

export type GestureSequence = {
  id: string
  name: string
  steps: string[]
  createdAt: string
  updatedAt: string
}

const JSTSU_NAMES = [
  'ne',
  'ushi',
  'tora',
  'u',
  'tatsu',
  'mi',
  'uma',
  'hitsuji',
  'saru',
  'tori',
  'inu',
  'i',
]

const LIBRARY: Gesture[] = JSTSU_NAMES.map((jstsu) => ({ id: jstsu, jstsu }))

export function gestureImageUrl(jstsu: string): string {
  return `/img/gestures/${jstsu}.jpg`
}

function newId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `seq-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export const useGesturesStore = defineStore('gestures', () => {
  const library = ref<Gesture[]>(LIBRARY)
  const sequences = ref<GestureSequence[]>([])

  function findGesture(id: string): Gesture | null {
    return library.value.find((g) => g.id === id) ?? null
  }

  function findSequence(id: string): GestureSequence | null {
    return sequences.value.find((s) => s.id === id) ?? null
  }

  function createSequence(name: string, steps: string[]): GestureSequence {
    const now = new Date().toISOString()
    const seq: GestureSequence = {
      id: newId(),
      name,
      steps: [...steps],
      createdAt: now,
      updatedAt: now,
    }
    sequences.value.push(seq)
    return seq
  }

  function updateSequence(
    id: string,
    updates: { name?: string; steps?: string[] },
  ): GestureSequence | null {
    const seq = findSequence(id)
    if (!seq) return null
    if (updates.name !== undefined) seq.name = updates.name
    if (updates.steps !== undefined) seq.steps = [...updates.steps]
    seq.updatedAt = new Date().toISOString()
    return seq
  }

  function deleteSequence(id: string): boolean {
    const idx = sequences.value.findIndex((s) => s.id === id)
    if (idx < 0) return false
    sequences.value.splice(idx, 1)
    return true
  }

  return {
    library,
    sequences,
    findGesture,
    findSequence,
    createSequence,
    updateSequence,
    deleteSequence,
  }
})
