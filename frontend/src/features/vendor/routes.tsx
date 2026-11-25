import type { RouteObject } from "react-router"

import { page } from "@/lib/lazy-page"

// Vendor portal, mounted at /vendor behind RequireAuth(isVendor). The layout gates every
// page on the vendor's approval status (the API returns 403 until approved).
export const vendorRoutes: RouteObject[] = [
  {
    ...page(() => import("./vendor-layout")),
    children: [
      { index: true, ...page(() => import("./dashboard-page")) },
      { path: "products", ...page(() => import("./products-page")) },
      { path: "products/new", ...page(() => import("./product-editor-page")) },
      { path: "products/:id", ...page(() => import("./product-editor-page")) },
      { path: "orders", ...page(() => import("./orders-page")) },
      { path: "orders/:orderNumber", ...page(() => import("./order-page")) },
      { path: "reviews", ...page(() => import("./reviews-page")) },
      { path: "questions", ...page(() => import("./questions-page")) },
    ],
  },
]
