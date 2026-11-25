import { LifeBuoyIcon } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useStaffTickets } from "@/features/staff/api"
import { SearchInput, TableShell, useSearch } from "@/features/staff/shared"
import { dateTime } from "@/lib/format"

export default function StaffTicketsPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState("open")
  const search = useSearch()
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useStaffTickets({
    page,
    status: status === "all" ? undefined : status,
    q: search.query,
  })

  return (
    <div className="space-y-6">
      <Title>Support</Title>
      <PageHeader title="Support queue" description="Customer and vendor tickets. Replies are emailed to the user." />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={status} onValueChange={(v) => (setStatus(v), setPage(1))}>
          <TabsList>
            {[
              ["open", "Open"],
              ["in_progress", "In progress"],
              ["resolved", "Resolved"],
              ["closed", "Closed"],
              ["all", "All"],
            ].map(([value, label]) => (
              <TabsTrigger key={value} value={value}>
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <SearchInput value={search.value} onChange={(v) => (search.setValue(v), setPage(1))} placeholder="Subject, user or email" />
      </div>
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={LifeBuoyIcon} title="Queue is empty" description="Nice work." />
      ) : (
        <>
          <TableShell dimmed={isPlaceholderData}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ticket</TableHead>
                  <TableHead>From</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Replies</TableHead>
                  <TableHead>Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((t) => (
                  <TableRow key={t.id} className="cursor-pointer" onClick={() => navigate(`/staff/support/${t.id}`)}>
                    <TableCell>
                      <p className="max-w-72 truncate font-medium">{t.subject}</p>
                      <p className="text-xs text-muted-foreground">
                        #{t.id}
                        {t.order && ` · Order ${t.order}`}
                      </p>
                    </TableCell>
                    <TableCell>
                      <p>{t.user.username}</p>
                      <p className="text-xs text-muted-foreground capitalize">{t.user.role}</p>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={t.status} label={t.status_display} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{t.reply_count}</TableCell>
                    <TableCell className="text-muted-foreground">{dateTime(t.updated_at)}</TableCell>
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
