import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, type PropsWithChildren } from 'react'
import { getCurrentUser, loginAccount, logoutAccount, registerAccount, type UserAccount } from '../lib/api'

interface AuthState {
  user: UserAccount | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient()
  const current = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUser,
    retry: false,
    staleTime: 60_000,
  })

  async function login(email: string, password: string) {
    const result = await loginAccount(email, password)
    queryClient.setQueryData(['current-user'], result)
  }

  async function register(email: string, password: string, displayName: string) {
    const result = await registerAccount(email, password, displayName)
    queryClient.setQueryData(['current-user'], result)
  }

  async function logout() {
    await logoutAccount()
    queryClient.setQueryData(['current-user'], null)
    queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'current-user' })
  }

  async function refresh() {
    await current.refetch()
  }

  return <AuthContext.Provider value={{ user: current.data?.user ?? null, loading: current.isLoading, login, register, logout, refresh }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider 未挂载')
  return value
}
