import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api, ApiError, unwrap, type Schemas } from "@/api/client"
import { errorMessage } from "@/components/common/states"

export type VendorProduct = Schemas["VendorProduct"]
export type VendorOrderItem = Schemas["VendorOrderItem"]
export type VendorOrder = Schemas["VendorOrder"]
export type Variant = Schemas["Variant"]
export type ProductImage = Schemas["ProductImage"]
export type ItemStatus = Schemas["OrderStatusEnum"]

/** Shape of GET /vendor/dashboard/ (an untyped dict in the schema; see analytics/api.py). */
export interface VendorDashboard {
  days: number
  commission_rate: string
  kpis: {
    total_products: number
    active_products: number
    out_of_stock: number
    total_orders: number
    pending_orders: number
    items_to_fulfil: number
    units_sold: number
    gross_sales: string
    recognised_sales: string
    revenue: string
    average_rating: number
    review_count: number
  }
  sales_trend: { label: string; value: string | number }[]
  best_sellers: { label: string; value: string | number; units: number }[]
}

const keys = {
  dashboard: (days: number) => ["vendor", "dashboard", days] as const,
  products: (params: object) => ["vendor", "products", params] as const,
  product: (id: number) => ["vendor", "product", id] as const,
  items: (params: object) => ["vendor", "items", params] as const,
  order: (n: string) => ["vendor", "order", n] as const,
  reviews: (params: object) => ["vendor", "reviews", params] as const,
  questions: (page: number) => ["vendor", "questions", page] as const,
}

/** Toast API failures that are not field validation errors (those render inline). */
export function toastUnlessFieldErrors(err: unknown) {
  if (!(err instanceof ApiError && Object.keys(err.fields).length)) toast.error(errorMessage(err))
}

// ---- application / dashboard ----------------------------------------------
export function useApplication() {
  return useQuery({ queryKey: ["vendor", "application"], queryFn: () => unwrap(api.GET("/api/v1/vendor/application/")) })
}

export function useVendorDashboard(days: number) {
  return useQuery({
    queryKey: keys.dashboard(days),
    queryFn: async () =>
      (await unwrap(api.GET("/api/v1/vendor/dashboard/", { params: { query: { days: days as 7 | 30 | 90 } } }))) as unknown as VendorDashboard,
    placeholderData: keepPreviousData,
  })
}

// ---- products ---------------------------------------------------------------
export function useVendorProducts(params: { page: number; q?: string; status?: "active" | "inactive" }) {
  return useQuery({
    queryKey: keys.products(params),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/vendor/products/", {
          params: { query: params as { page: number } },
        }),
      ),
    placeholderData: keepPreviousData,
  })
}

export function useVendorProduct(id: number | null) {
  return useQuery({
    queryKey: keys.product(id ?? 0),
    queryFn: () => unwrap(api.GET("/api/v1/vendor/products/{id}/", { params: { path: { id: id! } } })),
    enabled: id !== null,
  })
}

function useInvalidateProducts() {
  const qc = useQueryClient()
  return (id?: number) => {
    qc.invalidateQueries({ queryKey: ["vendor", "products"] })
    qc.invalidateQueries({ queryKey: ["vendor", "dashboard"] })
    if (id) qc.invalidateQueries({ queryKey: keys.product(id) })
  }
}

export type ProductInput = Pick<VendorProduct, "name" | "category" | "description" | "price" | "stock" | "is_active">

export function useSaveProduct(id: number | null) {
  const invalidate = useInvalidateProducts()
  return useMutation({
    mutationFn: (body: Partial<ProductInput>) =>
      id
        ? unwrap(api.PATCH("/api/v1/vendor/products/{id}/", { params: { path: { id } }, body }))
        : unwrap(api.POST("/api/v1/vendor/products/", { body: body as ProductInput })),
    onSuccess: (product) => invalidate(product.id),
    onError: toastUnlessFieldErrors,
  })
}

export function useUploadCover(id: number) {
  const invalidate = useInvalidateProducts()
  return useMutation({
    mutationFn: (file: File | null) => {
      const form = new FormData()
      form.append("cover_image", file ?? "")
      return unwrap(
        api.PATCH("/api/v1/vendor/products/{id}/", {
          params: { path: { id } },
          body: form as never,
          bodySerializer: (b) => b as unknown as FormData,
        }),
      )
    },
    onSuccess: () => invalidate(id),
    onError: (err) => toast.error(err instanceof ApiError ? err.fields.cover_image || err.message : errorMessage(err)),
  })
}

export function useDeleteProduct() {
  const invalidate = useInvalidateProducts()
  return useMutation({
    mutationFn: async (id: number) => {
      const { data, response, error } = await api.DELETE("/api/v1/vendor/products/{id}/", { params: { path: { id } } })
      if (!response.ok) throw new ApiError(response.status, error)
      // 200 + hidden_instead: the product had orders, so the API deactivated it.
      return (data as { detail?: string } | undefined)?.detail ?? null
    },
    onSuccess: (detail) => {
      invalidate()
      toast.success(detail ?? "Product deleted")
    },
    onError: (err) => toast.error(errorMessage(err)),
  })
}

// ---- variants & images --------------------------------------------------------
export type VariantInput = Pick<Variant, "attribute_name" | "attribute_value" | "price_override" | "stock" | "is_active">

export function useSaveVariant(productId: number) {
  const invalidate = useInvalidateProducts()
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<VariantInput> & { id?: number }) =>
      id
        ? unwrap(api.PATCH("/api/v1/vendor/products/{product_pk}/variants/{id}/", { params: { path: { product_pk: productId, id } }, body }))
        : unwrap(api.POST("/api/v1/vendor/products/{product_pk}/variants/", { params: { path: { product_pk: productId } }, body: body as VariantInput })),
    onSuccess: () => invalidate(productId),
  })
}

export function useDeleteVariant(productId: number) {
  const invalidate = useInvalidateProducts()
  return useMutation({
    mutationFn: (id: number) =>
      unwrap(api.DELETE("/api/v1/vendor/products/{product_pk}/variants/{id}/", { params: { path: { product_pk: productId, id } } })),
    onSuccess: () => {
      invalidate(productId)
      toast.success("Option deleted")
    },
    onError: (err) =>
      toast.error(
        err instanceof ApiError && err.status === 409
          ? "This option has been ordered, so it can’t be deleted. Turn it off instead."
          : errorMessage(err),
      ),
  })
}

export function useUploadImage(productId: number) {
  const invalidate = useInvalidateProducts()
  return useMutation({
    mutationFn: ({ file, alt_text, position }: { file: File; alt_text: string; position: number }) => {
      const form = new FormData()
      form.append("image", file)
      form.append("alt_text", alt_text)
      form.append("position", String(position))
      return unwrap(
        api.POST("/api/v1/vendor/products/{product_pk}/images/", {
          params: { path: { product_pk: productId } },
          body: form as never,
          bodySerializer: (b) => b as unknown as FormData,
        }),
      )
    },
    onSuccess: () => invalidate(productId),
    onError: (err) => toast.error(err instanceof ApiError ? err.fields.image || err.message : errorMessage(err)),
  })
}

export function useUpdateImage(productId: number) {
  const invalidate = useInvalidateProducts()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; alt_text?: string; position?: number }) =>
      unwrap(api.PATCH("/api/v1/vendor/products/{product_pk}/images/{id}/", { params: { path: { product_pk: productId, id } }, body })),
    onSuccess: () => invalidate(productId),
    onError: (err) => toast.error(errorMessage(err)),
  })
}

export function useDeleteImage(productId: number) {
  const invalidate = useInvalidateProducts()
  return useMutation({
    mutationFn: (id: number) =>
      unwrap(api.DELETE("/api/v1/vendor/products/{product_pk}/images/{id}/", { params: { path: { product_pk: productId, id } } })),
    onSuccess: () => invalidate(productId),
    onError: (err) => toast.error(errorMessage(err)),
  })
}

// ---- orders -----------------------------------------------------------------
export function useVendorItems(params: { page: number; status?: ItemStatus; q?: string }) {
  return useQuery({
    queryKey: keys.items(params),
    queryFn: () => unwrap(api.GET("/api/v1/vendor/order-items/", { params: { query: params } })),
    placeholderData: keepPreviousData,
  })
}

export function useVendorOrder(orderNumber: string) {
  return useQuery({
    queryKey: keys.order(orderNumber),
    queryFn: () => unwrap(api.GET("/api/v1/vendor/orders/{order_number}/", { params: { path: { order_number: orderNumber } } })),
  })
}

export function useSetItemStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status, tracking_number = "" }: { id: number; status: ItemStatus; tracking_number?: string }) =>
      unwrap(api.POST("/api/v1/vendor/order-items/{id}/status/", { params: { path: { id } }, body: { status, tracking_number } })),
    onSuccess: (item) => {
      qc.invalidateQueries({ queryKey: ["vendor", "items"] })
      qc.invalidateQueries({ queryKey: keys.order(item.order_number) })
      qc.invalidateQueries({ queryKey: ["vendor", "dashboard"] })
      toast.success(`${item.product_name} marked ${item.status_display.toLowerCase()}`)
    },
    onError: (err) => toast.error(errorMessage(err)),
  })
}

// ---- reviews & questions ------------------------------------------------------
export function useVendorReviews(params: { page: number; rating?: number }) {
  return useQuery({
    queryKey: keys.reviews(params),
    queryFn: () => unwrap(api.GET("/api/v1/vendor/reviews/", { params: { query: params as { page: number } } })),
    placeholderData: keepPreviousData,
  })
}

export function useVendorQuestions(page: number) {
  return useQuery({
    queryKey: keys.questions(page),
    queryFn: () => unwrap(api.GET("/api/v1/vendor/questions/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  })
}

export function useAnswerQuestion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, answer }: { id: number; answer: string }) =>
      unwrap(api.POST("/api/v1/vendor/questions/{id}/answer/", { params: { path: { id } }, body: { answer } })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vendor", "questions"] })
      toast.success("Answer published")
    },
    onError: toastUnlessFieldErrors,
  })
}
