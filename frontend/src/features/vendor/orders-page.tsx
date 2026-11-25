import { SearchIcon, ShoppingCartIcon } from "lucide-react"
import { useDeferredValue, useState } from "react"
import { Link } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useSetItemStatus, useVendorItems, type ItemStatus } from "@/features/vendor/api"
import { ItemActions } from "@/features/vendor/item-actions"
import { date, money } from "@/lib/format"
import { cn } from "@/lib/utils"

const TABS: (ItemStatus | "all")[] = ["all", "pending", "processing", "shipped", "delivered", "cancelled"]

export default function VendorOrdersPage() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<ItemStatus | "all">("pending")
  const [q, setQ] = useState("")
  const query = useDeferredValue(q.trim())
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useVendorItems({
    page,
    status: status === "all" ? undefined : status,
    q: query || undefined,
  })
  const setItemStatus = useSetItemStatus()

  return (
    <div className="space-y-6">
      <Title>Orders</Title>
      <PageHeader title="Orders" description="Every line of every order for your products. Ship with a tracking number." />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={status} onValueChange={(v) => (setStatus(v as ItemStatus | "all"), setPage(1))}>
          <TabsList className="flex-wrap">
            {TABS.map((t) => (
              <TabsTrigger key={t} value={t} className="capitalize">
                {t}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative w-full sm:w-64">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} placeholder="Order number or product" className="pl-9" aria-label="Search orders" />
        </div>
      </div>

      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={ShoppingCartIcon} title={status === "pending" ? "Nothing waiting" : "No order lines"} description="Orders for your products appear here." />
      ) : (
        <>
          <div className={cn("overflow-x-auto rounded-2xl border", isPlaceholderData && "opacity-60")}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Order</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead className="text-right">Earnings</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <Link to={`/vendor/orders/${item.order_number}`} className="font-medium hover:underline">
                        {item.order_number}
                      </Link>
                      <p className="text-xs text-muted-foreground">{date(item.order_created_at)}</p>
                    </TableCell>
                    <TableCell>
                      <p className="max-w-56 truncate">{item.product_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.variant_label && `${item.variant_label} · `}Qty {item.quantity} × {money(item.price)}
                      </p>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {money(item.vendor_earnings)}
                      <p className="text-xs text-muted-foreground">{item.payment_status === "paid" ? "Paid" : "Awaiting payment"}</p>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={item.status} label={item.status_display} />
                      {item.tracking_number && <p className="mt-1 font-mono text-xs text-muted-foreground">{item.tracking_number}</p>}
                    </TableCell>
                    <TableCell>
                      <ItemActions
                        allowed={item.allowed_next_statuses}
                        currentTracking={item.tracking_number}
                        pending={setItemStatus.isPending && setItemStatus.variables?.id === item.id}
                        onChange={(next, tracking) => setItemStatus.mutate({ id: item.id, status: next, tracking_number: tracking })}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
    </div>
  )
}
