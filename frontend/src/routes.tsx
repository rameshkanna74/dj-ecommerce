import { createBrowserRouter, type RouteObject } from "react-router"

import { GuestOnly, isCustomer, isPlatformAdmin, isVendor, RequireAuth } from "@/components/common/guards"
import { StoreLayout } from "@/components/layout/layouts"
import { RouteError } from "@/features/misc/route-error"
import { page } from "@/lib/lazy-page"
import { staffRoutes } from "@/features/staff/routes"
import { vendorRoutes } from "@/features/vendor/routes"

const routes: RouteObject[] = [
  {
    errorElement: <RouteError />,
    children: [
      {
        element: <StoreLayout />,
        children: [
          { index: true, ...page(() => import("@/features/catalog/home-page")) },
          { path: "products", ...page(() => import("@/features/catalog/products-page")) },
          { path: "products/:slug", ...page(() => import("@/features/catalog/product-page")) },
          { path: "stores", ...page(() => import("@/features/catalog/stores-page")) },
          { path: "stores/:slug", ...page(() => import("@/features/catalog/store-page")) },
          {
            element: <GuestOnly />,
            children: [
              { path: "login", ...page(() => import("@/features/auth/login-page")) },
              { path: "register", ...page(() => import("@/features/auth/register-page")) },
            ],
          },
          { path: "forgot-password", ...page(() => import("@/features/auth/forgot-password-page")) },
          // Must match the link in the API password-reset email: {CORECART_FRONTEND_URL}/reset-password?uid=&token=
          { path: "reset-password", ...page(() => import("@/features/auth/reset-password-page")) },
          {
            element: <RequireAuth allow={isCustomer} />,
            children: [
              { path: "cart", ...page(() => import("@/features/cart/cart-page")) },
              { path: "checkout", ...page(() => import("@/features/checkout/checkout-page")) },
              { path: "checkout/success/:orderNumber", ...page(() => import("@/features/checkout/success-page")) },
            ],
          },
          { path: "*", ...page(() => import("@/features/misc/not-found-page")) },
        ],
      },
      {
        path: "account",
        element: <RequireAuth />,
        children: [
          {
            ...page(() => import("@/features/account/account-layout")),
            children: [
              { index: true, ...page(() => import("@/features/account/profile-page")) },
              { path: "security", ...page(() => import("@/features/account/security-page")) },
              {
                element: <RequireAuth allow={isCustomer} />,
                children: [
                  { path: "orders", ...page(() => import("@/features/account/orders-page")) },
                  { path: "orders/:orderNumber", ...page(() => import("@/features/account/order-page")) },
                  { path: "wishlist", ...page(() => import("@/features/account/wishlist-page")) },
                ],
              },
              { path: "support", ...page(() => import("@/features/account/support-page")) },
              { path: "support/:id", ...page(() => import("@/features/account/ticket-page")) },
            ],
          },
        ],
      },
      { path: "vendor", element: <RequireAuth allow={isVendor} />, children: vendorRoutes },
      { path: "staff", element: <RequireAuth allow={isPlatformAdmin} />, children: staffRoutes },
    ],
  },
]

export const router = createBrowserRouter(routes)
