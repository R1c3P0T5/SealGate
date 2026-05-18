import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { LoginResponse } from '../../api/types.gen'
import { useAuthStore } from '../auth'

vi.mock('../../api/sdk.gen', () => ({
  loginApiAuthLoginPost: vi.fn<() => Promise<{ data: LoginResponse; error: undefined }>>(),
}))

vi.mock('../../api/client.gen', () => ({ client: { setConfig: vi.fn<() => void>() } }))

import { loginApiAuthLoginPost } from '../../api/sdk.gen'

describe('useAuthStore', () => {
  const mockLoginResponse: { data: LoginResponse; error: undefined } = {
    data: {
      access_token: 'tok123',
      token_type: 'bearer',
      user: {
        id: '1',
        username: 'alice',
        full_name: 'Alice',
        role_name: 'user',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      },
    },
    error: undefined,
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('starts unauthenticated', () => {
    const store = useAuthStore()
    expect(store.token).toBeNull()
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })

  it('login sets token and user', async () => {
    vi.mocked(loginApiAuthLoginPost).mockResolvedValueOnce(mockLoginResponse)
    const store = useAuthStore()
    await store.login('alice', 'pass')
    expect(store.token).toBe('tok123')
    expect(store.user?.username).toBe('alice')
    expect(store.isAuthenticated).toBe(true)
  })

  it('login persists to localStorage', async () => {
    vi.mocked(loginApiAuthLoginPost).mockResolvedValueOnce(mockLoginResponse)
    const store = useAuthStore()
    await store.login('alice', 'pass')
    const saved = JSON.parse(localStorage.getItem('faceguard-auth') ?? '{}')
    expect(saved.token).toBe('tok123')
  })

  it('login error leaves state unauthenticated', async () => {
    vi.mocked(loginApiAuthLoginPost).mockRejectedValueOnce(new Error('401'))
    const store = useAuthStore()
    await expect(store.login('alice', 'wrong')).rejects.toThrow('401')
    expect(store.isAuthenticated).toBe(false)
  })

  it('logout clears state and localStorage', async () => {
    vi.mocked(loginApiAuthLoginPost).mockResolvedValueOnce(mockLoginResponse)
    const store = useAuthStore()
    await store.login('alice', 'pass')
    store.logout()
    expect(store.token).toBeNull()
    expect(store.user).toBeNull()
    expect(localStorage.getItem('faceguard-auth')).toBeNull()
  })

  it('restore loads token and user from localStorage', () => {
    localStorage.setItem(
      'faceguard-auth',
      JSON.stringify({
        token: 'saved-tok',
        user: { id: '2', username: 'bob', email: null, is_active: true },
      }),
    )
    const store = useAuthStore()
    store.restore()
    expect(store.token).toBe('saved-tok')
    expect(store.user?.username).toBe('bob')
  })

  it('restore with no stored data leaves state unauthenticated', () => {
    const store = useAuthStore()
    store.restore()
    expect(store.isAuthenticated).toBe(false)
  })

  it('restore with corrupt JSON leaves state unauthenticated', () => {
    localStorage.setItem('faceguard-auth', 'not-json')
    const store = useAuthStore()
    store.restore()
    expect(store.isAuthenticated).toBe(false)
  })

  it('logout when already logged out does not throw', () => {
    const store = useAuthStore()
    expect(() => store.logout()).not.toThrow()
    expect(store.isAuthenticated).toBe(false)
  })
})
