import { PackageIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useStaffProducts, useUpdateStaffProduct } from "@/features/staff/api"
import { SearchInput, TableShell, useSearch } from "@/features/staff/shared"
import { money } from "@/lib/format"
import { cn } from "@/lib/utils"

export default function StaffProductsPage() {
  const [page, setPage] = useState(1)
  const [lowStock, setLowStock] = useState(false)
  const search = useSearch()
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useStaffProducts({
    page,
    q: search.query,
    low_stock: lowStock ? "1" : undefined,
  })
  const update = useUpdateStaffProduct()

  return (
    <div className="space-y-6">
      <Title>Products</Title>
      <PageHeader title="Products" description="Take listings down, feature products on the home page, and watch stock." />
      <div className="flex flex-wrap items-center gap-4">
        <SearchInput value={search.value} onChange={(v) => (search.setValue(v), setPage(1))} placeholder="Search products" />
        <div className="flex items-center gap-2">
          <Switch id="low" checked={lowStock} onCheckedChange={(v) => (setLowStock(v), setPage(1))} />
          <Label htmlFor="low" className="font-normal">
            Low stock only (≤ 5)
          </Label>
        </div>
      </div>
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={PackageIcon} title="No products match" />
      ) : (
        <>
          <TableShell dimmed={isPlaceholderData}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="text-center">Featured</TableHead>
                  <TableHead className="text-center">Live</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>
                      <Link to={`/products/${p.slug}`} className="font-medium hover:underline">
                        {p.name}
                      </Link>
                      <p className="text-xs text-muted-foreground">{p.vendor ?? "Platform"}</p>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{p.category}</TableCell>
                    <TableCell className="text-right tabular-nums">{money(p.price)}</TableCell>
                    <TableCell className={cn("text-right tabular-nums", (p.stock ?? 0) <= 0 && "text-destructive")}>{p.stock}</TableCell>
                    <TableCell className="text-center">
                      <Switch
                        checked={Boolean(p.is_featured)}
                        onCheckedChange={(is_featured) => update.mutate({ id: p.id, is_featured })}
                        aria-label={`Feature ${p.name}`}
                      />
                    </TableCell>
                    <TableCell className="text-center">
                      <Switch
                        checked={p.is_active !== false}
                        onCheckedChange={(is_active) => update.mutate({ id: p.id, is_active })}
                        aria-label={`Publish ${p.name}`}
                      />
                    </TableCell>
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
