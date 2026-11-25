import type { ReactNode } from "react"
import { Navigate, Outlet, useLocation } from "react-router"

import { PageLoader } from "@/components/common/states"
import { useAuth, type User } from "@/providers/auth"

type Check = (user: User) => boolean

export const isCustomer: Check = (u) => u.role === "customer"
export const isVendor: Check = (u) => u.role === "vendor"
export const isPlatformAdmin: Check = (u) => u.is_platform_admin

/**
 * Route guard. Anonymous users go to /login?next=<here>. Signed-in users who fail
 * ``allow`` go home (the API would 403 anyway; this just avoids a broken page).
 */
export function RequireAuth({ allow, children }: { allow?: Check; children?: ReactNode }) {
  const { user, initializing } = useAuth()
  const location = useLocation()
  if (initializing) return <PageLoader />
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  if (allow && !allow(user)) return <Navigate to="/" replace />
  return children ?? <Outlet />
}

/** For /login and /register: signed-in users are sent on. */
export function GuestOnly({ children }: { children?: ReactNode }) {
  const { user, initializing } = useAuth()
  if (initializing) return <PageLoader />
  if (user) return <Navigate to={homeFor(user)} replace />
  return children ?? <Outlet />
}

export function homeFor(user: User) {
  if (user.is_platform_admin) return "/staff"
  if (user.role === "vendor") return "/vendor"
  return "/"
}

/** Only allow same-site relative redirects (``?next=``) to prevent open redirects. */
export function safeNext(next: string | null, fallback = "/") {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : fallback
}
