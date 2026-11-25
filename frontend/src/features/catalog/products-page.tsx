import { SearchXIcon, SlidersHorizontalIcon, XIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { useSearchParams } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { ProductCard, ProductCardSkeleton, ProductGrid } from "@/components/product/product-card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import { useCategories, useProducts, type ProductFilters, type Sort } from "@/features/catalog/api"
import { pluralize } from "@/lib/format"
import { cn } from "@/lib/utils"

const SORTS: { value: Sort; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "popular", label: "Most popular" },
  { value: "rating", label: "Top rated" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
]

const PAGE_SIZE = 20

/** URL search params are the single source of truth for filters (shareable, back-button friendly). */
export function useFilterParams() {
  const [params, setParams] = useSearchParams()
  const num = (key: string) => {
    const value = Number(params.get(key))
    return params.get(key) && Number.isFinite(value) && value >= 0 ? value : undefined
  }
  const filters: ProductFilters = {
    q: params.get("q") || undefined,
    category: params.get("category") || undefined,
    sort: (SORTS.find((s) => s.value === params.get("sort"))?.value ?? undefined) as Sort | undefined,
    min_price: num("min_price"),
    max_price: num("max_price"),
    in_stock: params.get("in_stock") === "true" || undefined,
    page: num("page") || undefined,
    page_size: PAGE_SIZE,
  }
  function update(changes: Record<string, string | undefined>, resetPage = true) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (resetPage && !("page" in changes)) next.delete("page")
    setParams(next, { preventScrollReset: !("page" in changes) })
  }
  return { filters, update, clear: () => setParams(new URLSearchParams()) }
}

function FilterPanel({
  filters,
  update,
}: {
  filters: ProductFilters
  update: (changes: Record<string, string | undefined>) => void
}) {
  const { data: categories } = useCategories()
  const [min, setMin] = useState(filters.min_price?.toString() ?? "")
  const [max, setMax] = useState(filters.max_price?.toString() ?? "")

  function applyPrice(e: FormEvent) {
    e.preventDefault()
    update({ min_price: min || undefined, max_price: max || undefined })
  }

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <p className="text-sm font-medium">Category</p>
        <div className="flex flex-col items-start gap-1">
          {[{ slug: "", name: "Everything" }, ...(categories ?? [])].map((c) => {
            const active = (filters.category ?? "") === c.slug
            return (
              <button
                key={c.slug || "all"}
                type="button"
                onClick={() => update({ category: c.slug || undefined })}
                className={cn(
                  "rounded-md px-2 py-1 -ml-2 text-sm transition-colors",
                  active ? "bg-muted font-medium text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
                aria-pressed={active}
              >
                {c.name}
              </button>
            )
          })}
        </div>
      </div>

      <form onSubmit={applyPrice} className="space-y-3">
        <p className="text-sm font-medium">Price</p>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            inputMode="decimal"
            min={0}
            placeholder="Min"
            aria-label="Minimum price"
            value={min}
            onChange={(e) => setMin(e.target.value)}
          />
          <span className="text-muted-foreground">–</span>
          <Input
            type="number"
            inputMode="decimal"
            min={0}
            placeholder="Max"
            aria-label="Maximum price"
            value={max}
            onChange={(e) => setMax(e.target.value)}
          />
        </div>
        <Button type="submit" variant="outline" size="sm" className="w-full">
          Apply
        </Button>
      </form>

      <div className="flex items-center justify-between gap-3">
        <Label htmlFor="in-stock" className="font-normal">
          In stock only
        </Label>
        <Switch
          id="in-stock"
          checked={Boolean(filters.in_stock)}
          onCheckedChange={(checked) => update({ in_stock: checked ? "true" : undefined })}
        />
      </div>
    </div>
  )
}

export function ActiveFilters({
  filters,
  update,
  clear,
}: {
  filters: ProductFilters
  update: (changes: Record<string, string | undefined>) => void
  clear: () => void
}) {
  const { data: categories } = useCategories()
  const chips: { key: string; label: string; remove: Record<string, undefined> }[] = []
  if (filters.q) chips.push({ key: "q", label: `“${filters.q}”`, remove: { q: undefined } })
  if (filters.category)
    chips.push({
      key: "category",
      label: categories?.find((c) => c.slug === filters.category)?.name ?? filters.category,
      remove: { category: undefined },
    })
  if (filters.min_price !== undefined || filters.max_price !== undefined)
    chips.push({
      key: "price",
      label: `${filters.min_price ?? 0} – ${filters.max_price ?? "∞"}`,
      remove: { min_price: undefined, max_price: undefined },
    })
  if (filters.in_stock) chips.push({ key: "stock", label: "In stock", remove: { in_stock: undefined } })
  if (!chips.length) return null
  return (
    <div className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <button
          key={chip.key}
          type="button"
          onClick={() => update(chip.remove)}
          className="inline-flex items-center gap-1 rounded-full border bg-background px-3 py-1 text-xs hover:bg-muted"
        >
          {chip.label}
          <XIcon className="size-3" aria-label="Remove filter" />
        </button>
      ))}
      <button type="button" onClick={clear} className="text-xs text-muted-foreground underline-offset-4 hover:underline">
        Clear all
      </button>
    </div>
  )
}

export function SortSelect({ value, onChange }: { value?: Sort; onChange: (v: Sort) => void }) {
  return (
    <Select value={value ?? "newest"} onValueChange={(v) => onChange(v as Sort)}>
      <SelectTrigger className="w-44" aria-label="Sort products">
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="end">
        {SORTS.map((s) => (
          <SelectItem key={s.value} value={s.value}>
            {s.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default function ProductsPage() {
  const { filters, update, clear } = useFilterParams()
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useProducts(filters)
  const { data: categories } = useCategories()
  const category = categories?.find((c) => c.slug === filters.category)
  const heading = filters.q ? `Results for “${filters.q}”` : (category?.name ?? "All products")

  return (
    <div className="container-page space-y-8 py-10">
      <Title>{heading}</Title>
      <PageHeader
        eyebrow="Shop"
        title={heading}
        description={category?.description || (data ? pluralize(data.count, "product") : undefined)}
      />

      <div className="grid gap-10 lg:grid-cols-[13rem_1fr]">
        <aside className="hidden lg:block">
          <div className="sticky top-24">
            <FilterPanel key={`${filters.min_price}-${filters.max_price}`} filters={filters} update={update} />
          </div>
        </aside>

        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="sm" className="lg:hidden">
                  <SlidersHorizontalIcon /> Filters
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80 overflow-y-auto">
                <SheetHeader>
                  <SheetTitle>Filters</SheetTitle>
                </SheetHeader>
                <div className="px-4 pb-6">
                  <FilterPanel filters={filters} update={update} />
                </div>
              </SheetContent>
            </Sheet>
            <p className="hidden text-sm text-muted-foreground lg:block">
              {data ? pluralize(data.count, "product") : " "}
            </p>
            <SortSelect value={filters.sort} onChange={(sort) => update({ sort })} />
          </div>

          <ActiveFilters filters={filters} update={update} clear={clear} />

          {isError ? (
            <ErrorState error={error} onRetry={() => refetch()} />
          ) : isPending ? (
            <ProductGrid className="lg:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <ProductCardSkeleton key={i} />
              ))}
            </ProductGrid>
          ) : data.results.length === 0 ? (
            <EmptyState
              icon={SearchXIcon}
              title="No products match"
              description="Try a different search or remove some filters."
              action={
                <Button variant="outline" size="sm" onClick={clear}>
                  Clear filters
                </Button>
              }
            />
          ) : (
            <>
              <ProductGrid className={cn("lg:grid-cols-3", isPlaceholderData && "opacity-60 transition-opacity")}>
                {data.results.map((p, i) => (
                  <ProductCard key={p.id} product={p} priority={i < 3} />
                ))}
              </ProductGrid>
              <Pager
                page={filters.page ?? 1}
                count={data.count}
                pageSize={PAGE_SIZE}
                onPage={(page) => {
                  update({ page: page > 1 ? String(page) : undefined }, false)
                  window.scrollTo({ top: 0, behavior: "smooth" })
                }}
              />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
