import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react'
import { apiBase } from '../lib/apiBase'
import type { Usage } from '../lib/pricing'

export type Role = 'admin' | 'user'

export type User = {
  id: string
  username: string
  role: Role
}

export type UsageReport = Usage & {
  turns: number
  models: Record<string, Usage>
  all_users?: UsageReport | null
}

type AuthState =
  | { status: 'loading' }
  | { status: 'unauthenticated' }
  | { status: 'authenticated'; user: User; usage: UsageReport | null }

type AuthContextValue = {
  state: AuthState
  login(username: string, password: string): Promise<void>
  logout(): Promise<void>
  refreshUsage(): Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

async function fetchUsage(): Promise<UsageReport | null> {
  try {
    const res = await fetch(`${apiBase()}/auth/me/usage`, { credentials: 'include' })
    if (!res.ok) return null
    return (await res.json()) as UsageReport
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading' })

  // Restore the session on mount via /auth/me (the cookie rides along).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${apiBase()}/auth/me`, { credentials: 'include' })
        if (!res.ok) {
          if (!cancelled) setState({ status: 'unauthenticated' })
          return
        }
        const user = (await res.json()) as User
        const usage = await fetchUsage()
        if (!cancelled) setState({ status: 'authenticated', user, usage })
      } catch {
        if (!cancelled) setState({ status: 'unauthenticated' })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${apiBase()}/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      let detail = res.statusText
      try {
        detail = (await res.json()).detail ?? detail
      } catch {
        /* keep statusText */
      }
      throw new Error(detail)
    }
    const user = (await res.json()) as User
    const usage = await fetchUsage()
    setState({ status: 'authenticated', user, usage })
  }, [])

  const logout = useCallback(async () => {
    try {
      await fetch(`${apiBase()}/auth/logout`, { method: 'POST', credentials: 'include' })
    } finally {
      setState({ status: 'unauthenticated' })
    }
  }, [])

  const refreshUsage = useCallback(async () => {
    const usage = await fetchUsage()
    setState((s) => (s.status === 'authenticated' ? { ...s, usage } : s))
  }, [])

  return (
    <AuthContext.Provider value={{ state, login, logout, refreshUsage }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
