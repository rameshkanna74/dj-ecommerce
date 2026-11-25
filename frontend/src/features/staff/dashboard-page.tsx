import { AlertTriangleIcon, ArrowRightIcon, BanknoteIcon, ClockIcon, ShoppingCartIcon, StoreIcon, UsersIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { AreaChart, BarList, DaysToggle, StatCard } from "@/components/common/charts"
import { PageHeader } from "@/components/common/page-header"
import { ErrorState, PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAdminDashboard } from "@/features/staff/api"
import { date, money } from "@/lib/format"

export default function AdminDashboardPage() {
  const [days, setDays] = useState(30)
  const { data, isPending, isError, error, refetch } = useAdminDashboard(days)
  if (isPending) return <PageLoader />
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />
  const k = data.kpis

  return (
    <div className="space-y-8">
      <Title>Admin dashboard</Title>
      <PageHeader title="Marketplace overview" description="Revenue counts paid, non-cancelled orders only." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Revenue" value={money(k.revenue)} hint={`${k.paid_orders} paid orders · avg ${money(k.avg_order_value)}`} icon={BanknoteIcon} tone="brand" />
        <StatCard
          label="Awaiting payment"
          value={k.awaiting_payment}
          hint={`${k.pending_orders} pending of ${k.orders} orders`}
          icon={ClockIcon}
          tone={k.awaiting_payment ? "warning" : "default"}
        />
        <StatCard
          label="Vendors"
          value={k.vendors}
          hint={k.pending_vendors ? `${k.pending_vendors} awaiting approval` : "No pending applications"}
          icon={StoreIcon}
          tone={k.pending_vendors ? "warning" : "default"}
        />
        <StatCard
          label="Customers"
          value={k.customers}
          hint={`${k.active_products}/${k.products} products live${k.out_of_stock ? ` · ${k.out_of_stock} out of stock` : ""}`}
          icon={UsersIcon}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="shadow-none xl:col-span-2">
          <CardHeader>
            <CardTitle>Recognised revenue</CardTitle>
            <CardAction>
              <DaysToggle value={days} onChange={setDays} />
            </CardAction>
          </CardHeader>
          <CardContent>
            <AreaChart data={data.sales_trend.map((p) => ({ label: p.label, value: Number(p.value) }))} format={money} />
          </CardContent>
        </Card>
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Categories</CardTitle>
          </CardHeader>
          <CardContent>
            {data.category_performance.length ? (
              <BarList items={data.category_performance.map((c) => ({ label: c.label, value: Number(c.value) }))} format={money} />
            ) : (
              <p className="text-sm text-muted-foreground">No paid sales yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="shadow-none lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent orders</CardTitle>
            <CardAction>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/staff/orders">
                  All orders <ArrowRightIcon />
                </Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            {data.recent_orders.length ? (
              <ul className="divide-y">
                {data.recent_orders.map((o) => (
                  <li key={o.order_number} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                    <Link to={`/staff/orders/${o.order_number}`} className="font-medium hover:underline">
                      {o.order_number}
                    </Link>
                    <span className="text-xs text-muted-foreground">{date(o.created_at)}</span>
                    <span className="ml-auto flex items-center gap-2">
                      {o.status !== "cancelled" && <StatusBadge status={o.payment_status} label={o.payment_status_display} />}
                      <StatusBadge status={o.status} label={o.status_display} />
                      <span className="w-20 text-right font-medium tabular-nums">{money(o.total_amount)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <ShoppingCartIcon className="size-4" /> No orders yet.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>Vendor applications</CardTitle>
            </CardHeader>
            <CardContent>
              {data.pending_vendors.length ? (
                <ul className="space-y-3">
                  {data.pending_vendors.map((v) => (
                    <li key={v.id} className="text-sm">
                      <Link to="/staff/vendors?status=pending" className="font-medium hover:underline">
                        {v.business_name}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {v.email} · {date(v.created_at)}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">All caught up.</p>
              )}
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>Low stock</CardTitle>
            </CardHeader>
            <CardContent>
              {data.low_stock_products.length ? (
                <ul className="space-y-2.5">
                  {data.low_stock_products.map((p) => (
                    <li key={p.id} className="flex items-center justify-between gap-2 text-sm">
                      <div className="min-w-0">
                        <Link to={`/products/${p.slug}`} className="block truncate hover:underline">
                          {p.name}
                        </Link>
                        <p className="text-xs text-muted-foreground">{p.vendor ?? "Platform"}</p>
                      </div>
                      <span className={`flex shrink-0 items-center gap-1 text-xs font-medium tabular-nums ${p.stock <= 0 ? "text-destructive" : "text-warning"}`}>
                        {p.stock <= 0 && <AlertTriangleIcon className="size-3" />}
                        {p.stock} left
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Everything is well stocked.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
