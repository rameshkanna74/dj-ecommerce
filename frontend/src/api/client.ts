import createClient from "openapi-fetch"

import type { components, paths } from "./schema"

export type Schemas = components["schemas"]

/**
 * Auth model (see README "Connecting a browser frontend"):
 * - The short-lived access token lives only in memory (never localStorage).
 * - The refresh token is an httpOnly cookie scoped to /api/v1/auth/, set by logging in
 *   with `use_cookie: true`. It is rotated by POST /auth/token/refresh/ which requires
 *   the `X-Requested-With` header (CSRF protection for cookie-based calls).
 * - Any 401 triggers one shared refresh, then the original request is retried once.
 */
let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null
const listeners = new Set<(signedIn: boolean) => void>()

export const XHR_HEADER = { "X-Requested-With": "XMLHttpRequest" }

// A non-secret "this browser has a session" hint. The refresh cookie is httpOnly, so JS can't
// see it; without the hint every first-time visitor would fire a doomed refresh call (a 400).
const SESSION_HINT = "cc-session"

export function hasSessionHint() {
  try {
    return localStorage.getItem(SESSION_HINT) === "1"
  } catch {
    return true // storage blocked: just try the refresh
  }
}

export function setAccessToken(token: string | null) {
  const changed = Boolean(token) !== Boolean(accessToken)
  accessToken = token
  try {
    if (token) localStorage.setItem(SESSION_HINT, "1")
    else localStorage.removeItem(SESSION_HINT)
  } catch {
    /* ignore */
  }
  if (changed) listeners.forEach((fn) => fn(Boolean(token)))
}

export function onAuthChange(fn: (signedIn: boolean) => void) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshAccessToken(): Promise<boolean> {
  refreshing ??= fetch("/api/v1/auth/token/refresh/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...XHR_HEADER },
    body: "{}",
  })
    .then(async (res) => {
      if (!res.ok) {
        setAccessToken(null)
        return false
      }
      const data = (await res.json()) as { access: string }
      setAccessToken(data.access)
      return true
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

const NO_RETRY = ["/api/v1/auth/token/", "/api/v1/auth/logout/"]

async function authFetch(input: Request): Promise<Response> {
  const retry = input.clone()
  const send = (req: Request) => {
    if (accessToken) req.headers.set("Authorization", `Bearer ${accessToken}`)
    return fetch(req, { credentials: "same-origin" })
  }
  const response = await send(input)
  const path = new URL(input.url).pathname
  if (response.status !== 401 || NO_RETRY.some((p) => path.startsWith(p))) return response
  return (await refreshAccessToken()) ? send(retry) : response
}

export const api = createClient<paths>({ baseUrl: "", fetch: authFetch })

// ---------------------------------------------------------------------------
// Errors: DRF returns {"detail","code"} for domain errors and {field: [msgs]} for
// validation errors. `ApiError` normalises both for forms and toasts.
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  status: number
  code?: string
  fields: Record<string, string>

  constructor(status: number, body: unknown) {
    const { message, code, fields } = parseError(body, status)
    super(message)
    this.status = status
    this.code = code
    this.fields = fields
  }
}

function flatten(value: unknown): string {
  if (Array.isArray(value)) return value.map(flatten).join(" ")
  if (value && typeof value === "object") return Object.values(value).map(flatten).join(" ")
  return String(value ?? "")
}

function parseError(body: unknown, status: number) {
  const fields: Record<string, string> = {}
  let message = status === 429 ? "Too many requests. Please slow down and try again." : "Something went wrong."
  let code: string | undefined
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>
    if (typeof record.detail === "string") message = record.detail
    if (typeof record.code === "string") code = record.code
    for (const [key, value] of Object.entries(record)) {
      if (key === "detail" || key === "code") continue
      fields[key] = flatten(value)
    }
    if (!record.detail && fields.non_field_errors) message = fields.non_field_errors
    else if (!record.detail && Object.keys(fields).length) message = "Please check the highlighted fields."
  }
  return { message, code, fields }
}

/** Unwrap an openapi-fetch result: return data or throw an ApiError. */
export async function unwrap<T>(promise: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await promise
  if (!response.ok) throw new ApiError(response.status, error)
  return data as T
}
