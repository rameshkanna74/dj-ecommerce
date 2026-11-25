import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api, unwrap, type Schemas } from "@/api/client"

export type Product = Schemas["ProductList"]
export type ProductDetail = Schemas["ProductDetail"]
export type Variant = Schemas["Variant"]
export type Category = Schemas["Category"]
export type Store = Schemas["Store"]

export type Sort = "newest" | "popular" | "price_asc" | "price_desc" | "rating"

export interface ProductFilters {
  q?: string
  category?: string
  sort?: Sort
  min_price?: number
  max_price?: number
  in_stock?: boolean
  page?: number
  page_size?: number
}

export const catalogKeys = {
  products: (filters: ProductFilters) => ["products", filters] as const,
  product: (slug: string) => ["product", slug] as const,
  reviews: (slug: string, page: number) => ["product", slug, "reviews", page] as const,
  questions: (slug: string, page: number) => ["product", slug, "questions", page] as const,
  categories: ["categories"] as const,
  stores: (page: number) => ["stores", page] as const,
  store: (slug: string) => ["store", slug] as const,
  storeProducts: (slug: string, filters: ProductFilters) => ["store", slug, "products", filters] as const,
}

export function useProducts(filters: ProductFilters) {
  return useQuery({
    queryKey: catalogKeys.products(filters),
    queryFn: () => unwrap(api.GET("/api/v1/products/", { params: { query: filters } })),
    placeholderData: keepPreviousData,
  })
}

export function useProduct(slug: string) {
  return useQuery({
    queryKey: catalogKeys.product(slug),
    queryFn: () => unwrap(api.GET("/api/v1/products/{slug}/", { params: { path: { slug } } })),
  })
}

export function useCategories() {
  return useQuery({
    queryKey: catalogKeys.categories,
    queryFn: () => unwrap(api.GET("/api/v1/categories/")),
    staleTime: 10 * 60_000,
    select: (data) => (Array.isArray(data) ? data : ((data as { results?: Category[] }).results ?? [])),
  })
}

export function useReviews(slug: string, page = 1) {
  return useQuery({
    queryKey: catalogKeys.reviews(slug, page),
    queryFn: () => unwrap(api.GET("/api/v1/products/{slug}/reviews/", { params: { path: { slug }, query: { page } } })),
    placeholderData: keepPreviousData,
  })
}

export function useQuestions(slug: string, page = 1) {
  return useQuery({
    queryKey: catalogKeys.questions(slug, page),
    queryFn: () =>
      unwrap(api.GET("/api/v1/products/{slug}/questions/", { params: { path: { slug }, query: { page } } })),
    placeholderData: keepPreviousData,
  })
}

export function useCreateReview(slug: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { rating: number; comment: string }) =>
      unwrap(api.POST("/api/v1/products/{slug}/reviews/", { params: { path: { slug } }, body })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: catalogKeys.product(slug) })
    },
  })
}

export function useAskQuestion(slug: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (question: string) =>
      unwrap(api.POST("/api/v1/products/{slug}/questions/", { params: { path: { slug } }, body: { question } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...catalogKeys.product(slug), "questions"] }),
  })
}

export function useStockAlert(slug: string) {
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/products/{slug}/stock-alert/", { params: { path: { slug } } })),
  })
}

export function useStores(page = 1) {
  return useQuery({
    queryKey: catalogKeys.stores(page),
    queryFn: () => unwrap(api.GET("/api/v1/stores/", { params: { query: { page } } })),
  })
}

export function useStore(slug: string) {
  return useQuery({
    queryKey: catalogKeys.store(slug),
    queryFn: () => unwrap(api.GET("/api/v1/stores/{slug}/", { params: { path: { slug } } })),
  })
}

export function useStoreProducts(slug: string, filters: ProductFilters) {
  return useQuery({
    queryKey: catalogKeys.storeProducts(slug, filters),
    queryFn: () =>
      unwrap(api.GET("/api/v1/stores/{slug}/products/", { params: { path: { slug }, query: filters } })),
    placeholderData: keepPreviousData,
  })
}
