import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query"
import { toast } from "sonner"

import { api, ApiError, unwrap, type Schemas } from "@/api/client"
import { errorMessage } from "@/components/common/states"

export type StaffVendor = Schemas["StaffVendor"]
export type StaffProduct = Schemas["StaffProduct"]
export type StaffReview = Schemas["StaffReview"]
export type StaffUser = Schemas["StaffUser"]
export type StaffCategory = Schemas["StaffCategory"]
export type StaffTicket = Schemas["StaffTicket"]
export type Coupon = Schemas["Coupon"]
export type OrderSummary = Schemas["OrderSummary"]
export type OrderDetail = Schemas["OrderDetail"]
export type ItemStatus = Schemas["OrderStatusEnum"]

/** GET /staff/dashboard/ (an untyped dict in the schema; see analytics/api.py). */
export interface AdminDashboard {
  days: number
  kpis: {
    customers: number
    vendors: number
    pending_vendors: number
    products: number
    active_products: number
    out_of_stock: number
    orders: number
    pending_orders: number
    awaiting_payment: number
    revenue: string
    paid_orders: number
    avg_order_value: string
  }
  category_count: number
  sales_trend: { label: string; value: string | number }[]
  top_products: { product_id: number; product_name: string; units: number; revenue: string | number }[]
  category_performance: { label: string; value: string | number; units: number }[]
  recent_orders: OrderSummary[]
  pending_vendors: { id: number; business_name: string; email: string; created_at: string }[]
  low_stock_products: { id: number; name: string; slug: string; stock: number; vendor: string | null }[]
}

type Query = Record<string, string | number | boolean | undefined>
/** Several staff list filters (q, payment_status, low_stock, ...) are not declared in the schema. */
const q = (query: Query) => ({ query: query as never })

export function onError(err: unknown) {
  if (!(err instanceof ApiError && Object.keys(err.fields).length)) toast.error(errorMessage(err))
}

function useStaffMutation<V, R>(fn: (vars: V) => Promise<R>, invalidate: QueryKey[], success?: string | ((r: R) => string)) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (result) => {
      invalidate.forEach((queryKey) => qc.invalidateQueries({ queryKey }))
      qc.invalidateQueries({ queryKey: ["staff", "dashboard"] })
      if (success) toast.success(typeof success === "function" ? success(result) : success)
    },
    onError,
  })
}

// ---- dashboard -----------------------------------------------------------------
export function useAdminDashboard(days: number) {
  return useQuery({
    queryKey: ["staff", "dashboard", days],
    queryFn: async () =>
      (await unwrap(api.GET("/api/v1/staff/dashboard/", { params: { query: { days: days as 7 | 30 | 90 } } }))) as unknown as AdminDashboard,
    placeholderData: keepPreviousData,
  })
}

// ---- vendors ---------------------------------------------------------------------
export function useStaffVendors(query: Query) {
  return useQuery({
    queryKey: ["staff", "vendors", query],
    queryFn: () => unwrap(api.GET("/api/v1/staff/vendors/", { params: q(query) })),
    placeholderData: keepPreviousData,
  })
}

export function useVendorAction() {
  return useStaffMutation(
    ({ id, action, reason = "" }: { id: number; action: "approve" | "reject" | "suspend"; reason?: string }) => {
      const path = { params: { path: { id } } }
      if (action === "approve") return unwrap(api.POST("/api/v1/staff/vendors/{id}/approve/", path))
      if (action === "reject") return unwrap(api.POST("/api/v1/staff/vendors/{id}/reject/", { ...path, body: { reason } }))
      return unwrap(api.POST("/api/v1/staff/vendors/{id}/suspend/", { ...path, body: { reason } }))
    },
    [["staff", "vendors"]],
    (v) => `${v.business_name}: ${v.approval_status}`,
  )
}

export function useUpdateVendor() {
  return useStaffMutation(
    ({ id, commission_rate }: { id: number; commission_rate: string }) =>
      unwrap(api.PATCH("/api/v1/staff/vendors/{id}/", { params: { path: { id } }, body: { commission_rate } })),
    [["staff", "vendors"]],
    "Commission updated",
  )
}

// ---- orders ------------------------------------------------------------------------
export function useStaffOrders(query: Query) {
  return useQuery({
    queryKey: ["staff", "orders", query],
    queryFn: () => unwrap(api.GET("/api/v1/staff/orders/", { params: q(query) })),
    placeholderData: keepPreviousData,
  })
}

export function useStaffOrder(orderNumber: string) {
  return useQuery({
    queryKey: ["staff", "order", orderNumber],
    queryFn: () => unwrap(api.GET("/api/v1/staff/orders/{order_number}/", { params: { path: { order_number: orderNumber } } })),
  })
}

export function useOrderAction(orderNumber: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ action, text = "" }: { action: "mark-paid" | "refund" | "cancel"; text?: string }) => {
      const path = { params: { path: { order_number: orderNumber } } }
      if (action === "mark-paid")
        return unwrap(api.POST("/api/v1/staff/orders/{order_number}/mark-paid/", { ...path, body: { reference: text } }))
      if (action === "refund")
        return unwrap(api.POST("/api/v1/staff/orders/{order_number}/refund/", { ...path, body: { reason: text } }))
      return unwrap(api.POST("/api/v1/staff/orders/{order_number}/cancel/", { ...path, body: { reason: text } }))
    },
    onSuccess: (order, { action }) => {
      qc.setQueryData(["staff", "order", orderNumber], order)
      qc.invalidateQueries({ queryKey: ["staff", "orders"] })
      qc.invalidateQueries({ queryKey: ["staff", "dashboard"] })
      toast.success({ "mark-paid": "Marked as paid", refund: "Marked as refunded", cancel: "Order cancelled" }[action])
    },
    onError,
  })
}

export function useStaffItemStatus(orderNumber: string) {
  return useStaffMutation(
    ({ id, status, tracking_number = "" }: { id: number; status: ItemStatus; tracking_number?: string }) =>
      unwrap(api.POST("/api/v1/staff/order-items/{id}/status/", { params: { path: { id } }, body: { status, tracking_number } })),
    [["staff", "order", orderNumber], ["staff", "orders"]],
    (item) => `${item.product_name} → ${item.status_display}`,
  )
}

// ---- catalogue, reviews, users -------------------------------------------------------
export function useStaffProducts(query: Query) {
  return useQuery({
    queryKey: ["staff", "products", query],
    queryFn: () => unwrap(api.GET("/api/v1/staff/products/", { params: q(query) })),
    placeholderData: keepPreviousData,
  })
}

export function useUpdateStaffProduct() {
  return useStaffMutation(
    ({ id, ...body }: { id: number; is_active?: boolean; is_featured?: boolean }) =>
      unwrap(api.PATCH("/api/v1/staff/products/{id}/", { params: { path: { id } }, body })),
    [["staff", "products"]],
  )
}

export function useStaffReviews(query: Query) {
  return useQuery({
    queryKey: ["staff", "reviews", query],
    queryFn: () => unwrap(api.GET("/api/v1/staff/reviews/", { params: q(query) })),
    placeholderData: keepPreviousData,
  })
}

export function useModerateReview() {
  return useStaffMutation(
    ({ id, is_visible }: { id: number; is_visible: boolean }) =>
      unwrap(api.PATCH("/api/v1/staff/reviews/{id}/", { params: { path: { id } }, body: { is_visible } })),
    [["staff", "reviews"]],
    (r) => (r.is_visible ? "Review restored" : "Review hidden"),
  )
}

export function useStaffUsers(query: Query) {
  return useQuery({
    queryKey: ["staff", "users", query],
    queryFn: () => unwrap(api.GET("/api/v1/staff/users/", { params: q(query) })),
    placeholderData: keepPreviousData,
  })
}

export function useSetUserActive() {
  return useStaffMutation(
    ({ id, is_active }: { id: number; is_active: boolean }) =>
      unwrap(api.PATCH("/api/v1/staff/users/{id}/", { params: { path: { id } }, body: { is_active } })),
    [["staff", "users"]],
    (u) => `${u.username} ${u.is_active ? "activated" : "deactivated"}`,
  )
}

// ---- coupons & categories ---------------------------------------------------------------
export function useCoupons(page: number) {
  return useQuery({
    queryKey: ["staff", "coupons", page],
    queryFn: () => unwrap(api.GET("/api/v1/staff/coupons/", { params: q({ page }) })),
    placeholderData: keepPreviousData,
  })
}

export type CouponInput = Omit<Coupon, "id" | "used_count">

export function useSaveCoupon() {
  return useStaffMutation(
    ({ id, ...body }: Partial<CouponInput> & { id?: number }) =>
      id
        ? unwrap(api.PATCH("/api/v1/staff/coupons/{id}/", { params: { path: { id } }, body }))
        : unwrap(api.POST("/api/v1/staff/coupons/", { body: body as CouponInput })),
    [["staff", "coupons"]],
    (c) => `Coupon ${c.code} saved`,
  )
}

export function useDeleteCoupon() {
  return useStaffMutation(
    (id: number) => unwrap(api.DELETE("/api/v1/staff/coupons/{id}/", { params: { path: { id } } })),
    [["staff", "coupons"]],
    "Coupon deleted",
  )
}

export function useStaffCategories(page: number) {
  return useQuery({
    queryKey: ["staff", "categories", page],
    queryFn: () => unwrap(api.GET("/api/v1/staff/categories/", { params: q({ page }) })),
    placeholderData: keepPreviousData,
  })
}

export function useSaveCategory() {
  const qc = useQueryClient()
  return useStaffMutation(
    async ({ id, ...body }: { id?: number; name: string; description: string; is_active: boolean }) => {
      const saved = id
        ? await unwrap(api.PATCH("/api/v1/staff/categories/{id}/", { params: { path: { id } }, body }))
        : await unwrap(api.POST("/api/v1/staff/categories/", { body }))
      qc.invalidateQueries({ queryKey: ["categories"] }) // storefront menu
      return saved
    },
    [["staff", "categories"]],
    (c) => `Category ${c.name} saved`,
  )
}

export function useDeleteCategory() {
  return useStaffMutation(
    (id: number) => unwrap(api.DELETE("/api/v1/staff/categories/{id}/", { params: { path: { id } } })),
    [["staff", "categories"], ["categories"]],
    "Category deleted",
  )
}

// ---- support ------------------------------------------------------------------------------
export function useStaffTickets(query: Query) {
  return useQuery({
    queryKey: ["staff", "tickets", query],
    queryFn: () => unwrap(api.GET("/api/v1/staff/tickets/", { params: q(query) })),
    placeholderData: keepPreviousData,
  })
}

export function useStaffTicket(id: number) {
  return useQuery({
    queryKey: ["staff", "ticket", id],
    queryFn: () => unwrap(api.GET("/api/v1/staff/tickets/{id}/", { params: { path: { id } } })),
  })
}

export function useRespondTicket(id: number) {
  return useStaffMutation(
    (body: { body: string; status: Schemas["TicketStatusEnum"] | "" }) =>
      unwrap(api.POST("/api/v1/staff/tickets/{id}/respond/", { params: { path: { id } }, body })),
    [["staff", "ticket", id], ["staff", "tickets"]],
    "Response sent",
  )
}
