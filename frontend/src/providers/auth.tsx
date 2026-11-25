import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from "react"

import { api, ApiError, hasSessionHint, refreshAccessToken, setAccessToken, unwrap, XHR_HEADER, type Schemas } from "@/api/client"

export type User = Schemas["User"]
type Role = User["role"]

interface AuthContextValue {
  user: User | null
  /** True until the initial silent refresh has finished. */
  initializing: boolean
  login: (username: string, password: string) => Promise<User>
  /** Store tokens returned by a registration endpoint and load the user. */
  acceptTokens: (access: string) => Promise<User>
  logout: () => Promise<void>
  hasRole: (...roles: Role[]) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)
export const ME_KEY = ["me"] as const

async function fetchMe() {
  return unwrap(api.GET("/api/v1/me/"))
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  // No session hint = never signed in on this browser: skip the silent refresh entirely.
  const [booted, setBooted] = useState(() => !hasSessionHint())
  const [signedIn, setSignedIn] = useState(false)

  // Silent sign-in from the httpOnly refresh cookie on first load.
  useEffect(() => {
    if (booted) return
    refreshAccessToken().then((ok) => {
      setSignedIn(ok)
      setBooted(true)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, [])

  const me = useQuery({ queryKey: ME_KEY, queryFn: fetchMe, enabled: signedIn, staleTime: 5 * 60_000 })
  const user = signedIn ? (me.data ?? null) : null

  const acceptTokens = useCallback(
    async (access: string) => {
      setAccessToken(access)
      const fresh = await queryClient.fetchQuery({ queryKey: ME_KEY, queryFn: fetchMe })
      setSignedIn(true)
      // Cart, wishlist etc. belong to the new user.
      queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== ME_KEY[0] })
      return fresh
    },
    [queryClient],
  )

  const login = useCallback(
    async (username: string, password: string) => {
      const res = await fetch("/api/v1/auth/token/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, use_cookie: true }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new ApiError(res.status, body)
      return acceptTokens((body as { access: string }).access)
    },
    [acceptTokens],
  )

  const logout = useCallback(async () => {
    await fetch("/api/v1/auth/logout/", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...XHR_HEADER },
      body: "{}",
    }).catch(() => undefined)
    setAccessToken(null)
    setSignedIn(false)
    queryClient.clear()
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      initializing: !booted || (signedIn && me.isPending),
      login,
      acceptTokens,
      logout,
      hasRole: (...roles) => Boolean(user && roles.includes(user.role)),
    }),
    [user, booted, signedIn, me.isPending, login, acceptTokens, logout],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth() {
  const ctx = use(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>")
  return ctx
}
