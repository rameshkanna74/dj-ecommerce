import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api, unwrap } from "@/api/client"
import { CART_KEY } from "@/features/cart/api"
import type { Product } from "@/features/catalog/api"
import { useAuth } from "@/providers/auth"

export const WISHLIST_KEY = ["wishlist"] as const

export function useWishlist() {
  const { user } = useAuth()
  return useQuery({
    queryKey: WISHLIST_KEY,
    queryFn: () => unwrap(api.GET("/api/v1/wishlist/")),
    enabled: user?.role === "customer",
    select: (data) => (Array.isArray(data) ? data : ((data as unknown as { results: Product[] }).results ?? [])),
  })
}

export function useWishlistIds() {
  const { data } = useWishlist()
  return new Set((data ?? []).map((p) => p.id))
}

/** Toggle with an optimistic update so the heart responds instantly. */
export function useToggleWishlist() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ product, saved }: { product: Product; saved: boolean }) => {
      if (saved) {
        await unwrap(api.DELETE("/api/v1/wishlist/{product_id}/", { params: { path: { product_id: product.id } } }))
      } else {
        await unwrap(api.POST("/api/v1/wishlist/", { body: { product: product.id } }))
      }
    },
    onMutate: async ({ product, saved }) => {
      await qc.cancelQueries({ queryKey: WISHLIST_KEY })
      const previous = qc.getQueryData<Product[]>(WISHLIST_KEY)
      qc.setQueryData<Product[]>(WISHLIST_KEY, (list = []) =>
        saved ? list.filter((p) => p.id !== product.id) : [product, ...list],
      )
      return { previous }
    },
    onError: (_err, _vars, ctx) => {
      qc.setQueryData(WISHLIST_KEY, ctx?.previous)
      toast.error("Could not update your wishlist.")
    },
    onSuccess: (_data, { saved }) => toast.success(saved ? "Removed from wishlist" : "Saved to wishlist"),
    onSettled: () => qc.invalidateQueries({ queryKey: WISHLIST_KEY }),
  })
}

export function useMoveWishlistToCart() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (productId: number) =>
      unwrap(api.POST("/api/v1/wishlist/{product_id}/move-to-cart/", { params: { path: { product_id: productId } } })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: WISHLIST_KEY })
      qc.invalidateQueries({ queryKey: CART_KEY })
      toast.success("Moved to your cart")
    },
  })
}
