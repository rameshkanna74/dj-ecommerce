import { ArrowLeftIcon, CheckIcon, LifeBuoyIcon, TruckIcon } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router"
import { toast } from "sonner"

import { ErrorState, PageLoader, Spinner, errorMessage } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { useCancelOrder, useOrder, type OrderDetail } from "@/features/account/orders-api"
import { date, dateTime, money } from "@/lib/format"
import { cn } from "@/lib/utils"

const STEPS = ["pending", "processing", "shipped", "delivered"] as const

function Progress({ order }: { order: OrderDetail }) {
  if (order.status === "cancelled")
    return <p className="rounded-xl bg-destructive/10 p-4 text-sm text-destructive">Cancelled on {date(order.cancelled_at)}</p>
  const current = STEPS.indexOf(order.status as (typeof STEPS)[number])
  return (
    <ol className="grid grid-cols-4 gap-2">
      {STEPS.map((step, i) => (
        <li key={step} className="space-y-2">
          <div className={cn("h-1.5 rounded-full", i <= current ? "bg-brand" : "bg-muted")} />
          <p className={cn("flex items-center gap-1 text-xs capitalize", i <= current ? "text-foreground" : "text-muted-foreground")}>
            {i < current && <CheckIcon className="size-3" />}
            {step}
          </p>
        </li>
      ))}
    </ol>
  )
}

function CancelButton({ order }: { order: OrderDetail }) {
  const cancel = useCancelOrder(order.order_number)
  const [reason, setReason] = useState("")
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline">Cancel order</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Cancel this order?</AlertDialogTitle>
          <AlertDialogDescription>
            All items will be cancelled and returned to stock. This can’t be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (optional)" maxLength={300} aria-label="Reason" />
        <AlertDialogFooter>
          <AlertDialogCancel>Keep order</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-white hover:bg-destructive/90"
            onClick={(e) => {
              e.preventDefault()
              cancel.mutate(reason, {
                onSuccess: () => toast.success("Order cancelled"),
                onError: (err) => toast.error(errorMessage(err)),
              })
            }}
            disabled={cancel.isPending}
          >
            {cancel.isPending && <Spinner />} Cancel order
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export default function OrderPage() {
  const { orderNumber = "" } = useParams()
  const { data: order, isPending, isError, error, refetch } = useOrder(orderNumber)

  if (isPending) return <PageLoader />
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />
  const address = order.shipping_address

  return (
    <div className="space-y-6">
      <Title>{`Order ${order.order_number}`}</Title>
      <Link to="/account/orders" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" /> All orders
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-heading text-4xl">Order {order.order_number}</h1>
          <p className="text-sm text-muted-foreground">Placed {dateTime(order.created_at)}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" asChild>
            <Link to={`/account/support?order=${order.order_number}`}>
              <LifeBuoyIcon /> Get help
            </Link>
          </Button>
          {order.can_cancel && <CancelButton order={order} />}
        </div>
      </div>

      <Progress order={order} />

      {order.payment_instructions && (
        <div className="rounded-2xl border border-warning/40 bg-warning-soft p-4 text-sm">
          <p className="font-medium">{order.payment_method_display}</p>
          <p className="text-muted-foreground">{order.payment_instructions}</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Items</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {order.items.map((item) => (
                <li key={item.id} className="flex flex-wrap items-start gap-4 py-4 first:pt-0 last:pb-0">
                  <div className="min-w-0 flex-1 space-y-1">
                    <Link to={`/products/${item.product_slug}`} className="font-medium hover:underline">
                      {item.product_name}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {item.vendor?.business_name ?? "CoreCart"}
                      {item.variant_label && <> · {item.variant_label}</>} · Qty {item.quantity}
                    </p>
                    {item.tracking_number && (
                      <p className="flex items-center gap-1.5 text-xs">
                        <TruckIcon className="size-3.5 text-brand" /> Tracking: <span className="font-mono">{item.tracking_number}</span>
                      </p>
                    )}
                  </div>
                  <StatusBadge status={item.status} label={item.status_display} />
                  <p className="w-24 text-right text-sm font-medium tabular-nums">{money(item.subtotal)}</p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Subtotal</dt>
                  <dd className="tabular-nums">{money(order.subtotal_amount)}</dd>
                </div>
                {Number(order.discount_amount) > 0 && (
                  <div className="flex justify-between text-success">
                    <dt>Discount {order.coupon_code && `(${order.coupon_code})`}</dt>
                    <dd className="tabular-nums">−{money(order.discount_amount)}</dd>
                  </div>
                )}
                <div className="flex justify-between border-t pt-2 font-semibold">
                  <dt>Total</dt>
                  <dd className="tabular-nums">{money(order.total_amount)}</dd>
                </div>
                <div className="flex items-center justify-between pt-2">
                  <dt className="text-muted-foreground">Payment</dt>
                  <dd>
                    <StatusBadge status={order.payment_status} label={order.payment_status_display} />
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>Delivery</CardTitle>
            </CardHeader>
            <CardContent className="space-y-0.5 text-sm">
              <p className="font-medium">{address.full_name}</p>
              <p className="text-muted-foreground">{address.address}</p>
              <p className="text-muted-foreground">
                {[address.city, address.state, address.postal_code].filter(Boolean).join(", ")}
              </p>
              <p className="text-muted-foreground">{address.country}</p>
              <p className="pt-1 text-muted-foreground">{address.phone}</p>
            </CardContent>
          </Card>
        </div>
      </div>

      {order.timeline.length > 0 && (
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="relative space-y-5 border-l pl-6">
              {order.timeline.map((event) => (
                <li key={event.id} className="relative">
                  <span className="absolute top-1.5 -left-[1.6rem] size-2.5 rounded-full border-2 border-background bg-brand" />
                  <p className="text-sm">{event.note}</p>
                  <p className="text-xs text-muted-foreground">{dateTime(event.timestamp)}</p>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
