import { MapPinIcon, SearchXIcon } from "lucide-react"
import { useParams } from "react-router"

import { Pager } from "@/components/common/pager"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { ProductCard, ProductCardSkeleton, ProductGrid } from "@/components/product/product-card"
import { ProductImage } from "@/components/product/product-image"
import { useStore, useStoreProducts } from "@/features/catalog/api"
import { ActiveFilters, SortSelect, useFilterParams } from "@/features/catalog/products-page"
import { pluralize } from "@/lib/format"

export default function StorePage() {
  const { slug = "" } = useParams()
  const store = useStore(slug)
  const { filters, update, clear } = useFilterParams()
  const products = useStoreProducts(slug, filters)

  if (store.isPending) return <PageLoader />
  if (store.isError)
    return (
      <div className="container-page py-16">
        <ErrorState error={store.error} onRetry={() => store.refetch()} />
      </div>
    )
  const s = store.data

  return (
    <div className="pb-10">
      <Title>{s.business_name}</Title>
      <div className="container-page pt-6">
        <div className="relative h-48 overflow-hidden rounded-3xl md:h-64">
          <ProductImage src={s.business_banner} name={`${s.business_name} studio`} alt="" size="lg" loading="eager" />
        </div>
        <div className="flex flex-col gap-5 px-2 md:flex-row md:items-end md:px-6">
          <div className="-mt-12 size-24 shrink-0 overflow-hidden rounded-2xl border-4 border-background bg-muted shadow-sm md:size-28">
            <ProductImage src={s.business_logo} name={s.business_name} size="sm" />
          </div>
          <div className="space-y-1 pb-1">
            <h1 className="font-heading text-4xl">{s.business_name}</h1>
            {(s.business_city || s.business_country) && (
              <p className="flex items-center gap-1 text-sm text-muted-foreground">
                <MapPinIcon className="size-3.5" />
                {[s.business_city, s.business_country].filter(Boolean).join(", ")}
              </p>
            )}
          </div>
        </div>
        {s.business_description && (
          <p className="mt-6 max-w-3xl px-2 leading-relaxed text-muted-foreground md:px-6">{s.business_description}</p>
        )}
      </div>

      <div className="container-page mt-12 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            {products.data ? pluralize(products.data.count, "product") : " "}
          </p>
          <SortSelect value={filters.sort} onChange={(sort) => update({ sort })} />
        </div>
        <ActiveFilters filters={filters} update={update} clear={clear} />
        {products.isError ? (
          <ErrorState error={products.error} onRetry={() => products.refetch()} />
        ) : products.isPending ? (
          <ProductGrid>
            {Array.from({ length: 4 }, (_, i) => (
              <ProductCardSkeleton key={i} />
            ))}
          </ProductGrid>
        ) : !products.data.results.length ? (
          <EmptyState icon={SearchXIcon} title="No products here yet" />
        ) : (
          <>
            <ProductGrid>
              {products.data.results.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </ProductGrid>
            <Pager
              page={filters.page ?? 1}
              count={products.data.count}
              onPage={(page) => update({ page: page > 1 ? String(page) : undefined }, false)}
            />
          </>
        )}
      </div>
    </div>
  )
}
