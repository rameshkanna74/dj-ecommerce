import { ArrowLeftIcon, BanknoteIcon, Undo2Icon, XCircleIcon } from "lucide-react"
import { Link, useParams } from "react-router"

import { ErrorState, PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useOrderAction, useStaffItemStatus, useStaffOrder, type OrderDetail } from "@/features/staff/api"
import { ConfirmAction } from "@/features/staff/shared"
import { ItemActions } from "@/features/vendor/item-actions"
import { dateTime, money } from "@/lib/format"

// Mirrors OrderItem.ALLOWED_TRANSITIONS; the API re-validates every change.
const NEXT: Record<string, string[]> = {
  pending: ["processing", "cancelled"],
  processing: ["shipped", "cancelled"],
  shipped: ["delivered"],
}

function allowedFor(item: OrderDetail["items"][number], order: OrderDetail) {
  const next = NEXT[item.status ?? ""] ?? []
  return order.payment_status === "paid" ? next.filter((s) => s !== "cancelled") : next
}

export default function StaffOrderPage() {
  const { orderNumber = "" } = useParams()
  const { data: order, isPending, isError, error, refetch } = useStaffOrder(orderNumber)
  const action = useOrderAction(orderNumber)
  const itemStatus = useStaffItemStatus(orderNumber)

  if (isPending) return <PageLoader />
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />
  const a = order.shipping_address
  const paid = order.payment_status === "paid"
  const cancelled = order.status === "cancelled"
  const shipped = order.items.some((i) => i.status === "shipped" || i.status === "delivered")

  return (
    <div className="space-y-6">
      <Title>{`Order ${order.order_number}`}</Title>
      <Link to="/staff/orders" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" /> Orders
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1 className="font-heading text-4xl">Order {order.order_number}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            {dateTime(order.created_at)} · {order.payment_method_display}
            <StatusBadge status={order.status} label={order.status_display} />
            <StatusBadge status={order.payment_status} label={order.payment_status_display} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {!paid && !cancelled && order.payment_status !== "refunded" && (
            <ConfirmAction
              trigger={
                <Button>
                  <BanknoteIcon /> Mark paid
                </Button>
              }
              title="Record payment"
              description={`Confirm that ${money(order.total_amount)} has been received.`}
              inputLabel="Payment reference (optional)"
              inputPlaceholder="Bank reference, receipt number…"
              confirmLabel="Mark as paid"
              onConfirm={(text) => action.mutateAsync({ action: "mark-paid", text })}
            />
          )}
          {paid && (
            <ConfirmAction
              trigger={
                <Button variant="outline">
                  <Undo2Icon /> Refund
                </Button>
              }
              title="Mark as refunded"
              description="Record that the payment was returned to the customer. The order can be cancelled afterwards."
              inputLabel="Note (optional)"
              confirmLabel="Mark refunded"
              onConfirm={(text) => action.mutateAsync({ action: "refund", text })}
            />
          )}
          {!cancelled && !paid && !shipped && (
            <ConfirmAction
              trigger={
                <Button variant="ghost" className="text-destructive hover:text-destructive">
                  <XCircleIcon /> Cancel order
                </Button>
              }
              title="Cancel this order?"
              description="All remaining items are cancelled, stock is returned and the coupon use is released."
              inputLabel="Reason (shown in the order history)"
              confirmLabel="Cancel order"
              destructive
              onConfirm={(text) => action.mutateAsync({ action: "cancel", text })}
            />
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Items</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {order.items.map((item) => (
                <li key={item.id} className="flex flex-wrap items-center gap-4 py-4 first:pt-0 last:pb-0">
                  <div className="min-w-0 flex-1">
                    <Link to={`/products/${item.product_slug}`} className="font-medium hover:underline">
                      {item.product_name}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {item.vendor?.business_name ?? "Platform"}
                      {item.variant_label && ` · ${item.variant_label}`} · {item.quantity} × {money(item.price)}
                    </p>
                    {item.tracking_number && <p className="mt-1 font-mono text-xs">Tracking: {item.tracking_number}</p>}
                  </div>
                  <StatusBadge status={item.status} label={item.status_display} />
                  <span className="w-20 text-right text-sm tabular-nums">{money(item.subtotal)}</span>
                  <ItemActions
                    allowed={allowedFor(item, order)}
                    currentTracking={item.tracking_number}
                    pending={itemStatus.isPending && itemStatus.variables?.id === item.id}
                    onChange={(status, tracking) => itemStatus.mutate({ id: item.id, status, tracking_number: tracking })}
                  />
                </li>
              ))}
            </ul>
            <dl className="mt-4 space-y-1 border-t pt-4 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Subtotal</dt>
                <dd className="tabular-nums">{money(order.subtotal_amount)}</dd>
              </div>
              {Number(order.discount_amount) > 0 && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Discount ({order.coupon_code})</dt>
                  <dd className="tabular-nums">−{money(order.discount_amount)}</dd>
                </div>
              )}
              <div className="flex justify-between font-semibold">
                <dt>Total</dt>
                <dd className="tabular-nums">{money(order.total_amount)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>Customer & delivery</CardTitle>
            </CardHeader>
            <CardContent className="space-y-0.5 text-sm">
              <p className="font-medium">{a.full_name}</p>
              <p className="text-muted-foreground">{a.phone}</p>
              <p className="pt-2 text-muted-foreground">{a.address}</p>
              <p className="text-muted-foreground">{[a.city, a.state, a.postal_code].filter(Boolean).join(", ")}</p>
              <p className="text-muted-foreground">{a.country}</p>
              {order.customer_note && <p className="mt-3 rounded-lg bg-muted p-3 text-xs">“{order.customer_note}”</p>}
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>History</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-3 border-l pl-4">
                {order.timeline.map((t) => (
                  <li key={t.id}>
                    <p className="text-sm">{t.note}</p>
                    <p className="text-xs text-muted-foreground">{dateTime(t.timestamp)}</p>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
