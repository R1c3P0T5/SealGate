import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Gesture = {
  id: string
  jstsu: string
}

// Fixed palette of hand signs (romaji), matching the backend SIGN_KANJI domain
// and the image filenames under public/img/gestures/.
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

export const useGesturesStore = defineStore('gestures', () => {
  const library = ref<Gesture[]>(LIBRARY)
  return { library }
})
