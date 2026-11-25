import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api, ApiError, unwrap, type Schemas } from "@/api/client"
import { useAuth } from "@/providers/auth"

export type Cart = Schemas["Cart"]
export type CartItem = Schemas["CartItem"]

export const CART_KEY = ["cart"] as const

export function useCart() {
  const { user } = useAuth()
  return useQuery({
    queryKey: CART_KEY,
    queryFn: () => unwrap(api.GET("/api/v1/cart/")),
    enabled: user?.role === "customer",
  })
}

/** Every cart mutation returns the full cart, so we write it straight into the cache. */
function useCartMutation<V>(fn: (vars: V) => Promise<Cart>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (cart) => qc.setQueryData(CART_KEY, cart),
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not update your cart."),
  })
}

export function useAddToCart() {
  return useCartMutation((body: { product: number; variant?: number; quantity: number }) =>
    unwrap(api.POST("/api/v1/cart/items/", { body })),
  )
}

export function useUpdateCartItem() {
  return useCartMutation(({ id, ...body }: { id: number; quantity?: number; is_saved_for_later?: boolean }) =>
    unwrap(api.PATCH("/api/v1/cart/items/{id}/", { params: { path: { id } }, body })),
  )
}

export function useRemoveCartItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE("/api/v1/cart/items/{id}/", { params: { path: { id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: CART_KEY }),
  })
}
