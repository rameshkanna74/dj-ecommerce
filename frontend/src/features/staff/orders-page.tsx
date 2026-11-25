import { ShoppingCartIcon } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useStaffOrders } from "@/features/staff/api"
import { SearchInput, TableShell, useSearch } from "@/features/staff/shared"
import { dateTime, money } from "@/lib/format"

export default function StaffOrdersPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState("all")
  const [payment, setPayment] = useState("all")
  const search = useSearch()
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useStaffOrders({
    page,
    status: status === "all" ? undefined : status,
    payment_status: payment === "all" ? undefined : payment,
    q: search.query,
  })

  return (
    <div className="space-y-6">
      <Title>Orders</Title>
      <PageHeader title="Orders" description="Confirm payments, refund, cancel, and step in on fulfilment." />
      <div className="flex flex-wrap items-center gap-3">
        <SearchInput value={search.value} onChange={(v) => (search.setValue(v), setPage(1))} placeholder="Order number, email or name" />
        <Select value={status} onValueChange={(v) => (setStatus(v), setPage(1))}>
          <SelectTrigger className="w-40" aria-label="Order status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {["pending", "processing", "shipped", "delivered", "cancelled"].map((s) => (
              <SelectItem key={s} value={s} className="capitalize">
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={payment} onValueChange={(v) => (setPayment(v), setPage(1))}>
          <SelectTrigger className="w-44" aria-label="Payment status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All payments</SelectItem>
            <SelectItem value="unpaid">Awaiting payment</SelectItem>
            <SelectItem value="paid">Paid</SelectItem>
            <SelectItem value="refunded">Refunded</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={ShoppingCartIcon} title="No orders match" />
      ) : (
        <>
          <TableShell dimmed={isPlaceholderData}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Order</TableHead>
                  <TableHead>Placed</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead className="text-right">Items</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((o) => (
                  <TableRow key={o.order_number} className="cursor-pointer" onClick={() => navigate(`/staff/orders/${o.order_number}`)}>
                    <TableCell className="font-medium">{o.order_number}</TableCell>
                    <TableCell className="text-muted-foreground">{dateTime(o.created_at)}</TableCell>
                    <TableCell>
                      <StatusBadge status={o.status} label={o.status_display} />
                    </TableCell>
                    <TableCell>
                      {o.status === "cancelled" && o.payment_status === "unpaid" ? (
                        <span className="text-xs text-muted-foreground">—</span>
                      ) : (
                        <StatusBadge status={o.payment_status} label={o.payment_status_display} />
                      )}
                      <p className="mt-0.5 text-xs text-muted-foreground">{o.payment_method === "cod" ? "Cash on delivery" : "Bank transfer"}</p>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{o.item_count}</TableCell>
                    <TableCell className="text-right font-medium tabular-nums">{money(o.total_amount)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableShell>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
    </div>
  )
}
