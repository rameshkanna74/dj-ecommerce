import { CheckIcon, StarIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { Stars } from "@/components/product/rating"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useVendorReviews } from "@/features/vendor/api"
import { date } from "@/lib/format"

export default function VendorReviewsPage() {
  const [page, setPage] = useState(1)
  const [rating, setRating] = useState("all")
  const { data, isPending, isError, error, refetch } = useVendorReviews({ page, rating: rating === "all" ? undefined : Number(rating) })

  return (
    <div className="space-y-6">
      <Title>Reviews</Title>
      <PageHeader title="Reviews" description="What customers say about your products. Hidden reviews were moderated by the platform." />
      <Tabs value={rating} onValueChange={(v) => (setRating(v), setPage(1))}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          {[5, 4, 3, 2, 1].map((r) => (
            <TabsTrigger key={r} value={String(r)}>
              {r}★
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={StarIcon} title="No reviews yet" />
      ) : (
        <>
          <ul className="grid gap-4 md:grid-cols-2">
            {data.results.map((r) => (
              <li key={r.id} className="space-y-2 rounded-2xl border p-5">
                <div className="flex items-center justify-between gap-2">
                  <Stars value={r.rating} />
                  <span className="text-xs text-muted-foreground">{date(r.created_at)}</span>
                </div>
                <Link to={`/products/${r.product}`} className="block text-sm font-medium hover:underline">
                  {r.product}
                </Link>
                {r.comment && <p className="text-sm text-muted-foreground">{r.comment}</p>}
                <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  {r.author}
                  {r.is_verified_purchase && (
                    <span className="inline-flex items-center gap-1 text-success">
                      <CheckIcon className="size-3" /> Verified
                    </span>
                  )}
                  {r.is_visible === false && <span className="text-destructive">Hidden by moderation</span>}
                </p>
              </li>
            ))}
          </ul>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
    </div>
  )
}
