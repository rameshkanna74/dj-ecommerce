import { ArrowLeftIcon } from "lucide-react"
import { Link, useParams } from "react-router"

import { ErrorState, PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useSetItemStatus, useVendorOrder } from "@/features/vendor/api"
import { ItemActions } from "@/features/vendor/item-actions"
import { dateTime, money } from "@/lib/format"

export default function VendorOrderPage() {
  const { orderNumber = "" } = useParams()
  const { data: order, isPending, isError, error, refetch } = useVendorOrder(orderNumber)
  const setItemStatus = useSetItemStatus()

  if (isPending) return <PageLoader />
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />
  const a = order.shipping_address
  const earnings = order.items.reduce((sum, i) => sum + Number(i.vendor_earnings), 0)

  return (
    <div className="space-y-6">
      <Title>{`Order ${order.order_number}`}</Title>
      <Link to="/vendor/orders" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" /> Orders
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="font-heading text-4xl">Order {order.order_number}</h1>
          <p className="text-sm text-muted-foreground">Placed {dateTime(order.created_at)}</p>
        </div>
        <div className="flex gap-2">
          {order.status && <StatusBadge status={order.status} />}
          {order.payment_status && <StatusBadge status={order.payment_status} />}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Your items</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {order.items.map((item) => (
                <li key={item.id} className="flex flex-wrap items-center gap-4 py-4 first:pt-0 last:pb-0">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{item.product_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.variant_label && `${item.variant_label} · `}Qty {item.quantity} × {money(item.price)} · You earn{" "}
                      {money(item.vendor_earnings)} ({Number(item.commission_rate)}% commission)
                    </p>
                    {item.tracking_number && <p className="mt-1 font-mono text-xs">Tracking: {item.tracking_number}</p>}
                  </div>
                  <StatusBadge status={item.status} label={item.status_display} />
                  <ItemActions
                    allowed={item.allowed_next_statuses}
                    currentTracking={item.tracking_number}
                    pending={setItemStatus.isPending && setItemStatus.variables?.id === item.id}
                    onChange={(status, tracking) => setItemStatus.mutate({ id: item.id, status, tracking_number: tracking })}
                  />
                </li>
              ))}
            </ul>
            <p className="mt-4 border-t pt-4 text-right text-sm">
              Your earnings: <span className="font-semibold tabular-nums">{money(earnings)}</span>
            </p>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>Ship to</CardTitle>
            </CardHeader>
            <CardContent className="space-y-0.5 text-sm">
              <p className="font-medium">{a.full_name}</p>
              <p className="text-muted-foreground">{a.address}</p>
              <p className="text-muted-foreground">{[a.city, a.state, a.postal_code].filter(Boolean).join(", ")}</p>
              <p className="text-muted-foreground">{a.country}</p>
              <p className="pt-1 text-muted-foreground">{a.phone}</p>
            </CardContent>
          </Card>
          {order.customer_note && (
            <Card className="shadow-none">
              <CardHeader>
                <CardTitle>Customer note</CardTitle>
              </CardHeader>
              <CardContent className="text-sm whitespace-pre-line text-muted-foreground">{order.customer_note}</CardContent>
            </Card>
          )}
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>Activity</CardTitle>
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
