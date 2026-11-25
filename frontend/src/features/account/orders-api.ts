import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api, unwrap, type Schemas } from "@/api/client"

export type OrderSummary = Schemas["OrderSummary"]
export type OrderDetail = Schemas["OrderDetail"]
export type OrderStatus = Schemas["OrderStatusEnum"]
export type Ticket = Schemas["Ticket"]

export function useOrders(page: number, status?: OrderStatus) {
  return useQuery({
    queryKey: ["orders", page, status],
    queryFn: () => unwrap(api.GET("/api/v1/orders/", { params: { query: { page, status } } })),
    placeholderData: keepPreviousData,
  })
}

export function useOrder(orderNumber: string) {
  return useQuery({
    queryKey: ["order", orderNumber],
    queryFn: () => unwrap(api.GET("/api/v1/orders/{order_number}/", { params: { path: { order_number: orderNumber } } })),
  })
}

export function useCancelOrder(orderNumber: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reason: string) =>
      unwrap(
        api.POST("/api/v1/orders/{order_number}/cancel/", {
          params: { path: { order_number: orderNumber } },
          body: { reason },
        }),
      ),
    onSuccess: (order) => {
      qc.setQueryData(["order", orderNumber], order)
      qc.invalidateQueries({ queryKey: ["orders"] })
    },
  })
}

// ---- support tickets -------------------------------------------------------
export function useTickets(page: number) {
  return useQuery({
    queryKey: ["tickets", page],
    queryFn: () => unwrap(api.GET("/api/v1/support/tickets/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  })
}

export function useTicket(id: number) {
  return useQuery({
    queryKey: ["ticket", id],
    queryFn: () => unwrap(api.GET("/api/v1/support/tickets/{id}/", { params: { path: { id } } })),
  })
}

export function useCreateTicket() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { subject: string; message: string; order?: string }) =>
      unwrap(api.POST("/api/v1/support/tickets/", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tickets"] }),
  })
}

export function useReplyTicket(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: string) =>
      unwrap(api.POST("/api/v1/support/tickets/{id}/reply/", { params: { path: { id } }, body: { body } })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ticket", id] })
      qc.invalidateQueries({ queryKey: ["tickets"] })
    },
  })
}

export function useCloseTicket(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/support/tickets/{id}/close/", { params: { path: { id } } })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ticket", id] })
      qc.invalidateQueries({ queryKey: ["tickets"] })
    },
  })
}
