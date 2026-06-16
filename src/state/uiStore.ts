import { useEffect, useState } from 'react'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ColorMode } from '../theme'

type UiStore = {
  // null = follow the OS setting; an explicit value = a user override that
  // persists across reloads (see partialize below).
  modePref: ColorMode | null
  setMode(mode: ColorMode): void
  clearMode(): void
}

export const useUiStore = create<UiStore>()(
  persist(
    (set) => ({
      modePref: null,
      setMode: (mode) => set({ modePref: mode }),
      clearMode: () => set({ modePref: null }),
    }),
    {
      name: 'app.ui.v1',
      partialize: (s) => ({ modePref: s.modePref }),
    },
  ),
)

function systemColorMode(): ColorMode {
  if (typeof window === 'undefined' || !window.matchMedia) return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/**
 * Resolved color mode: the user's saved choice if they've made one, otherwise
 * whatever the OS reports — and it tracks live OS changes until they override.
 */
export function useColorMode(): {
  mode: ColorMode
  isExplicit: boolean
  toggle(): void
} {
  const pref = useUiStore((s) => s.modePref)
  const setMode = useUiStore((s) => s.setMode)

  const [system, setSystem] = useState<ColorMode>(systemColorMode)
  useEffect(() => {
    if (!window.matchMedia) return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setSystem(mq.matches ? 'dark' : 'light')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const mode = pref ?? system
  return {
    mode,
    isExplicit: pref !== null,
    toggle: () => setMode(mode === 'dark' ? 'light' : 'dark'),
  }
}
