import { ChevronRightIcon, PackageIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useOrders, type OrderStatus } from "@/features/account/orders-api"
import { date, money, pluralize } from "@/lib/format"

const FILTERS: { value: OrderStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "processing", label: "Processing" },
  { value: "shipped", label: "Shipped" },
  { value: "delivered", label: "Delivered" },
  { value: "cancelled", label: "Cancelled" },
]

export default function OrdersPage() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<OrderStatus | "all">("all")
  const { data, isPending, isError, error, refetch } = useOrders(page, status === "all" ? undefined : status)

  return (
    <div className="space-y-6">
      <Title>Orders</Title>
      <PageHeader title="Orders" description="Track deliveries, view receipts and cancel pending orders." />
      <Tabs
        value={status}
        onValueChange={(v) => {
          setStatus(v as OrderStatus | "all")
          setPage(1)
        }}
      >
        <TabsList className="flex-wrap">
          {FILTERS.map((f) => (
            <TabsTrigger key={f.value} value={f.value}>
              {f.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState
          icon={PackageIcon}
          title={status === "all" ? "No orders yet" : `No ${status} orders`}
          description={status === "all" ? "When you place an order it will show up here." : undefined}
          action={
            status === "all" && (
              <Button asChild>
                <Link to="/products">Start shopping</Link>
              </Button>
            )
          }
        />
      ) : (
        <>
          <ul className="divide-y rounded-2xl border">
            {data.results.map((o) => (
              <li key={o.order_number}>
                <Link
                  to={`/account/orders/${o.order_number}`}
                  className="flex flex-wrap items-center gap-x-6 gap-y-2 p-4 transition-colors hover:bg-muted/40 sm:p-5"
                >
                  <div className="min-w-36">
                    <p className="font-medium">{o.order_number}</p>
                    <p className="text-xs text-muted-foreground">{date(o.created_at)}</p>
                  </div>
                  <StatusBadge status={o.status} label={o.status_display} />
                  {o.payment_status !== "paid" && o.status !== "cancelled" && (
                    <StatusBadge status={o.payment_status} label={o.payment_status_display} />
                  )}
                  <div className="ml-auto flex items-center gap-4 text-sm">
                    <span className="text-muted-foreground">{pluralize(o.item_count, "item")}</span>
                    <span className="font-semibold tabular-nums">{money(o.total_amount)}</span>
                    <ChevronRightIcon className="size-4 text-muted-foreground" />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
    </div>
  )
}
