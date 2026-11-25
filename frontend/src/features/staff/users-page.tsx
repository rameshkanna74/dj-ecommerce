import { UsersIcon } from "lucide-react"
import { useState } from "react"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useSetUserActive, useStaffUsers } from "@/features/staff/api"
import { SearchInput, TableShell, useSearch } from "@/features/staff/shared"
import { date } from "@/lib/format"
import { useAuth } from "@/providers/auth"

export default function StaffUsersPage() {
  const { user: me } = useAuth()
  const [page, setPage] = useState(1)
  const [role, setRole] = useState("all")
  const search = useSearch()
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useStaffUsers({
    page,
    role: role === "all" ? undefined : role,
    q: search.query,
  })
  const setActive = useSetUserActive()

  return (
    <div className="space-y-6">
      <Title>Users</Title>
      <PageHeader title="Users" description="Deactivated users can’t sign in and their sessions stop working." />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={role} onValueChange={(v) => (setRole(v), setPage(1))}>
          <TabsList>
            {["all", "customer", "vendor", "admin"].map((r) => (
              <TabsTrigger key={r} value={r} className="capitalize">
                {r === "all" ? "All" : `${r}s`}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <SearchInput value={search.value} onChange={(v) => (search.setValue(v), setPage(1))} placeholder="Username or email" />
      </div>
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={UsersIcon} title="No users match" />
      ) : (
        <>
          <TableShell dimmed={isPlaceholderData}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead>Last login</TableHead>
                  <TableHead className="text-right">Active</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <p className="font-medium">
                        {[u.first_name, u.last_name].filter(Boolean).join(" ") || u.username}
                        {u.id === me?.id && <span className="ml-2 text-xs text-muted-foreground">(you)</span>}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        @{u.username} · {u.email}
                      </p>
                    </TableCell>
                    <TableCell>
                      <StatusBadge tone={u.role === "admin" ? "brand" : u.role === "vendor" ? "info" : "neutral"} label={u.role} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">{date(u.date_joined)}</TableCell>
                    <TableCell className="text-muted-foreground">{date(u.last_login)}</TableCell>
                    <TableCell className="text-right">
                      <Switch
                        checked={u.is_active !== false}
                        disabled={u.id === me?.id || (setActive.isPending && setActive.variables?.id === u.id)}
                        onCheckedChange={(is_active) => setActive.mutate({ id: u.id, is_active })}
                        aria-label={`${u.is_active ? "Deactivate" : "Activate"} ${u.username}`}
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
