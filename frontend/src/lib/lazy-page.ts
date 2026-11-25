import type { ComponentType } from "react"
import type { RouteObject } from "react-router"

/** Lazy route helper: every page is its own chunk, so the first load stays small. */
export function page(load: () => Promise<{ default: ComponentType }>): Pick<RouteObject, "lazy"> {
  return { lazy: async () => ({ Component: (await load()).default }) }
}
