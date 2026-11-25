import { FolderTreeIcon, LayoutDashboardIcon, LifeBuoyIcon, PackageIcon, ShoppingCartIcon, StarIcon, StoreIcon, TicketPercentIcon, UsersIcon } from "lucide-react"
import type { RouteObject } from "react-router"

import { PortalLayout, type NavItem } from "@/components/layout/layouts"
import { page } from "@/lib/lazy-page"

const NAV: NavItem[] = [
  { to: "/staff", label: "Dashboard", icon: LayoutDashboardIcon, end: true },
  { to: "/staff/orders", label: "Orders", icon: ShoppingCartIcon },
  { to: "/staff/vendors", label: "Vendors", icon: StoreIcon },
  { to: "/staff/products", label: "Products", icon: PackageIcon },
  { to: "/staff/reviews", label: "Reviews", icon: StarIcon },
  { to: "/staff/users", label: "Users", icon: UsersIcon },
  { to: "/staff/coupons", label: "Coupons", icon: TicketPercentIcon },
  { to: "/staff/categories", label: "Categories", icon: FolderTreeIcon },
  { to: "/staff/support", label: "Support", icon: LifeBuoyIcon },
]

// Admin console, mounted at /staff behind RequireAuth(isPlatformAdmin).
export const staffRoutes: RouteObject[] = [
  {
    element: <PortalLayout title="Admin" items={NAV} />,
    children: [
      { index: true, ...page(() => import("./dashboard-page")) },
      { path: "orders", ...page(() => import("./orders-page")) },
      { path: "orders/:orderNumber", ...page(() => import("./order-page")) },
      { path: "vendors", ...page(() => import("./vendors-page")) },
      { path: "products", ...page(() => import("./products-page")) },
      { path: "reviews", ...page(() => import("./reviews-page")) },
      { path: "users", ...page(() => import("./users-page")) },
      { path: "coupons", ...page(() => import("./coupons-page")) },
      { path: "categories", ...page(() => import("./categories-page")) },
      { path: "support", ...page(() => import("./tickets-page")) },
      { path: "support/:id", ...page(() => import("./ticket-page")) },
    ],
  },
]
