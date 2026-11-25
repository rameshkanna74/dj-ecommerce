import { PackageIcon, PlusIcon, SearchIcon } from "lucide-react"
import { useDeferredValue, useState } from "react"
import { Link, useNavigate } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { ProductImage } from "@/components/product/product-image"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useSaveProduct, useVendorProducts, type VendorProduct } from "@/features/vendor/api"
import { money } from "@/lib/format"
import { cn } from "@/lib/utils"

function productStock(p: Pick<VendorProduct, "stock" | "variants">) {
  const active = p.variants.filter((v) => v.is_active !== false)
  return active.length ? active.reduce((sum, v) => sum + (v.stock ?? 0), 0) : (p.stock ?? 0)
}

function ActiveSwitch({ product }: { product: VendorProduct }) {
  const save = useSaveProduct(product.id)
  return (
    <Switch
      checked={product.is_active !== false}
      disabled={save.isPending}
      onCheckedChange={(is_active) => save.mutate({ is_active })}
      aria-label={product.is_active ? "Hide product" : "Publish product"}
      onClick={(e) => e.stopPropagation()}
    />
  )
}

export default function VendorProductsPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<"all" | "active" | "inactive">("all")
  const [q, setQ] = useState("")
  const query = useDeferredValue(q.trim())
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useVendorProducts({
    page,
    q: query || undefined,
    status: status === "all" ? undefined : status,
  })

  return (
    <div className="space-y-6">
      <Title>Products</Title>
      <PageHeader
        title="Products"
        description="Manage your catalogue, stock and options."
        actions={
          <Button asChild>
            <Link to="/vendor/products/new">
              <PlusIcon /> New product
            </Link>
          </Button>
        }
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={status} onValueChange={(v) => (setStatus(v as typeof status), setPage(1))}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="active">Live</TabsTrigger>
            <TabsTrigger value="inactive">Hidden</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative w-full sm:w-64">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} placeholder="Search products" className="pl-9" aria-label="Search products" />
        </div>
      </div>

      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState
          icon={PackageIcon}
          title={query || status !== "all" ? "No matching products" : "No products yet"}
          description={query || status !== "all" ? undefined : "Add your first product to start selling."}
          action={
            !query && status === "all" && (
              <Button asChild>
                <Link to="/vendor/products/new">Add a product</Link>
              </Button>
            )
          }
        />
      ) : (
        <>
          <div className={cn("overflow-x-auto rounded-2xl border", isPlaceholderData && "opacity-60")}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="text-right">Sold</TableHead>
                  <TableHead>Rating</TableHead>
                  <TableHead className="text-right">Live</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((p) => {
                  const stock = productStock(p)
                  return (
                    <TableRow key={p.id} className="cursor-pointer" onClick={() => navigate(`/vendor/products/${p.id}`)}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="size-10 shrink-0 overflow-hidden rounded-lg bg-muted">
                            <ProductImage src={p.cover_image ?? p.images[0]?.image} name={p.name} size="sm" />
                          </div>
                          <div className="min-w-0">
                            <Link to={`/vendor/products/${p.id}`} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>
                              {p.name}
                            </Link>
                            {p.variants.length > 0 && <p className="text-xs text-muted-foreground">{p.variants.length} options</p>}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{money(p.price)}</TableCell>
                      <TableCell className={cn("text-right tabular-nums", stock === 0 && "text-destructive", stock > 0 && stock <= 5 && "text-warning")}>
                        {stock}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{p.units_sold}</TableCell>
                      <TableCell className="text-sm text-muted-foreground tabular-nums">
                        {p.review_count ? `★ ${Number(p.average_rating).toFixed(1)} (${p.review_count})` : "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <ActiveSwitch product={p} />
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
    </div>
  )
}
