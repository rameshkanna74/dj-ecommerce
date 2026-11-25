import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

/** Prev/next pager for DRF page-number pagination ({count, next, previous}). */
export function Pager({
  page,
  count,
  pageSize = 20,
  onPage,
}: {
  page: number
  count: number
  pageSize?: number
  onPage: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize))
  if (pages <= 1) return null
  return (
    <nav className="flex items-center justify-center gap-3 pt-6" aria-label="Pagination">
      <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <ChevronLeftIcon /> Previous
      </Button>
      <span className="text-sm text-muted-foreground tabular-nums">
        Page {page} of {pages}
      </span>
      <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next <ChevronRightIcon />
      </Button>
    </nav>
  )
}
