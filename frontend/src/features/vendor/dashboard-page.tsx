import { ArrowRightIcon, BoxIcon, CircleDollarSignIcon, PackageXIcon, PlusIcon, StarIcon, TruckIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { AreaChart, BarList, DaysToggle, StatCard } from "@/components/common/charts"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useVendorDashboard, useVendorItems } from "@/features/vendor/api"
import { date, money } from "@/lib/format"
import { useAuth } from "@/providers/auth"

function ToShip() {
  const { data, isPending } = useVendorItems({ page: 1, status: "pending" })
  const processing = useVendorItems({ page: 1, status: "processing" })
  const items = [...(data?.results ?? []), ...(processing.data?.results ?? [])].slice(0, 6)
  if (isPending) return <PageLoader />
  if (!items.length)
    return <EmptyState icon={TruckIcon} title="All caught up" description="New orders to fulfil will appear here." className="py-10" />
  return (
    <ul className="divide-y">
      {items.map((item) => (
        <li key={item.id} className="flex items-center gap-3 py-3 text-sm">
          <div className="min-w-0 flex-1">
            <Link to={`/vendor/orders/${item.order_number}`} className="font-medium hover:underline">
              {item.product_name}
            </Link>
            <p className="text-xs text-muted-foreground">
              {item.order_number} · {date(item.order_created_at)} · Qty {item.quantity}
            </p>
          </div>
          <StatusBadge status={item.status} label={item.status_display} />
        </li>
      ))}
    </ul>
  )
}

export default function VendorDashboardPage() {
  const { user } = useAuth()
  const [days, setDays] = useState(30)
  const { data, isPending, isError, error, refetch } = useVendorDashboard(days)

  if (isPending) return <PageLoader />
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />
  const k = data.kpis

  return (
    <div className="space-y-8">
      <Title>Vendor dashboard</Title>
      <PageHeader
        eyebrow={user?.vendor?.business_name}
        title="Dashboard"
        description="Revenue counts paid orders only, after the platform commission."
        actions={
          <Button asChild>
            <Link to="/vendor/products/new">
              <PlusIcon /> New product
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Net revenue" value={money(k.revenue)} hint={`Gross sales ${money(k.gross_sales)}`} icon={CircleDollarSignIcon} tone="brand" />
        <StatCard
          label="To fulfil"
          value={k.items_to_fulfil}
          hint={`${k.pending_orders} pending orders`}
          icon={TruckIcon}
          tone={k.items_to_fulfil ? "warning" : "default"}
        />
        <StatCard label="Products" value={`${k.active_products} / ${k.total_products}`} hint={`${k.units_sold} units sold`} icon={BoxIcon} />
        <StatCard
          label={k.out_of_stock ? "Out of stock" : "Rating"}
          value={k.out_of_stock ? k.out_of_stock : k.review_count ? Number(k.average_rating).toFixed(1) : "—"}
          hint={k.out_of_stock ? "Active products with no stock" : `${k.review_count} reviews`}
          icon={k.out_of_stock ? PackageXIcon : StarIcon}
          tone={k.out_of_stock ? "danger" : "default"}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="shadow-none xl:col-span-2">
          <CardHeader>
            <CardTitle>Sales</CardTitle>
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
            <CardTitle>Best sellers</CardTitle>
          </CardHeader>
          <CardContent>
            {data.best_sellers.length ? (
              <BarList items={data.best_sellers.map((b) => ({ label: b.label, value: Number(b.value) }))} format={money} />
            ) : (
              <p className="text-sm text-muted-foreground">No sales yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="shadow-none">
        <CardHeader>
          <CardTitle>Ready to fulfil</CardTitle>
          <CardAction>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/vendor/orders">
                All orders <ArrowRightIcon />
              </Link>
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <ToShip />
        </CardContent>
      </Card>
    </div>
  )
}
