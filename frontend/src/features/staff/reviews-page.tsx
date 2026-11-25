import { EyeIcon, EyeOffIcon, StarIcon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { Stars } from "@/components/product/rating"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useModerateReview, useStaffReviews } from "@/features/staff/api"
import { date } from "@/lib/format"
import { cn } from "@/lib/utils"

export default function StaffReviewsPage() {
  const [page, setPage] = useState(1)
  const [visible, setVisible] = useState("all")
  const { data, isPending, isError, error, refetch } = useStaffReviews({ page, visible: visible === "all" ? undefined : visible })
  const moderate = useModerateReview()

  return (
    <div className="space-y-6">
      <Title>Reviews</Title>
      <PageHeader title="Reviews" description="Hide reviews that break the guidelines. Ratings are recalculated automatically." />
      <Tabs value={visible} onValueChange={(v) => (setVisible(v), setPage(1))}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="true">Visible</TabsTrigger>
          <TabsTrigger value="false">Hidden</TabsTrigger>
        </TabsList>
      </Tabs>
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={StarIcon} title="No reviews" />
      ) : (
        <>
          <ul className="grid gap-4 md:grid-cols-2">
            {data.results.map((r) => (
              <li key={r.id} className={cn("space-y-2 rounded-2xl border p-5", r.is_visible === false && "bg-muted/40")}>
                <div className="flex items-center justify-between gap-2">
                  <Stars value={r.rating} />
                  <span className="text-xs text-muted-foreground">{date(r.created_at)}</span>
                </div>
                <Link to={`/products/${r.product}`} className="block text-sm font-medium hover:underline">
                  {r.product}
                </Link>
                <p className="text-sm text-muted-foreground">{r.comment || <em>No comment</em>}</p>
                <div className="flex items-center justify-between gap-2 pt-1">
                  <span className="text-xs text-muted-foreground">
                    {r.author}
                    {r.is_verified_purchase && " · Verified"}
                  </span>
                  <Button
                    size="sm"
                    variant={r.is_visible === false ? "outline" : "ghost"}
                    disabled={moderate.isPending && moderate.variables?.id === r.id}
                    onClick={() => moderate.mutate({ id: r.id, is_visible: r.is_visible === false })}
                  >
                    {r.is_visible === false ? <EyeIcon /> : <EyeOffIcon />}
                    {r.is_visible === false ? "Restore" : "Hide"}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
    </div>
  )
}
