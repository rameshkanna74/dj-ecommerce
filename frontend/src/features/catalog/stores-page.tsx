import { MapPinIcon, StoreIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { ProductImage } from "@/components/product/product-image"
import { useStores } from "@/features/catalog/api"

export default function StoresPage() {
  const [page, setPage] = useState(1)
  const { data, isPending, isError, error, refetch } = useStores(page)

  return (
    <div className="container-page space-y-10 py-10">
      <Title>Stores</Title>
      <PageHeader
        eyebrow="The makers"
        title="Independent stores"
        description="Every store on the marketplace is reviewed and approved before it can sell."
      />
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={StoreIcon} title="No stores yet" description="Approved stores will appear here." />
      ) : (
        <>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {data.results.map((store) => (
              <Link
                key={store.id}
                to={`/stores/${store.store_slug}`}
                className="group overflow-hidden rounded-2xl border transition-shadow hover:shadow-lg"
              >
                <div className="relative h-32 overflow-hidden">
                  <ProductImage
                    src={store.business_banner}
                    name={`${store.business_name} banner`}
                    alt=""
                    size="sm"
                    className="transition-transform duration-500 group-hover:scale-105"
                  />
                </div>
                <div className="relative space-y-2 p-5 pt-10">
                  <div className="absolute -top-8 left-5 size-16 overflow-hidden rounded-xl border-4 border-background bg-muted">
                    <ProductImage src={store.business_logo} name={store.business_name} size="sm" />
                  </div>
                  <p className="font-medium">{store.business_name}</p>
                  <p className="line-clamp-2 min-h-10 text-sm text-muted-foreground">
                    {store.business_description || "Independent maker"}
                  </p>
                  {(store.business_city || store.business_country) && (
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <MapPinIcon className="size-3" />
                      {[store.business_city, store.business_country].filter(Boolean).join(", ")}
                    </p>
                  )}
                </div>
              </Link>
            ))}
          </div>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
    </div>
  )
}
